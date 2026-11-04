# anyget (API + CLI)

FastAPI core and Typer CLI for AnyGet. See the root `CLAUDE.md`.

```sh
uv sync
uv run uvicorn anyget.main:app --reload   # http://127.0.0.1:8000/api/health
uv run anyget version
uv run pytest
```
