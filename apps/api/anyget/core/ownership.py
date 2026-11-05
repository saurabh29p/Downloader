"""v2 ownership migration: rows made before sign-in existed get an owner.

Library items and watches are the owner's. Jobs are different: a hosted AnyGet (or one
with an owner sign-in) used to show its job list to anyone, so those old rows are
cleared instead. Their files stay on disk and in the Library. Runs at every start; it
only touches rows without a user, which new code never writes.
"""

import logging

from sqlalchemy import delete, update
from sqlmodel import col

from anyget.core.db import Database
from anyget.core.jobs import Job
from anyget.core.settings import Settings
from anyget.core.users import OWNER_ID
from anyget.library.models import LibraryItem
from anyget.watch.models import Watch

log = logging.getLogger("anyget.ownership")


def adopt_rows(db: Database, settings: Settings) -> dict[str, int]:
    counts: dict[str, int] = {}
    with db.session() as session:
        for name, model in (("library", LibraryItem), ("watches", Watch)):
            result = session.execute(
                update(model).where(col(model.user_id).is_(None)).values(user_id=OWNER_ID)
            )
            counts[name] = int(getattr(result, "rowcount", 0) or 0)
        jobs = col(Job.user_id).is_(None)
        if settings.hosted or settings.owner_configured:
            result = session.execute(delete(Job).where(jobs))
            counts["jobs_cleared"] = int(getattr(result, "rowcount", 0) or 0)
        else:
            result = session.execute(update(Job).where(jobs).values(user_id=OWNER_ID))
            counts["jobs"] = int(getattr(result, "rowcount", 0) or 0)
        session.commit()
    if any(counts.values()):
        log.info("ownership migration: %s", counts)
    return counts
