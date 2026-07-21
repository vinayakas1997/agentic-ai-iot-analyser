"""Shared schema utility functions for the Manager Agent."""


def build_planner_schema_payload(line_context: dict | None, dataset_context: dict | None) -> dict:
    if not line_context:
        return {
            "datasets_in_scope": [],
            "datasets_excluded": [],
            "dataset_schemas": [],
            "join_catalog": [],
        }
    line_name = line_context.get("line_name")
    entry = (dataset_context or {}).get("by_line", {}).get(line_name) or {}
    return {
        "datasets_in_scope": line_context.get("datasets_in_scope") or entry.get("included") or [],
        "datasets_excluded": line_context.get("datasets_excluded") or entry.get("excluded") or [],
        "dataset_schemas": line_context.get("datasets_full") or [],
        "join_catalog": line_context.get("join_catalog") or [],
    }
