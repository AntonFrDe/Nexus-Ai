from datetime import UTC, datetime
from typing import Any

from nexus.execution.schemas import (
    CompareRow,
    CompareSide,
    ExecutionComparison,
    ExecutionTrace,
    TraceFailure,
    TraceSpan,
)
from nexus.execution.states import TERMINAL, ExecutionStatus


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _duration(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return int((_aware(end) - _aware(start)).total_seconds() * 1000)


def _labels(execution) -> dict[str, str]:
    return {
        node["id"]: node.get("label") or node["type"].rsplit(".", 1)[-1]
        for node in execution.graph["nodes"]
    }


def _tokens(usage: dict[str, Any]) -> int | None:
    values = [usage.get("input_tokens"), usage.get("output_tokens")]
    known = [value for value in values if value is not None]
    return sum(known) if known else None


def build_trace(execution, rows) -> ExecutionTrace:
    labels = _labels(execution)
    origin = min((_aware(row.started_at) for row in rows), default=None)
    spans = [
        TraceSpan(
            id=row.id,
            node_id=row.node_id,
            label=labels.get(row.node_id, row.node_id),
            node_type=row.node_type,
            status=row.status,
            attempt=row.attempt,
            start_ms=_duration(origin, row.started_at) or 0,
            duration_ms=_duration(row.started_at, row.ended_at),
            model=(row.usage or {}).get("model"),
            tokens=_tokens(row.usage or {}),
            cost_usd=(row.usage or {}).get("cost_usd"),
            error=row.error,
        )
        for row in rows
    ]
    failure = None
    if execution.error and execution.status != ExecutionStatus.PAUSED:
        failed = next((row for row in rows if row.node_id == execution.error_node), None)
        failure = TraceFailure(
            node_id=execution.error_node,
            label=labels.get(execution.error_node or ""),
            message=execution.error,
            input=failed.input if failed else None,
        )
    return ExecutionTrace(
        execution_id=execution.id,
        status=execution.status,
        recorded=ExecutionStatus(execution.status) in TERMINAL,
        replay_of=execution.replay_of,
        overrides=execution.overrides,
        duration_ms=_duration(execution.started_at, execution.ended_at),
        spans=spans,
        failure=failure,
    )


def _side(row) -> CompareSide:
    if row is None:
        return CompareSide(status=None, duration_ms=None, model=None, tokens=None, cost_usd=None)
    usage = row.usage or {}
    return CompareSide(
        status=row.status,
        duration_ms=_duration(row.started_at, row.ended_at),
        model=usage.get("model"),
        tokens=_tokens(usage),
        cost_usd=usage.get("cost_usd"),
        output=row.output,
    )


def _latest(rows) -> dict[str, Any]:
    return {row.node_id: row for row in rows}


def compare_executions(left, left_rows, right, right_rows) -> ExecutionComparison:
    before, after = _latest(left_rows), _latest(right_rows)
    labels = {**_labels(right), **_labels(left)}
    configs = [{n["id"]: n.get("config", {}) for n in run.graph["nodes"]} for run in (left, right)]
    rows = []
    for node_id in [*before, *(key for key in after if key not in before)]:
        one, other = _side(before.get(node_id)), _side(after.get(node_id))
        rows.append(
            CompareRow(
                node_id=node_id,
                label=labels.get(node_id, node_id),
                left=one,
                right=other,
                same_status=one.status == other.status,
                same_output=one.output == other.output,
                config_changed=configs[0].get(node_id) != configs[1].get(node_id),
            )
        )
    return ExecutionComparison(
        left_id=left.id,
        right_id=right.id,
        left_status=left.status,
        right_status=right.status,
        rows=rows,
    )
