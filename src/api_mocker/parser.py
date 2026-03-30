"""Parse OpenAPI 3.x specifications into internal route definitions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RouteDefinition:
    """Represents a single API route parsed from an OpenAPI spec."""

    def __init__(
        self,
        path: str,
        method: str,
        operation_id: str | None,
        summary: str | None,
        response_schema: dict[str, Any] | None,
        status_code: int,
        parameters: list[dict[str, Any]] | None = None,
    ) -> None:
        self.path = path
        self.method = method.upper()
        self.operation_id = operation_id
        self.summary = summary
        self.response_schema = response_schema or {}
        self.status_code = status_code
        self.parameters = parameters or []

    def __repr__(self) -> str:
        return f"RouteDefinition({self.method} {self.path})"


class OpenAPIParser:
    """Parse an OpenAPI 3.x JSON/YAML spec into route definitions."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        self._validate_spec()

    @classmethod
    def from_file(cls, path: str | Path) -> "OpenAPIParser":
        """Load spec from a JSON file."""
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Spec file not found: {path}")
        with open(file_path) as f:
            spec = json.load(f)
        return cls(spec)

    @classmethod
    def from_dict(cls, spec: dict[str, Any]) -> "OpenAPIParser":
        """Load spec from a dictionary."""
        return cls(spec)

    def _validate_spec(self) -> None:
        """Basic validation of the OpenAPI spec."""
        if "openapi" not in self.spec:
            raise ValueError("Missing 'openapi' version field in spec")
        if "paths" not in self.spec:
            raise ValueError("Missing 'paths' field in spec")
        version = self.spec["openapi"]
        if not version.startswith("3."):
            raise ValueError(f"Only OpenAPI 3.x is supported, got {version}")

    def _resolve_ref(self, ref: str) -> dict[str, Any]:
        """Resolve a $ref pointer within the spec."""
        parts = ref.lstrip("#/").split("/")
        obj: Any = self.spec
        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part, {})
            else:
                return {}
        return obj if isinstance(obj, dict) else {}

    def _resolve_schema(self, schema: dict[str, Any] | None) -> dict[str, Any]:
        """Resolve a schema, following $ref recursively."""
        if schema is None:
            return {}
        return self._deep_resolve(schema)

    def _deep_resolve(self, obj: dict[str, Any], _seen: set[str] | None = None) -> dict[str, Any]:
        """Recursively resolve all $ref pointers in a schema."""
        if _seen is None:
            _seen = set()

        if "$ref" in obj:
            ref = obj["$ref"]
            if ref in _seen:
                return {}
            _seen = _seen | {ref}
            resolved = self._resolve_ref(ref)
            return self._deep_resolve(resolved, _seen)

        result: dict[str, Any] = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                result[key] = self._deep_resolve(value, _seen)
            elif isinstance(value, list):
                result[key] = [
                    self._deep_resolve(item, _seen) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def parse(self) -> list[RouteDefinition]:
        """Parse all paths and methods into RouteDefinition objects."""
        routes: list[RouteDefinition] = []
        paths = self.spec.get("paths", {})

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in ("get", "post", "put", "patch", "delete", "head", "options"):
                if method not in path_item:
                    continue
                operation = path_item[method]
                if not isinstance(operation, dict):
                    continue

                operation_id = operation.get("operationId")
                summary = operation.get("summary")
                parameters = operation.get("parameters", [])

                # Find the success response schema
                responses = operation.get("responses", {})
                status_code, response_schema = self._extract_response(responses)

                routes.append(
                    RouteDefinition(
                        path=path,
                        method=method,
                        operation_id=operation_id,
                        summary=summary,
                        response_schema=response_schema,
                        status_code=status_code,
                        parameters=parameters,
                    )
                )

        return routes

    def _extract_response(
        self, responses: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        """Extract the primary success response schema and status code."""
        # Prefer 200, then 201, then first 2xx
        for code in ["200", "201"]:
            if code in responses:
                schema = self._get_response_schema(responses[code])
                return int(code), schema

        for code, response in responses.items():
            if code.startswith("2"):
                schema = self._get_response_schema(response)
                return int(code), schema

        return 200, {}

    def _get_response_schema(self, response: dict[str, Any]) -> dict[str, Any]:
        """Extract schema from a response object."""
        if "$ref" in response:
            response = self._resolve_ref(response["$ref"])
        content = response.get("content", {})
        json_content = content.get("application/json", {})
        schema = json_content.get("schema", {})
        return self._resolve_schema(schema)
