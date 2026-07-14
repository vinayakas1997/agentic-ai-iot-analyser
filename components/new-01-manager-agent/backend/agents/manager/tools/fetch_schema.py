import json
import logging

from agents.manager.db import build_full_line_schema, fetch_global_datasets
from agents.manager.state import ManagerState

logger = logging.getLogger(__name__)


async def tool_fetch_schema(state: ManagerState) -> ManagerState:
    logger.debug("tool_fetch_schema: starting")
    slots = state.get("slots") or {}
    line = slots.get("line") or {}
    canonical = line.get("canonical")
    dataset_context = dict(state.get("dataset_context") or {})

    if not canonical:
        return {**state, "tool_result": json.dumps({"error": "no_line_resolved"})}

    datasets = await fetch_global_datasets(canonical)
    if not datasets:
        return {**state, "error": "no_datasets", "tool_result": json.dumps({"error": "no_datasets", "line": canonical})}

    schema = build_full_line_schema(canonical, datasets)

    data_earliest_map = {}
    for ds in datasets:
        if ds.get("data_earliest_ts"):
            data_earliest_map[ds.get("dataset_name")] = ds["data_earliest_ts"]

    by_line = dict(dataset_context.get("by_line") or {})
    dataset_names = [d.get("dataset_name") for d in schema.get("datasets") or [] if d.get("dataset_name")]
    by_line[canonical] = {
        "loaded": True,
        "available": dataset_names,
        "included": dataset_names[:],
        "excluded": [],
        "mentioned": [],
        "full_schema": schema,
        "bundle": {
            "line_name": canonical,
            "datasets": datasets,
            "schema": schema,
            "full_schema": schema,
            "global_version": datasets[0].get("global_version", 1) if datasets else 1,
            "dataset_names": dataset_names,
        },
    }
    dataset_context["by_line"] = by_line
    dataset_context["active_line"] = canonical

    line_context = {
        "line_name": canonical,
        "datasets": datasets,
        "schema": schema,
        "datasets_full": schema.get("datasets") or [],
        "dataset_summaries": [
            {
                "dataset_name": ds.get("dataset_name"),
                "table": ds.get("source_config", {}).get("table") if isinstance(ds.get("source_config"), dict) else None,
                "role": ds.get("role"),
                "description": ds.get("description"),
                "data_earliest_ts": ds.get("data_earliest_ts"),
            }
            for ds in datasets
        ],
        "suggested_aims": [
            {
                "aim": aim,
                "dataset": ds.get("dataset_name"),
                "role": ds.get("role"),
                "kpi_value": "",
            }
            for ds in datasets
            for aim in (ds.get("suggested_aims") or [])
        ],
        "join_catalog": schema.get("join_catalog") or [],
    }

    result = {
        "datasets": [d.get("dataset_name") for d in datasets if d.get("dataset_name")],
        "data_earliest": data_earliest_map,
        "suggested_aims": line_context["suggested_aims"],
    }

    return {
        **state,
        "line_context": line_context,
        "dataset_context": dataset_context,
        "slots": {**slots, "dataset_context": dataset_context},
        "tool_result": json.dumps(result),
    }
