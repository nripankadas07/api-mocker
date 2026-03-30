"""CLI interface for api-mocker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import uvicorn

from .server import create_mock_app


def main(argv: list[str] | None = None) -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="api-mocker",
        description="Generate mock REST APIs from OpenAPI specs",
    )
    parser.add_argument(
        "spec",
        type=str,
        help="Path to an OpenAPI 3.x JSON spec file",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible mock data (default: 42)",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        help="Disable seeded randomness for varied responses",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the spec and print routes without starting the server",
    )

    args = parser.parse_args(argv)

    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"Error: Spec file not found: {args.spec}", file=sys.stderr)
        sys.exit(1)

    with open(spec_path) as f:
        try:
            spec = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in spec file: {e}", file=sys.stderr)
            sys.exit(1)

    seed = None if args.no_seed else args.seed

    try:
        app = create_mock_app(spec, seed=seed)
    except ValueError as e:
        print(f"Error: Invalid OpenAPI spec: {e}", file=sys.stderr)
        sys.exit(1)

    if args.validate_only:
        from .parser import OpenAPIParser

        parser_obj = OpenAPIParser.from_dict(spec)
        routes = parser_obj.parse()
        print(f"Valid OpenAPI {spec.get('openapi', '?')} spec")
        print(f"Title: {spec.get('info', {}).get('title', 'Untitled')}")
        print(f"Routes found: {len(routes)}")
        for route in routes:
            print(f"  {route.method:7s} {route.path}")
        return

    print(f"Starting mock server from: {spec_path}")
    print(f"Listening on: http://{args.host}:{args.port}")
    print(f"Mock routes endpoint: http://{args.host}:{args.port}/__mock__/routes")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
