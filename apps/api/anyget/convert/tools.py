"""Run an external converter with a time limit and a readable error."""

import asyncio
import shutil

from anyget.handlers.base import HandlerError


def which(name: str) -> str | None:
    return shutil.which(name)


async def run(args: list[str], *, time_limit: float = 3600, what: str = "converter") -> str:
    exe = which(args[0])
    if exe is None:
        raise HandlerError("tool_missing", f"{args[0]} is not installed")
    process = await asyncio.create_subprocess_exec(
        exe, *args[1:], stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), time_limit)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise HandlerError("upstream", f"{what} took too long") from exc
    except asyncio.CancelledError:
        process.kill()
        await process.wait()
        raise
    if process.returncode != 0:
        lines = stderr.decode(errors="replace").strip().splitlines() or ["no output"]
        raise HandlerError("upstream", f"{what} failed: {lines[-1][:300]}")
    return stdout.decode(errors="replace")
