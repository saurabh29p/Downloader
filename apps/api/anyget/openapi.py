"""Print the OpenAPI schema as JSON (used by `make gen` to build packages/shared)."""

import json
import sys

from anyget.main import create_app


def main() -> None:
    schema = create_app().openapi()
    sys.stdout.write(json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
