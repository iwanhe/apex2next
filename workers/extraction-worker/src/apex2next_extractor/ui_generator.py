"""Deterministic, fail-closed UI metadata generation from Normalized IR.

Only reviewed presentation metadata is emitted into the application-facing spec.
Expressions, SQL, PL/SQL, credentials, and arbitrary source properties stay in the
migration report/source IR and are never executed or rendered.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

_PRESENTATION_KEYS = {
    "label", "prompt", "placeholder", "display_as", "displayAs", "item_type",
    "itemType", "region_type", "regionType", "button_position", "buttonPosition",
    "sequence", "required", "is_required", "isRequired", "read_only", "readOnly",
    "is_hidden", "isHidden", "format_mask", "formatMask", "heading",
    "column_heading", "columnHeading", "css_classes", "cssClasses", "page", "page_id", "pageId",
}
_PAGE_CHILD_TYPES = {
    "REGION", "ITEM", "BUTTON", "PROCESS", "VALIDATION", "DYNAMIC_ACTION",
    "DYNAMIC_ACTION_ACTION", "BRANCH", "COLUMN", "DISPLAY_COLUMN",
    "CHART_SERIES", "CHART_AXIS", "LOV", "SAVED_REPORT", "REPORT_SORT",
}
_MANUAL_TYPES = {"PROCESS", "VALIDATION", "DYNAMIC_ACTION", "DYNAMIC_ACTION_ACTION",
                 "BRANCH", "AUTHENTICATION", "AUTHORIZATION", "PLUGIN", "SUPPORTING_OBJECT"}


def _route_id(page: dict[str, Any]) -> str:
    identity = str(page.get("id", "unknown"))
    slug = re.sub(r"[^a-z0-9]+", "-", str(page.get("name") or "").lower()).strip("-")[:48] or "page"
    return f"{slug}-{hashlib.sha256(identity.encode()).hexdigest()[:8]}"


def _safe_properties(properties: Any) -> dict[str, Any]:
    """Copy a small presentation allowlist; never copy expression/source payloads."""
    if not isinstance(properties, dict):
        return {}
    result: dict[str, Any] = {}
    for key, prop in sorted(properties.items()):
        if key not in _PRESENTATION_KEYS or not isinstance(prop, dict):
            continue
        value = prop.get("value")
        if prop.get("valueType") not in {"STRING", "NUMBER", "BOOLEAN", "NULL"}:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            result[key] = value
    return result


def build_ui_spec(document: dict[str, Any]) -> dict[str, Any]:
    """Build a stable page/component registry suitable for generated app code."""
    objects = document.get("objects", [])
    pages = sorted((obj for obj in objects if obj.get("type") == "PAGE"),
                   key=lambda obj: str(obj.get("id", "")))
    page_specs = []
    unassigned = []
    for page in pages:
        page_id = page.get("id")
        children = []
        for obj in sorted(objects, key=lambda item: str(item.get("id", ""))):
            if obj.get("parentId") != page_id or obj.get("type") not in _PAGE_CHILD_TYPES:
                continue
            kind = str(obj.get("type") or "UNKNOWN").upper()
            status = "MANUAL_REVIEW" if kind in _MANUAL_TYPES else "METADATA_ONLY"
            children.append({
                "id": str(obj.get("id", "")),
                "type": kind,
                "sourceType": str(obj.get("sourceType") or ""),
                "name": str(obj.get("name") or obj.get("id") or kind),
                "reviewStatus": status,
                "presentation": _safe_properties(obj.get("properties", {})),
            })
        page_specs.append({
            "id": str(page_id),
            "name": str(page.get("name") or page_id),
            "title": str(page.get("name") or page_id),
            "route": _route_id(page),
            "reviewStatus": "METADATA_ONLY",
            "components": children,
        })
    page_ids = {str(page.get("id")) for page in pages}
    for obj in objects:
        if obj.get("type") in _PAGE_CHILD_TYPES and str(obj.get("parentId")) not in page_ids:
            unassigned.append(str(obj.get("id", "")))
    def registry(types: set[str]) -> list[dict[str, Any]]:
        entries = []
        for obj in sorted(objects, key=lambda item: str(item.get("id", ""))):
            kind = str(obj.get("type") or "UNKNOWN").upper()
            if kind not in types:
                continue
            entries.append({
                "id": str(obj.get("id", "")),
                "type": kind,
                "name": str(obj.get("name") or obj.get("id") or kind),
                "reviewStatus": "MANUAL_REVIEW" if kind in _MANUAL_TYPES or kind == "LOV" else "METADATA_ONLY",
                "presentation": _safe_properties(obj.get("properties", {})),
            })
        return entries

    return {
        "format": "apex2next.generated-ui-spec.v1",
        "application": {
            "id": str(document.get("application", {}).get("id", "")),
            "name": str(document.get("application", {}).get("name") or "Migrated APEX application"),
        },
        "sourceHash": document.get("metadata", {}).get("sourceHash"),
        "pages": page_specs,
        "navigation": registry({"LIST", "LIST_ITEM", "BREADCRUMB"}),
        "lovs": registry({"LOV"}),
        "authorizationSchemes": registry({"AUTHORIZATION"}),
        "unassignedComponentIds": sorted(unassigned),
        "safety": {
            "mode": "METADATA_ONLY",
            "sourceExpressionsIncluded": False,
            "businessBehaviorGenerated": False,
            "authorizationEnabled": False,
            "note": "Generated inventory is descriptive only. Implement and verify behavior before enabling routes.",
        },
    }


def build_ui_generator_files(document: dict[str, Any]) -> dict[str, str]:
    """Return application-facing UI spec, read-only inventory component, and generation report."""
    import json

    spec = build_ui_spec(document)
    encoded = json.dumps(spec, ensure_ascii=False, sort_keys=True, indent=2)
    ts = "// GENERATED by APEX2NEXT R3. Do not edit.\nexport const GENERATED_UI_SPEC = " + encoded + " as const;\n"
    report = {
        "format": spec["format"],
        "pageCount": len(spec["pages"]),
        "componentCount": sum(len(page["components"]) for page in spec["pages"]),
        "manualReviewCount": sum(
            component["reviewStatus"] == "MANUAL_REVIEW"
            for page in spec["pages"] for component in page["components"]
        ),
        "unassignedComponentIds": spec["unassignedComponentIds"],
        "safety": spec["safety"],
    }
    report_definitions = [
        {"pageId": page["id"], "regionId": component["id"], "name": component["name"],
         "kind": component["type"], "queryStatus": "MANUAL_REVIEW", "queryGenerated": False}
        for page in spec["pages"] for component in page["components"]
        if component["type"] == "REGION"
    ]
    form_definitions = [
        {"pageId": page["id"], "itemId": component["id"], "name": component["name"],
         "fieldType": "UNKNOWN", "writeStatus": "MANUAL_REVIEW", "validationGenerated": False}
        for page in spec["pages"] for component in page["components"]
        if component["type"] == "ITEM"
    ]
    reports_ts = "// GENERATED by APEX2NEXT R3. Query behavior requires review.\\nexport const GENERATED_REPORT_DEFINITIONS = " + json.dumps(report_definitions, ensure_ascii=False, sort_keys=True, indent=2) + " as const;\\n"
    forms_ts = "// GENERATED by APEX2NEXT R3. Form writes and validations require review.\\nexport const GENERATED_FORM_DEFINITIONS = " + json.dumps(form_definitions, ensure_ascii=False, sort_keys=True, indent=2) + " as const;\\n"
    files = {
        "apps/web/lib/apex2next-generated-spec.ts": ts,
        "apps/api/src/generated/apex2next-generated-spec.ts": ts,
        "apps/api/src/generated/report-definitions.ts": reports_ts,
        "apps/api/src/generated/form-definitions.ts": forms_ts,
        "apps/web/components/GeneratedPageInventory.tsx": """import type { GENERATED_UI_SPEC } from '../lib/apex2next-generated-spec';

