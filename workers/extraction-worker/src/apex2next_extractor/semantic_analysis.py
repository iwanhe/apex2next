"""Conservative semantic classification and versioned transformation planning."""
from __future__ import annotations
import hashlib
import json
from typing import Any
from .dependency_graph import analyze_dependency_graph

SEMANTIC_VERSION = "0.1.0"
RULESET_VERSION = "1.0.0"

COMPONENT_RULES = {
    "APPLICATION": ("Next.js application shell", "UI", "ASSISTED", .95, "APEX_APPLICATION_TO_NEXT_APP_V1"),
    "PAGE": ("Next.js App Router page/route", "UI", "ASSISTED", .95, "APEX_PAGE_TO_NEXT_ROUTE_V1"),
    "REGION": ("React server/client component", "UI", "ASSISTED", .90, "APEX_REGION_TO_REACT_COMPONENT_V1"),
    "ITEM": ("React form control + typed DTO field", "UI_AND_API", "ASSISTED", .90, "APEX_ITEM_TO_FORM_FIELD_V1"),
    "BUTTON": ("React button/action + API command", "UI_AND_API", "ASSISTED", .85, "APEX_BUTTON_TO_ACTION_V1"),
    "BRANCH": ("Next.js navigation/redirect", "UI", "ASSISTED", .85, "APEX_BRANCH_TO_NAVIGATION_V1"),
    "VALIDATION": ("NestJS DTO/domain validator", "API", "ASSISTED", .85, "APEX_VALIDATION_TO_NEST_VALIDATOR_V1"),
    "PROCESS": ("NestJS application/domain service", "API", "MANUAL", .75, "APEX_PROCESS_TO_NEST_SERVICE_V1"),
    "DYNAMIC_ACTION": ("React event/state handler or client workflow", "UI", "ASSISTED", .75, "APEX_DA_TO_REACT_HANDLER_V1"),
    "DYNAMIC_ACTION_ACTION": ("React handler or API command", "UI_AND_API", "ASSISTED", .70, "APEX_DA_ACTION_TO_HANDLER_V1"),
    "LIST": ("Next.js navigation/menu configuration", "UI", "ASSISTED", .90, "APEX_LIST_TO_NAV_CONFIG_V1"),
    "LIST_ITEM": ("Navigation item", "UI", "ASSISTED", .90, "APEX_LIST_ITEM_TO_NAV_ITEM_V1"),
    "BREADCRUMB": ("Next.js breadcrumb component", "UI", "ASSISTED", .95, "APEX_BREADCRUMB_TO_REACT_V1"),
    "LOV": ("PostgreSQL lookup + API endpoint + select control", "DATA_AND_API_AND_UI", "ASSISTED", .80, "APEX_LOV_TO_LOOKUP_V1"),
    "AUTHENTICATION": ("NestJS authentication strategy/identity provider adapter", "SECURITY", "MANUAL", .65, "APEX_AUTHN_TO_IDENTITY_ADAPTER_V1"),
    "AUTHORIZATION": ("NestJS guard/policy/permission service", "SECURITY", "ASSISTED", .80, "APEX_AUTHZ_TO_POLICY_GUARD_V1"),
    "THEME": ("Design tokens + shared UI theme", "UI", "ASSISTED", .85, "APEX_THEME_TO_DESIGN_TOKENS_V1"),
    "PLUGIN": ("Custom Next.js/NestJS adapter or replacement", "CROSS_CUTTING", "MANUAL", .45, "APEX_PLUGIN_TO_ADAPTER_V1"),
    "COLUMN": ("PostgreSQL column + API field", "DATA", "ASSISTED", .85, "APEX_COLUMN_TO_POSTGRES_FIELD_V1"),
    "DISPLAY_COLUMN": ("React table column definition", "UI", "ASSISTED", .90, "APEX_DISPLAY_COLUMN_TO_TABLE_COLUMN_V1"),
    "COMPONENT_ENTRY": ("Reusable React component/configuration", "UI", "ASSISTED", .75, "APEX_COMPONENT_ENTRY_TO_REACT_V1"),
    "PAGE_GROUP": ("Next.js route group/layout", "UI", "ASSISTED", .85, "APEX_PAGE_GROUP_TO_ROUTE_GROUP_V1"),
    "STATIC_FILE": ("Public asset or managed object storage", "ASSET", "ASSISTED", .90, "APEX_STATIC_FILE_TO_ASSET_V1"),
    "BUILD_OPTION": ("Build-time feature/configuration flag", "CONFIG", "ASSISTED", .75, "APEX_BUILD_OPTION_TO_FEATURE_FLAG_V1"),
    "COMPONENT_SETTING": ("Typed component configuration", "CONFIG", "ASSISTED", .65, "APEX_COMPONENT_SETTING_TO_CONFIG_V1"),
    "SUPPORTING_OBJECT": ("PostgreSQL schema object or NestJS provider (type-dependent)", "DATA_AND_API", "MANUAL", .50, "APEX_SUPPORTING_OBJECT_TO_TARGET_V1"),
    "SAVED_REPORT": ("Persisted report/query configuration", "DATA_AND_UI", "ASSISTED", .70, "APEX_SAVED_REPORT_TO_REPORT_CONFIG_V1"),
    "REPORT_SORT": ("Server-side query sort configuration", "API_AND_DATA", "ASSISTED", .75, "APEX_REPORT_SORT_TO_QUERY_SORT_V1"),
    "PARAMETER": ("Typed route/query parameter or DTO field", "API_AND_UI", "ASSISTED", .80, "APEX_PARAMETER_TO_DTO_V1"),
    "CHART_SERIES": ("Chart dataset/series configuration", "UI_AND_API", "ASSISTED", .75, "APEX_CHART_SERIES_TO_DATASET_V1"),
    "CHART_AXIS": ("Chart axis configuration", "UI", "ASSISTED", .80, "APEX_CHART_AXIS_TO_CHART_CONFIG_V1"),
}
EXPRESSION_RULES = {
    "SQL": ("PostgreSQL query/repository", "DATA", "ASSISTED", "SQL_TO_POSTGRES_QUERY_V1"),
    "PL_SQL": ("NestJS service/repository transaction logic", "API_AND_DATA", "MANUAL", "PLSQL_TO_NEST_SERVICE_V1"),
    "JAVASCRIPT": ("TypeScript/React handler or utility", "UI_OR_API", "ASSISTED", "JS_TO_TYPESCRIPT_V1"),
    "HTML": ("React JSX component", "UI", "ASSISTED", "HTML_TO_JSX_V1"),
    "CSS": ("CSS module/design token", "UI", "ASSISTED", "CSS_TO_CSS_MODULE_V1"),
    "APEX": ("Explicit route/session/config adapter", "CROSS_CUTTING", "MANUAL", "APEX_SUBSTITUTION_TO_RUNTIME_CONTEXT_V1"),
    "UNKNOWN": (None, "UNKNOWN", "MANUAL", "UNKNOWN_EXPRESSION_REVIEW_V1"),
}

