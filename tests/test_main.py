"""Tests for api-mocker."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_mocker.parser import OpenAPIParser, RouteDefinition
from api_mocker.generator import MockDataGenerator
from api_mocker.server import create_mock_app


# --- Sample OpenAPI Specs ---

PETSTORE_SPEC = {
    "openapi": "3.0.3",
    "info": {"title": "Petstore", "version": "1.0.0"},
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "responses": {
                    "200": {
                        "description": "A list of pets",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "$ref": "#/components/schemas/Pet"
                                    },
                                }
                            }
                        },
                    }
                },
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "responses": {
                    "201": {
                        "description": "Pet created",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Pet"}
                            }
                        },
                    }
                },
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "getPet",
                "summary": "Get a pet by ID",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "A pet",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Pet"}
                            }
                        },
                    }
                },
            },
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
                "responses": {"204": {"description": "Pet deleted"}},
            },
        },
    },
    "components": {
        "schemas": {
            "Pet": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "minimum": 1, "maximum": 9999},
                    "name": {"type": "string", "minLength": 3, "maxLength": 20},
                    "species": {
                        "type": "string",
                        "enum": ["dog", "cat", "bird", "fish"],
                    },
                    "age": {"type": "integer", "minimum": 0, "maximum": 30},
                },
            }
        }
    },
}

MINIMAL_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Minimal", "version": "0.1.0"},
    "paths": {
        "/health": {
            "get": {
                "summary": "Health check",
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "ok"}
                                    },
                                }
                            }
                        },
                    }
                },
            }
        }
    },
}


# --- Parser Tests ---


class TestParser:
    def test_parse_petstore_routes(self) -> None:
        parser = OpenAPIParser.from_dict(PETSTORE_SPEC)
        routes = parser.parse()
        assert len(routes) == 4
        methods = {(r.path, r.method) for r in routes}
        assert ("/pets", "GET") in methods
        assert ("/pets", "POST") in methods
        assert ("/pets/{petId}", "GET") in methods
        assert ("/pets/{petId}", "DELETE") in methods

    def test_parse_operation_ids(self) -> None:
        parser = OpenAPIParser.from_dict(PETSTORE_SPEC)
        routes = parser.parse()
        op_ids = {r.operation_id for r in routes}
        assert "listPets" in op_ids
        assert "createPet" in op_ids

    def test_parse_status_codes(self) -> None:
        parser = OpenAPIParser.from_dict(PETSTORE_SPEC)
        routes = parser.parse()
        route_map = {r.operation_id: r for r in routes}
        assert route_map["listPets"].status_code == 200
        assert route_map["createPet"].status_code == 201
        assert route_map["deletePet"].status_code == 204

    def test_parse_resolves_refs(self) -> None:
        parser = OpenAPIParser.from_dict(PETSTORE_SPEC)
        routes = parser.parse()
        get_pet = next(r for r in routes if r.operation_id == "getPet")
        assert "properties" in get_pet.response_schema
        assert "id" in get_pet.response_schema["properties"]

    def test_invalid_spec_missing_openapi(self) -> None:
        with pytest.raises(ValueError, match="Missing 'openapi'"):
            OpenAPIParser.from_dict({"paths": {}})

    def test_invalid_spec_missing_paths(self) -> None:
        with pytest.raises(ValueError, match="Missing 'paths'"):
            OpenAPIParser.from_dict({"openapi": "3.0.0"})

    def test_invalid_spec_wrong_version(self) -> None:
        with pytest.raises(ValueError, match="Only OpenAPI 3.x"):
            OpenAPIParser.from_dict({"openapi": "2.0", "paths": {}})

    def test_from_file(self, tmp_path: Path) -> None:
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(MINIMAL_SPEC))
        parser = OpenAPIParser.from_file(spec_file)
        routes = parser.parse()
        assert len(routes) == 1

    def test_from_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            OpenAPIParser.from_file("/nonexistent/spec.json")


# --- Generator Tests ---


class TestGenerator:
    def test_generate_object(self) -> None:
        gen = MockDataGenerator(seed=42)
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer", "minimum": 0, "maximum": 100},
            },
        }
        result = gen.generate(schema)
        assert isinstance(result, dict)
        assert "name" in result
        assert "age" in result
        assert isinstance(result["name"], str)
        assert isinstance(result["age"], int)

    def test_generate_array(self) -> None:
        gen = MockDataGenerator(seed=42)
        schema = {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 2,
            "maxItems": 5,
        }
        result = gen.generate(schema)
        assert isinstance(result, list)
        assert 2 <= len(result) <= 5
        assert all(isinstance(x, str) for x in result)

    def test_generate_enum(self) -> None:
        gen = MockDataGenerator(seed=42)
        schema = {"type": "string", "enum": ["a", "b", "c"]}
        result = gen.generate(schema)
        assert result in ["a", "b", "c"]

    def test_generate_with_example(self) -> None:
        gen = MockDataGenerator(seed=42)
        schema = {"type": "string", "example": "hello"}
        result = gen.generate(schema)
        assert result == "hello"

    def test_generate_email_format(self) -> None:
        gen = MockDataGenerator(seed=42)
        schema = {"type": "string", "format": "email"}
        result = gen.generate(schema)
        assert "@example.com" in result

    def test_generate_reproducible(self) -> None:
        gen1 = MockDataGenerator(seed=99)
        gen2 = MockDataGenerator(seed=99)
        schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
        assert gen1.generate(schema) == gen2.generate(schema)

    def test_generate_boolean(self) -> None:
        gen = MockDataGenerator(seed=42)
        result = gen.generate({"type": "boolean"})
        assert isinstance(result, bool)

    def test_generate_number(self) -> None:
        gen = MockDataGenerator(seed=42)
        result = gen.generate({"type": "number", "minimum": 0.0, "maximum": 10.0})
        assert isinstance(result, float)
        assert 0.0 <= result <= 10.0


# --- Server / Integration Tests ---


class TestServer:
    def test_petstore_mock_server(self) -> None:
        app = create_mock_app(PETSTORE_SPEC, seed=42)
        client = TestClient(app)

        resp = client.get("/pets")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert "id" in data[0]
        assert "name" in data[0]

    def test_get_pet_by_id(self) -> None:
        app = create_mock_app(PETSTORE_SPEC, seed=42)
        client = TestClient(app)

        resp = client.get("/pets/1")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "id" in data

    def test_create_pet(self) -> None:
        app = create_mock_app(PETSTORE_SPEC, seed=42)
        client = TestClient(app)

        resp = client.post("/pets", json={"name": "Buddy", "species": "dog"})
        assert resp.status_code == 201

    def test_delete_pet(self) -> None:
        app = create_mock_app(PETSTORE_SPEC, seed=42)
        client = TestClient(app)

        resp = client.delete("/pets/1")
        assert resp.status_code == 204

    def test_mock_routes_metadata(self) -> None:
        app = create_mock_app(PETSTORE_SPEC, seed=42)
        client = TestClient(app)

        resp = client.get("/__mock__/routes")
        assert resp.status_code == 200
        routes = resp.json()
        assert len(routes) == 4
        assert any(r["operation_id"] == "listPets" for r in routes)

    def test_minimal_spec_health(self) -> None:
        app = create_mock_app(MINIMAL_SPEC, seed=42)
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_reproducible_responses(self) -> None:
        app1 = create_mock_app(PETSTORE_SPEC, seed=42)
        app2 = create_mock_app(PETSTORE_SPEC, seed=42)
        client1 = TestClient(app1)
        client2 = TestClient(app2)

        r1 = client1.get("/pets").json()
        r2 = client2.get("/pets").json()
        assert r1 == r2