type GeneratedPage = (typeof GENERATED_UI_SPEC.pages)[number];

export function GeneratedPageInventory({ page }: { page: GeneratedPage }) {
  return (
    <section aria-label="Migrated APEX component inventory">
      <p className="muted">Source page: <code>{page.id}</code> · Metadata-only scaffold</p>
      {page.components.length === 0 ? <p>No components were extracted for this page.</p> : (
        <ul>
          {page.components.map((component) => (
            <li key={component.id}>
              <strong>{component.name}</strong> <code>{component.type}</code>
              {component.reviewStatus === 'MANUAL_REVIEW' ? (
                <span> — manual review required</span>
              ) : <span> — metadata captured; behavior not migrated</span>}
            </li>
          ))}
        </ul>
      )}
      <p className="muted">No source SQL, PL/SQL, dynamic code, or authorization rule is executed by this page.</p>
    </section>
  );
}
""",
        "migration-report/ui-generation.json": json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    }
    for page in spec["pages"]:
        route_file = f"apps/web/app/pages/{page['route']}/page.tsx"
        title = page["title"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        page_id = page["id"].replace("\\", "\\\\").replace("'", "\\'")
        files[route_file] = f"""import {{ GeneratedPageInventory }} from '../../../components/GeneratedPageInventory';
import {{ GENERATED_UI_SPEC }} from '../../../lib/apex2next-generated-spec';

const page = GENERATED_UI_SPEC.pages.find((entry) => entry.id === '{page_id}');

export default function Page() {{
  if (!page) return <main className="container"><h1>Page metadata unavailable</h1></main>;
  return <main className="container">
    <h1>{title}</h1>
    <GeneratedPageInventory page={{page}} />
  </main>;
}}
"""
    return files
