"""Retention: see the cleanup policy, and preview or run a cleanup."""

from typing import Annotated

from fastapi import APIRouter, Query

from anyget.api.deps import ServicesDep
from anyget.library.retention import CleanupResult, RetentionStatus

router = APIRouter(tags=["retention"])


@router.get("/retention", operation_id="getRetention")
async def get_retention(services: ServicesDep) -> RetentionStatus:
    """The policy: days (0 = off), when removals start (grace period), the last run."""
    return services.retention.status()


@router.post("/retention/run", operation_id="runRetention")
async def run_retention(
    services: ServicesDep, dry_run: Annotated[bool, Query()] = True
) -> CleanupResult:
    """What a cleanup would remove (dry_run=true, the default), or run it now."""
    return services.retention.run(dry_run=dry_run)
