from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexus.execution.models import Execution, NodeExecution


def _bucket() -> dict[str, Any]:
    return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "unpriced": 0}


def _add(bucket: dict[str, Any], usage: dict[str, Any]) -> None:
    bucket["calls"] += 1
    bucket["input_tokens"] += usage.get("input_tokens") or 0
    bucket["output_tokens"] += usage.get("output_tokens") or 0
    cost = usage.get("cost_usd")
    if cost is None:
        # An unknown price stays visible instead of reading as free.
        bucket["unpriced"] += 1
    else:
        bucket["cost_usd"] = round(bucket["cost_usd"] + cost, 6)


def summarize(factory: sessionmaker[Session], days: int) -> dict[str, Any]:
    since = datetime.now(UTC) - timedelta(days=days)
    with factory() as session:
        runs = list(session.scalars(select(Execution).where(Execution.created_at >= since)))
        calls = session.execute(
            select(NodeExecution.usage, Execution.workflow_name, Execution.created_at)
            .join(Execution, NodeExecution.execution_id == Execution.id)
            .where(Execution.created_at >= since, NodeExecution.usage.is_not(None))
        ).all()
        session.expunge_all()

    totals = _bucket()
    by_model: dict[str, dict[str, Any]] = defaultdict(_bucket)
    by_workflow: dict[str, dict[str, Any]] = defaultdict(_bucket)
    by_day: dict[str, dict[str, Any]] = defaultdict(_bucket)
    for usage, workflow, created in calls:
        _add(totals, usage)
        _add(by_model[usage.get("model", "unknown")], usage)
        _add(by_workflow[workflow], usage)
        _add(by_day[created.date().isoformat()], usage)

    statuses: dict[str, int] = defaultdict(int)
    failures: dict[str, int] = defaultdict(int)
    for run in runs:
        statuses[run.status] += 1
        if run.error:
            failures[run.error[:120]] += 1

    def rows(groups: dict[str, dict[str, Any]], key: str) -> list[dict[str, Any]]:
        return [{key: name, **values} for name, values in groups.items()]

    return {
        "days": days,
        "runs": len(runs),
        "statuses": statuses,
        "totals": totals,
        "by_model": sorted(rows(by_model, "model"), key=lambda row: -row["calls"]),
        "by_workflow": sorted(rows(by_workflow, "workflow"), key=lambda row: -row["calls"]),
        "by_day": sorted(rows(by_day, "day"), key=lambda row: row["day"]),
        "top_errors": [
            {"error": error, "count": count}
            for error, count in sorted(failures.items(), key=lambda item: -item[1])[:5]
        ],
    }
