# api-mocker

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Tests: Passing](https://img.shields.io/badge/Tests-Passing-green.svg)]()

Generate mock REST APIs from OpenAPI 3.x specifications. Point it at a spec file and get a fully functional FastAPI server with realistic mock responses â no backend required.

## Why

When building frontends, writing integration tests, or prototyping API consumers, you need a server that speaks your API contract. `api-mocker` reads your OpenAPI spec and spins up a live server that returns schema-compliant mock data with zero configuration.

## Installation

```bash
pip install -e .
```

Or with dev dependencies:

```bash
pip install -e ".[dev]"
```

## Usage

### CLI

```bash
# Start a mock server from your spec
api-mocker openapi.json

# Custom host and port
api-mocker openapi.json --host 0.0.0.0 --port 3000

# Validate spec without starting server
api-mocker openapi.json --validate-only

# Disable seeded randomness for varied responses
api-mocker openapi.json --no-seed
```

### Programmatic

```python
from api_mocker.server import create_mock_app

spec = {
    "openapi": "3.0.3",
    "info": {"title": "My API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {
                "responses": {
                    "200": {
                        "description": "User list",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "integer"},
                                            "email": {"type": "string", "format": "email"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

app = create_mock_app(spec, seed=42)
# Use with uvicorn or TestClient
```

### Inspecting Routes

Every mock server exposes a metadata endpoint:

```bash
curl http://localhost:8000/__mock__/routes
```

## API Reference

### `OpenAPIParser`

Parses an OpenAPI 3.x spec into route definitions.

- `from_file(path)` â Load from a JSON file
- `from_dict(spec)` â Load from a dictionary
- `parse()` â Returns `list[RouteDefinition]`

### `MockDataGenerator`

Generates schema-compliant mock data.

- `generate(schema)` â Returns mock data matching the JSON Schema
- Supports: objects, arrays, strings (with format: email, uuid, date, uri), integers, numbers, booleans, enums, allOf/oneOf/anyOf

### `create_mock_app(spec, seed=42)`

Creates a FastAPI application from an OpenAPI spec. Seed controls deterministic mock data generation.

## Architecture

```
api_mocker/
  parser.py      # OpenAPI spec parsing + $ref resolution
  generator.py   # Mock data generation from JSON Schema
  server.py      # FastAPI app builder + route registration
  cli.py         # CLI entry point (argparse + uvicorn)
```

The flow is: **Spec** â `Parser` â `RouteDefinitions` â `Generator` produces mock data â `Server` registers FastAPI routes returning that data.

## License

MIT