def _diag(code: str, severity: str, message: str, *, object_id: str | None = None,
          locator: dict[str, Any] | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {"code": code, "severity": severity, "category": "SEMANTIC_ANALYSIS", "message": message}
    if object_id is not None: item["objectId"] = object_id
    if locator is not None: item["sourceLocator"] = locator
    if details is not None: item["details"] = details
    return item

def _stable_id(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sem:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

def _walk_properties(properties: dict[str, Any], prefix: str = ""):
    for name in sorted(properties):
        prop = properties[name]
        path = f"{prefix}.{name}" if prefix else name
        if not isinstance(prop, dict): continue
        yield path, prop
        nested = prop.get("value")
        if prop.get("valueType") == "OBJECT" and isinstance(nested, dict):
            yield from _walk_properties(nested, path)

def _classify_component(obj: dict[str, Any]):
    kind = str(obj.get("type") or "UNKNOWN").upper()
    rule = COMPONENT_RULES.get(kind)
    diagnostics = []
    if rule is None:
        diagnostics.append(_diag("SEM001", "WARNING", "No semantic component mapping is registered; preserve and assess manually.",
            object_id=obj.get("id"), locator=obj.get("source"),
            details={"sourceType": obj.get("sourceType"), "componentType": kind}))
        return {"classification": "UNSUPPORTED", "target": None, "targetLayer": "UNKNOWN",
            "confidence": 0.0, "ruleId": "NO_COMPONENT_RULE_V1",
            "reason": "No registered mapping for this canonical component type."}, diagnostics
    target, layer, mode, confidence, rule_id = rule
    if kind == "PLUGIN":
        diagnostics.append(_diag("SEM004", "WARNING", "Plug-in behavior requires a plug-in-specific adapter or replacement assessment.",
            object_id=obj.get("id"), locator=obj.get("source")))
    if kind in {"AUTHENTICATION", "AUTHORIZATION"}:
        diagnostics.append(_diag("SEM005", "WARNING", "Security behavior requires identity, session, and authorization review; equivalence is not assumed.",
            object_id=obj.get("id"), locator=obj.get("source")))
    return {"classification": mode, "target": target, "targetLayer": layer,
        "confidence": confidence, "ruleId": rule_id,
        "reason": "Explicit canonical component mapping; behavior-level parity remains unverified."}, diagnostics

def analyze_semantics(document: dict[str, Any], dependency_graph: dict[str, Any] | None = None) -> dict[str, Any]:
    """Analyze one IR snapshot without mutating it or executing source expressions."""
    graph = dependency_graph if dependency_graph is not None else analyze_dependency_graph(document)
    objects_out, properties_out, diagnostics = [], [], []
    for obj in sorted(document.get("objects", []), key=lambda x: str(x.get("id", ""))):
        object_id = obj.get("id")
        component, component_diags = _classify_component(obj)
        diagnostics.extend(component_diags)
        expressions = []
        for path, prop in _walk_properties(obj.get("properties", {})):
            language = str(prop.get("expressionLanguage") or "UNKNOWN").upper()
            value_type = str(prop.get("valueType") or "UNKNOWN").upper()
            if value_type not in {"SQL_EXPRESSION", "PL_SQL_EXPRESSION", "JAVASCRIPT_EXPRESSION", "UNKNOWN"} and not prop.get("rawExpression"):
                continue
            target, layer, mode, rule_id = EXPRESSION_RULES.get(language, EXPRESSION_RULES["UNKNOWN"])
            confidence = {"HIGH": .90, "MEDIUM": .65, "LOW": .35, "NONE": 0.0}.get(str(prop.get("classificationConfidence", "NONE")).upper(), 0.0)
            if language == "UNKNOWN" or value_type == "UNKNOWN":
                mode = "MANUAL"
                diagnostics.append(_diag("SEM002", "WARNING", "Expression language or semantics are unknown; preserve raw source and require manual review.",
                    object_id=object_id, locator=prop.get("sourceLocator"),
                    details={"propertyPath": path, "valueType": value_type, "expressionLanguage": language}))
            elif language == "PL_SQL":
                diagnostics.append(_diag("SEM003", "WARNING", "PL/SQL requires behavior-aware redesign of transactions, package state, exceptions, and Oracle-specific semantics.",
                    object_id=object_id, locator=prop.get("sourceLocator"),
                    details={"propertyPath": path, "ruleId": rule_id}))
            record = {"id": _stable_id([object_id, path, rule_id]), "objectId": object_id,
                "propertyPath": path, "sourceValueType": value_type, "expressionLanguage": language,
                "classification": mode, "target": target, "targetLayer": layer,
                "confidence": confidence, "ruleId": rule_id,
                "rawSourcePreserved": bool(prop.get("preserved", True)),
                "sourceLocator": prop.get("sourceLocator")}
            expressions.append(record)
            properties_out.append(record)
        objects_out.append({"objectId": object_id, "objectType": obj.get("type", "UNKNOWN"),
            "sourceType": obj.get("sourceType"), "name": obj.get("name"), "component": component,
            "expressionCount": len(expressions), "expressions": expressions, "sourceLocator": obj.get("source")})

    for ref in sorted(document.get("references", []), key=lambda x: str(x.get("id", ""))):
        if ref.get("resolutionStatus") != "RESOLVED":
            diagnostics.append(_diag("SEM006", "WARNING", "Reference is not uniquely resolved; no target binding is proposed.",
                object_id=ref.get("sourceObjectId"), locator=ref.get("sourceLocator"),
                details={"referenceId": ref.get("id"), "resolutionStatus": ref.get("resolutionStatus"),
                         "referenceType": ref.get("referenceType")}))
    for cycle in graph.get("cycles", []):
        diagnostics.append(_diag("SEM007", "ERROR", "Dependency cycle blocks safe transformation ordering.",
            details={"cycleObjectIds": cycle}))
    for blocked_id in graph.get("blockedObjectIds", []):
        diagnostics.append(_diag("SEM008", "ERROR", "Object is blocked from dependency-first transformation ordering.", object_id=blocked_id))

    diagnostics.sort(key=lambda x: (x["code"], str(x.get("objectId") or ""),
        json.dumps(x.get("details", {}), sort_keys=True, ensure_ascii=False)))
    counts = {key: sum(1 for item in objects_out if item["component"]["classification"] == key)
              for key in ("AUTOMATIC", "ASSISTED", "MANUAL", "UNSUPPORTED")}
    return {"semanticVersion": SEMANTIC_VERSION, "rulesetVersion": RULESET_VERSION,
        "schema": "apex2next.semantic-analysis.v1", "applicationId": document.get("application", {}).get("id"),
        "dependencyGraphVersion": graph.get("graphVersion"), "objects": objects_out,
        "propertyTransformations": sorted(properties_out, key=lambda x: (str(x["objectId"]), x["propertyPath"])),
        "diagnostics": diagnostics, "summary": {"objectCount": len(objects_out),
            "propertyTransformationCount": len(properties_out), "classificationCounts": counts,
            "diagnosticCounts": {level: sum(1 for x in diagnostics if x["severity"] == level)
                                 for level in ("INFO", "WARNING", "ERROR")},
            "automaticCount": counts["AUTOMATIC"],
            "requiresReviewCount": counts["ASSISTED"] + counts["MANUAL"] + counts["UNSUPPORTED"]},
        "metadata": {"ordering": "DEPENDENCY_FIRST", "dependencyOrder": graph.get("migrationOrder", []),
            "sourceDocumentMutated": False, "sourceExpressionsExecuted": False, "codeGenerated": False}}
