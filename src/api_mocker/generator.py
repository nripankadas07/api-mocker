"""Generate mock data from OpenAPI schema definitions."""

from __future__ import annotations

import random
import string
from typing import Any


class MockDataGenerator:
    """Generate realistic mock data from JSON Schema / OpenAPI schema objects."""

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    def generate(self, schema: dict[str, Any]) -> Any:
        """Generate mock data matching the given schema."""
        if not schema:
            return {}

        if "$ref" in schema:
            # Unresolved ref â return empty object
            return {}

        schema_type = schema.get("type")

        # Handle enum
        if "enum" in schema:
            return self._rng.choice(schema["enum"])

        # Handle example
        if "example" in schema:
            return schema["example"]

        # Handle allOf
        if "allOf" in schema:
            merged: dict[str, Any] = {}
            for sub in schema["allOf"]:
                result = self.generate(sub)
                if isinstance(result, dict):
                    merged.update(result)
            return merged

        # Handle oneOf / anyOf â pick first
        if "oneOf" in schema:
            return self.generate(schema["oneOf"][0])
        if "anyOf" in schema:
            return self.generate(schema["anyOf"][0])

        if schema_type == "object":
            return self._generate_object(schema)
        elif schema_type == "array":
            return self._generate_array(schema)
        elif schema_type == "string":
            return self._generate_string(schema)
        elif schema_type == "integer":
            return self._generate_integer(schema)
        elif schema_type == "number":
            return self._generate_number(schema)
        elif schema_type == "boolean":
            return self._rng.choice([True, False])
        elif schema_type == "null":
            return None
        else:
            # No type specified â try to infer from properties
            if "properties" in schema:
                return self._generate_object(schema)
            return {}

    def _generate_object(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate a mock object from schema properties."""
        result: dict[str, Any] = {}
        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            result[prop_name] = self.generate(prop_schema)
        return result

    def _generate_array(self, schema: dict[str, Any]) -> list[Any]:
        """Generate a mock array."""
        items_schema = schema.get("items", {})
        min_items = schema.get("minItems", 1)
        max_items = schema.get("maxItems", 3)
        count = self._rng.randint(min_items, max_items)
        return [self.generate(items_schema) for _ in range(count)]

    def _generate_string(self, schema: dict[str, Any]) -> str:
        """Generate a mock string based on format hints."""
        fmt = schema.get("format", "")
        if fmt == "email":
            name = self._random_word(8)
            return f"{name}@example.com"
        elif fmt == "uri" or fmt == "url":
            return f"https://example.com/{self._random_word(6)}"
        elif fmt == "uuid":
            hex_chars = "0123456789abcdef"
            parts = [
                "".join(self._rng.choices(hex_chars, k=8)),
                "".join(self._rng.choices(hex_chars, k=4)),
                "4" + "".join(self._rng.choices(hex_chars, k=3)),
                "".join(self._rng.choices(hex_chars, k=4)),
                "".join(self._rng.choices(hex_chars, k=12)),
            ]
            return "-".join(parts)
        elif fmt == "date":
            return f"2024-{self._rng.randint(1, 12):02d}-{self._rng.randint(1, 28):02d}"
        elif fmt == "date-time":
            return f"2024-{self._rng.randint(1, 12):02d}-{self._rng.randint(1, 28):02d}T{self._rng.randint(0, 23):02d}:{self._rng.randint(0, 59):02d}:00Z"

        min_len = schema.get("minLength", 5)
        max_len = schema.get("maxLength", 20)
        length = self._rng.randint(min_len, max_len)
        return self._random_word(length)

    def _generate_integer(self, schema: dict[str, Any]) -> int:
        """Generate a mock integer."""
        minimum = schema.get("minimum", 0)
        maximum = schema.get("maximum", 1000)
        return self._rng.randint(int(minimum), int(maximum))

    def _generate_number(self, schema: dict[str, Any]) -> float:
        """Generate a mock number."""
        minimum = schema.get("minimum", 0.0)
        maximum = schema.get("maximum", 1000.0)
        return round(self._rng.uniform(float(minimum), float(maximum)), 2)

    def _random_word(self, length: int) -> str:
        """Generate a random lowercase word."""
        return "".join(self._rng.choices(string.ascii_lowercase, k=length))
