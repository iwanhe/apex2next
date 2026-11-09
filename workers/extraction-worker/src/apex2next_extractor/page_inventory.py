"""WP9.5 APEX page inventory: a deterministic, reviewable UI specification from a SQL export.

The inventory lists every page component the target must account for (regions, items, buttons,
processes, validations, dynamic actions, report/IR columns, cards, charts), plus LOVs, navigation,
breadcrumbs and authorization schemes. Each component has a stable key
``P<page>:<KIND>:<name>`` that the target's coverage matrix must map. Nothing is executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .apex_export import extract_export

INVENTORY_FORMAT = "apex2next.apex-page-inventory.v1"
_ID = re.compile(r"wwv_flow_imp\.id\((\d+)\)")
_STRING = re.compile(r"'((?:[^']|'')*)'")

COMPONENT_ROUTINES = {
    "create_page_plug": ("REGION", "p_plug_name"),
    "create_report_region": ("REPORT_REGION", "p_name"),
    "create_page_item": ("ITEM", "p_name"),
    "create_page_button": ("BUTTON", "p_button_name"),
    "create_page_process": ("PROCESS", "p_process_name"),
    "create_page_validation": ("VALIDATION", "p_validation_name"),
    "create_page_da_event": ("DYNAMIC_ACTION", "p_name"),
    "create_worksheet_column": ("IR_COLUMN", "p_db_column_name"),
    "create_report_columns": ("REPORT_COLUMN", "p_column_alias"),
    "create_region_column": ("REGION_COLUMN", "p_name"),
    "create_worksheet": ("IR", None),
    "create_worksheet_rpt": ("IR_REPORT", "p_report_alias"),
    "create_card": ("CARDS", None),
    "create_card_action": ("CARD_ACTION", "p_action_type"),
    "create_jet_chart": ("CHART", None),
    "create_jet_chart_series": ("CHART_SERIES", "p_name"),
}
KEEP = {
    "REPORT_REGION": ["p_source", "p_query_type", "p_query_order_by", "p_query_num_rows", "p_query_no_data_found",
                      "p_ajax_items_to_submit", "p_display_when_condition", "p_display_condition_type"],
    "REGION": ["p_plug_source_type", "p_query_type", "p_query_table", "p_plug_source", "p_source", "p_query_order_by",
               "p_edit_operations", "p_lost_update_check_type", "p_query_num_rows", "p_query_no_data_found",
               "p_pagination_type", "p_show_total_row_count", "p_plug_query_num_rows_type", "p_plug_query_no_data_found",
               "p_plug_display_point", "p_plug_display_condition_type", "p_plug_display_when_condition"],
    "ITEM": ["p_prompt", "p_display_as", "p_source", "p_source_type", "p_is_primary_key", "p_is_required",
             "p_is_query_only", "p_named_lov", "p_lov_display_null", "p_lov_null_text", "p_item_default",
             "p_read_only_when", "p_read_only_when_type", "p_display_when", "p_display_when_type",
             "p_inline_help_text", "p_format_mask", "p_protection_level", "p_source_data_type",
             "p_lov_display_extra", "p_item_sequence", "p_display_when2"],
    "BUTTON": ["p_button_image_alt", "p_button_sequence", "p_button_is_hot", "p_button_action", "p_button_redirect_url", "p_button_condition", "p_button_condition_type",
               "p_database_action", "p_confirm_message", "p_button_execute_validations", "p_button_position"],
    "PROCESS": ["p_process_point", "p_process_type", "p_process_sql_clob", "p_process_when", "p_process_when_type",
                "p_process_success_message", "p_process_sequence"],
    "VALIDATION": ["p_validation", "p_validation2", "p_validation_type", "p_error_message", "p_validation_condition",
                   "p_validation_condition_type"],
    "DYNAMIC_ACTION": ["p_triggering_element_type", "p_bind_event_type", "p_event_sequence"],
    "IR_COLUMN": ["p_column_label", "p_column_type", "p_format_mask", "p_display_text_as", "p_display_order",
                  "p_column_alignment", "p_column_link", "p_column_linktext", "p_rpt_named_lov"],
    "REPORT_COLUMN": ["p_column_heading", "p_column_format", "p_column_link", "p_column_linktext", "p_hidden_column",
                      "p_column_display_sequence", "p_column_alignment", "p_display_as", "p_derived_column"],
    "REGION_COLUMN": ["p_source_expression", "p_data_type"],
    "IR": ["p_max_row_count", "p_show_search_bar", "p_download_formats", "p_detail_link", "p_detail_link_text",
           "p_no_data_found_message", "p_pagination_type", "p_show_detail_link"],
    "IR_REPORT": ["p_report_columns", "p_sort_column_1", "p_sort_direction_1"],
    "CARDS": ["p_layout_type", "p_title_column_name", "p_sub_title_column_name", "p_body_column_name",
              "p_icon_css_classes"],
    "CARD_ACTION": ["p_action_type", "p_link_target"],
    "CHART": ["p_chart_type", "p_orientation", "p_value_format_type", "p_height", "p_legend_rendered"],
    "CHART_SERIES": ["p_data_source", "p_items_value_column_name", "p_items_label_column_name"],
}


def _text(call: dict[str, Any], key: str) -> Any:
    value = call["arguments"].get(key)
    raw = call["raw_arguments"].get(key)
    if isinstance(value, dict) and raw and "wwv_flow" in raw and "wwv_flow_imp.id" not in raw:
        return "\n".join(m.replace("''", "'") for m in _STRING.findall(raw))
    if isinstance(value, dict):
        return raw
    return value


def _ref(call: dict[str, Any], key: str) -> str | None:
    raw = call["raw_arguments"].get(key)
    m = _ID.search(raw or "")
    return m.group(1) if m else None


def build_page_inventory(files: dict[str, str]) -> dict[str, Any]:
    calls_by_file = {name: extract_export(text)["calls"] for name, text in sorted(files.items())}
    all_calls = [c for calls in calls_by_file.values() for c in calls]
    schemes = {}
    for c in all_calls:
        if c["routine"] == "create_security_scheme":
            schemes[_ref(c, "p_id")] = c["arguments"].get("p_name")
    inventory: dict[str, Any] = {"format": INVENTORY_FORMAT, "application": {}, "authorizations": [], "lovs": [],
                                 "navigation": [], "navigationBar": [], "breadcrumbs": [], "pages": []}
    app_text = next((t for n, t in files.items() if n.endswith("create_application.sql")), "")
    flow = re.search(r"create_flow\((.*?)\n\);", app_text, re.S)
    if flow:  # create_flow mixes expressions the generic call parser does not decode; read its literals
        props = dict(re.findall(r"^,?\s*(p_\w+)=>(.*)$", flow.group(1), re.M))
        lit = {}
        for k, v in props.items():  # literal, or the install-time default of nvl(<getter>, '<literal>')
            m = re.fullmatch(r"(?:nvl\(wwv_flow_application_install\.\w+,)?'((?:[^']|'')*)'\)?", v.strip())
            if m:
                lit[k] = m.group(1).replace("''", "'")
        ref = {k: _ID.search(v).group(1) for k, v in props.items() if _ID.search(v)}
        inventory["application"] = {
            "name": lit.get("p_name"), "alias": lit.get("p_alias"), "dateFormat": lit.get("p_date_format"),
            "timestampFormat": lit.get("p_timestamp_format"), "version": lit.get("p_flow_version"),
            "language": lit.get("p_flow_language"),
            "securityScheme": schemes.get(ref.get("p_security_scheme")),
            "authentication": next((c["arguments"].get("p_name") for c in all_calls
                                    if c["routine"] == "create_authentication"), None),
        }
    for c in all_calls:
        r = c["routine"]
        if r == "create_security_scheme":
            attrs = _text(c, "p_attributes")
            inventory["authorizations"].append({
                "name": c["arguments"].get("p_name"), "type": c["arguments"].get("p_scheme_type"),
                "expression": attrs, "errorMessage": c["arguments"].get("p_error_message")})
        elif r == "create_list_of_values":
            inventory["lovs"].append({"name": c["arguments"].get("p_lov_name"),
                                      "location": c["arguments"].get("p_location"),
                                      "query": _text(c, "p_lov_query") if c["arguments"].get("p_location") != "STATIC" else None,
                                      "id": _ref(c, "p_id"), "values": []})
        elif r == "create_static_lov_data":  # p_lov_id when present, else the preceding LOV of the file
            lov_id = _ref(c, "p_lov_id")
            lov = next((x for x in inventory["lovs"] if x["id"] == lov_id), None) if lov_id else (
                inventory["lovs"][-1] if inventory["lovs"] else None)
            if lov is not None:
                lov["values"].append({"seq": c["arguments"].get("p_lov_disp_sequence"),
                                      "display": c["arguments"].get("p_lov_disp_value"),
                                      "return": c["arguments"].get("p_lov_return_value")})
    item_ids = {_ref(c, "p_id"): c["arguments"].get("p_list_item_link_text") for c in all_calls
                if c["routine"] == "create_list_item"}
    crumb_ids = {_ref(c, "p_id"): c["arguments"].get("p_short_name") for c in all_calls
                 if c["routine"] == "create_menu_option"}
    nav_calls = []
    bar_calls = []
    for calls in calls_by_file.values():  # list items follow their create_list in the same file
        current = None
        for c in calls:
            if c["routine"] == "create_list":
                current = c["arguments"].get("p_name")
            elif c["routine"] == "create_list_item" and current == "Navigation Menu":
                nav_calls.append(c)
            elif c["routine"] == "create_list_item" and current == "Navigation Bar":
                bar_calls.append(c)
    inventory["navigationBar"] = sorted(
        ({"label": c["arguments"].get("p_list_item_link_text"),
          "target": c["arguments"].get("p_list_item_link_target"),
          "sequence": c["arguments"].get("p_list_item_display_sequence"),
          "parent": item_ids.get(_ref(c, "p_parent_list_item_id"))} for c in bar_calls),
        key=lambda x: x["sequence"] or 0)
    for c in all_calls:
        if c in nav_calls:
            target = c["arguments"].get("p_list_item_link_target") or ""
            m = re.search(r"f\?p=&APP_ID\.:(\d+):", target)
            inventory["navigation"].append({
                "label": c["arguments"].get("p_list_item_link_text"), "page": int(m.group(1)) if m else None,
                "sequence": c["arguments"].get("p_list_item_display_sequence"),
                "icon": c["arguments"].get("p_list_item_icon"),
                "parent": item_ids.get(_ref(c, "p_parent_list_item_id")),
                "scheme": schemes.get(_ref(c, "p_security_scheme"))})
        elif c["routine"] == "create_menu_option":
            inventory["breadcrumbs"].append({"label": c["arguments"].get("p_short_name"),
                                             "page": c["arguments"].get("p_page_id"),
                                             "parent": crumb_ids.get(_ref(c, "p_parent_id"))})
    for name, calls in calls_by_file.items():
        page_call = next((c for c in calls if c["routine"] == "create_page"), None)
        if page_call is None:
            continue
        page_id = page_call["arguments"].get("p_id")
        regions = {_ref(c, "p_id"): c["arguments"].get("p_plug_name") or c["arguments"].get("p_name")
                   for c in calls if c["routine"] in {"create_page_plug", "create_report_region"}}
        buttons = {_ref(c, "p_id"): c["arguments"].get("p_button_name") for c in calls
                   if c["routine"] == "create_page_button"}
        page_items = {_ref(c, "p_id"): c["arguments"].get("p_name") for c in calls if c["routine"] == "create_page_item"}
        components = []
        owners: dict[str, str | None] = {}  # chart/worksheet id -> owning region name
        last_region: str | None = None
        for c in calls:
            spec = COMPONENT_ROUTINES.get(c["routine"])
            if not spec:
                continue
            kind, name_key = spec
            ref = (_ref(c, "p_region_id") or _ref(c, "p_plug_id") or _ref(c, "p_item_plug_id")
                   or _ref(c, "p_button_plug_id"))
            region = regions.get(ref) if ref else None
            if region is None:
                owner = _ref(c, "p_chart_id") or _ref(c, "p_worksheet_id")
                region = owners.get(owner) if owner else None
            if region is None and kind not in {"REGION", "REPORT_REGION", "ITEM", "BUTTON", "PROCESS",
                                               "VALIDATION", "DYNAMIC_ACTION"}:
                region = last_region  # worksheets/report columns follow their region in the export
            if kind in {"REGION", "REPORT_REGION"}:
                last_region = c["arguments"].get(name_key)
            if kind in {"IR", "CHART"}:
                owners[_ref(c, "p_id")] = region
            cname = c["arguments"].get(name_key) if name_key else region
            if kind in {"IR_COLUMN", "REPORT_COLUMN", "REGION_COLUMN", "CARD_ACTION", "CHART_SERIES", "IR_REPORT"}:
                cname = f"{region}.{cname}"
            props = {k[2:]: _text(c, k) for k in KEEP[kind] if _text(c, k) not in (None, "")}
            if kind == "DYNAMIC_ACTION":
                trig = _ref(c, "p_triggering_button_id")
                if trig:
                    props["triggering_button"] = buttons.get(trig)
                if _ref(c, "p_triggering_region_id"):
                    props["triggering_region"] = regions.get(_ref(c, "p_triggering_region_id"))
                event_id = _ref(c, "p_id")
                props["actions"] = [
                    {"action": a["arguments"].get("p_action"), "result": a["arguments"].get("p_event_result"),
                     "region": regions.get(_ref(a, "p_affected_region_id")) if _ref(a, "p_affected_region_id") else None}
                    for a in calls if a["routine"] == "create_page_da_action" and _ref(a, "p_event_id") == event_id]
            if kind == "PROCESS" and _ref(c, "p_process_when_button_id"):
                props["when_button"] = buttons.get(_ref(c, "p_process_when_button_id"))
            if kind == "VALIDATION" and _ref(c, "p_associated_item"):
                props["associated_item"] = page_items.get(_ref(c, "p_associated_item"))
            components.append({"key": f"P{page_id}:{kind}:{cname}", "kind": kind, "name": cname, "props": props})
        components.sort(key=lambda x: x["key"])
        dupes = {x["key"] for x in components if [y["key"] for y in components].count(x["key"]) > 1}
        for d in sorted(dupes):  # disambiguate repeated keys deterministically
            for n, comp in enumerate(x for x in components if x["key"] == d):
                comp["key"] = f"{d}#{n + 1}"
        a = page_call["arguments"]
        inventory["pages"].append({
            "id": page_id, "name": a.get("p_name"), "alias": a.get("p_alias"), "title": a.get("p_step_title"),
            "mode": a.get("p_page_mode") or "NORMAL",
            "scheme": schemes.get(_ref(page_call, "p_required_role")), "file": name, "components": components})
    inventory["pages"].sort(key=lambda p: p["id"])
    for lov in inventory["lovs"]:
        lov.pop("id")
        lov["values"].sort(key=lambda v: v["seq"] or 0)
    inventory["lovs"].sort(key=lambda x: x["name"])
    inventory["navigation"].sort(key=lambda x: x["sequence"] or 0)
    inventory["breadcrumbs"].sort(key=lambda x: (x["page"] or 0))
    inventory["authorizations"].sort(key=lambda x: x["name"])
    inventory["summary"] = {"pages": len(inventory["pages"]),
                            "components": sum(len(p["components"]) for p in inventory["pages"])}
    inventory["sha256"] = hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest()
    return inventory


def inventory_from_export_dir(directory: Path) -> dict[str, Any]:
    files = {p.relative_to(directory).as_posix(): p.read_text(encoding="utf-8", errors="replace")
             for p in sorted(directory.rglob("*.sql"))}
    return build_page_inventory(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the WP9.5 APEX page inventory from an unpacked SQL export")
    parser.add_argument("export_dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inv = inventory_from_export_dir(args.export_dir)
    args.output.write_text(json.dumps(inv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
