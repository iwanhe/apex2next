"""Deterministic identity, provenance, and source adapters for Normalized IR v1.

All source text is treated as data. This module never executes SQL, PL/SQL, or APEXLang.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .apex_export import extract_export
from .apexlang import _mask_non_code, extract_apexlang

ADAPTER_VERSION = "0.1.0"
IR_VERSION = "1.0.0"
REFERENCE_RE = re.compile(r"(?<![A-Za-z0-9_])@([A-Za-z0-9_./-]+)")


def canonical_json(value: Any) -> str:
    """Serialize JSON-compatible values deterministically."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_identity(
    source_format: str,
    object_type: str,
    source_native_id: Any = None,
    *,
    parent_id: str | None = None,
    name: str | None = None,
    fallback: str | None = None,
) -> str:
    """Build a content-independent ID; fallback identities are explicitly weaker."""
    if source_native_id not in (None, ""):
        key = {"nativeId": str(source_native_id), "parentId": parent_id}
    elif name:
        key = {"name": name, "parentId": parent_id}
    else:
        key = {"fallback": fallback or "unknown"}
    payload = {"sourceFormat": source_format, "type": object_type, **key}
    return "obj:" + hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()[:24]


def object_fingerprint(
    object_type: str, source_type: str, name: str | None, properties: dict[str, Any]
) -> str:
    """Fingerprint semantic source content, excluding locator and generated metadata."""
    payload = {
        "type": object_type,
        "sourceType": source_type,
        "name": name,
        "properties": properties,
    }
    return "sha256:" + sha256_text(canonical_json(payload))


def _value_type(value: Any, raw: str | None = None) -> str:
    if isinstance(value, bool):
        return "BOOLEAN"
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return "NUMBER"
    if isinstance(value, list):
        return "ARRAY"
    if isinstance(value, dict):
        return "UNKNOWN" if "expression" in value else "OBJECT"
    if raw is not None and value == raw.strip() and not (
        (raw.strip().startswith("'") and raw.strip().endswith("'"))
        or raw.strip().lower() in {"true", "false"}
        or re.fullmatch(r"-?\d+(?:\.\d+)?", raw.strip())
    ):
        return "UNKNOWN"
    return "STRING"


def _property(value: Any, raw: str | None = None, locator: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"valueType": _value_type(value, raw), "preserved": True}
    if isinstance(value, dict) and "expression" in value:
        result["valueType"] = "UNKNOWN"
        result["rawExpression"] = str(value["expression"])
    elif raw is not None and _value_type(value, raw) == "UNKNOWN":
        result["rawExpression"] = raw
    else:
        result["value"] = value
    if locator is not None:
        result["sourceLocator"] = locator
    return result


def _diagnostic(code: str, severity: str, category: str, message: str,
                *, locator: dict[str, Any] | None = None,
                object_id: str | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "code": code, "severity": severity, "category": category, "message": message
    }
    if locator is not None:
        item["sourceLocator"] = locator
    if object_id is not None:
        item["objectId"] = object_id
    if details is not None:
        item["details"] = details
    return item


def _document(source_format: str, application: dict[str, Any], objects: list[dict[str, Any]],
              relationships: list[dict[str, Any]], references: list[dict[str, Any]],
              diagnostics: list[dict[str, Any]], artifact_hashes: list[str]) -> dict[str, Any]:
    hashes = sorted(set(artifact_hashes))
    source_hash = "sha256:" + sha256_text(canonical_json(hashes))
    document = {
        "irVersion": IR_VERSION,
        "application": application,
        "objects": objects,
        "relationships": relationships,
        "references": references,
        "dependencies": [],
        "diagnostics": sorted(
            diagnostics,
            key=lambda d: (
                d.get("sourceLocator", {}).get("file", ""),
                d.get("sourceLocator", {}).get("line") or 0,
                d["code"], d["message"],
            ),
        ),
        "metadata": {
            "sourceHash": source_hash,
            "adapterVersion": ADAPTER_VERSION,
            "schemaDialect": "https://json-schema.org/draft/2020-12/schema",
            "sourceArtifactHashes": hashes,
        },
    }
    return document


def adapt_apexlang_directory(source_dir: str | Path) -> dict[str, Any]:
    """Convert the static APEXLang inventory into a schema-valid structural IR."""
    root = Path(source_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"APEXLang source directory does not exist: {source_dir}")
    inventory = extract_apexlang(root)
    declarations = inventory["declarations"]
    artifact_bytes: dict[str, bytes] = {}
    for path in sorted(root.rglob("*.apx")):
        if path.is_symlink():
            continue
        resolved = path.resolve()
        if root not in resolved.parents and resolved != root:
            raise ValueError(f"Source path escapes selected root: {path}")
        artifact_bytes[path.relative_to(root).as_posix()] = path.read_bytes()
    version_path = root / ".apex" / "apexlang.json"
    if version_path.is_file() and not version_path.is_symlink():
        artifact_bytes[".apex/apexlang.json"] = version_path.read_bytes()

    hashes = {name: sha256_bytes(data) for name, data in artifact_bytes.items()}
    app_decl = next((d for d in declarations if d["object_type"] == "APPLICATION"), None)
    app_native_id = (app_decl or {}).get("name") or "application"
    app_id = stable_identity("APEXLANG", "APPLICATION", app_native_id)
    app_name = (app_decl or {}).get("properties", {}).get("name")
    application = {
        "id": app_id,
        "name": app_name,
        "sourceFormat": "APEXLANG",
        "sourceVersion": {
            "metadataVersion": inventory.get("apexlang_mmd_version"),
            "runtimeVersion": None,
        },
    }

    objects: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    stack: list[tuple[int, str]] = []
    occurrence: dict[tuple[str, str, str], int] = {}

    for declaration in declarations:
        file_name = declaration.get("file", "")
        line = declaration.get("line")
        column = declaration.get("column")
        indent = declaration.get("indent", 0)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent_id = stack[-1][1] if stack else app_id
        object_type = declaration.get("object_type", "UNKNOWN")
        source_type = declaration.get("kind", object_type)
        name = declaration.get("name") or None
        native_id = declaration.get("source_native_id") or name
        group_key = (object_type, parent_id, str(native_id or ""))
        occurrence[group_key] = occurrence.get(group_key, 0) + 1
        fallback = f"{file_name}:{line}:{occurrence[group_key]}"
        identity_parent_id = None if object_type == "APPLICATION" else parent_id
        object_id = stable_identity(
            "APEXLANG", object_type, native_id,
            parent_id=identity_parent_id, name=name, fallback=fallback
        )
        artifact_hash = hashes.get(file_name)
        locator = {
            "file": file_name or None, "line": line, "column": column or 1,
            "artifactHash": "sha256:" + artifact_hash if artifact_hash else None,
            "sourceNativeId": native_id,
        }
        properties = {
            key: _property(value)
            for key, value in sorted(declaration.get("properties", {}).items())
        }
        raw_body = declaration.get("raw_body")
        extensions: dict[str, Any] = {"sourceIndent": indent}
        if raw_body is not None:
            extensions["rawDeclarationBody"] = raw_body
        if not native_id:
            diagnostics.append(_diagnostic(
                "SRC001", "WARNING", "PROVENANCE",
                "Object has no source-native identifier; fallback identity uses its source locator.",
                locator=locator, object_id=object_id,
            ))
        effective_parent_id = None if object_type == "APPLICATION" else parent_id
        obj = {
            "id": object_id, "type": object_type, "sourceType": source_type,
            "name": name, "parentId": effective_parent_id, "properties": properties,
            "source": locator, "fingerprint": object_fingerprint(
                object_type, source_type, name, properties
            ),
            "status": {"parse": "SUCCESS", "resolve": "PENDING", "conversion": "PENDING"},
            "extensions": extensions,
        }
        objects.append(obj)
        if object_type == "UNKNOWN":
            diagnostics.append(_diagnostic(
                "IR002", "WARNING", "UNSUPPORTED_SOURCE_OBJECT",
                f"Unmapped APEXLang declaration preserved as UNKNOWN: {source_type}",
                locator=locator, object_id=object_id,
                details={"sourceType": source_type, "rawDeclarationBody": raw_body},
            ))
        if effective_parent_id:
            relationships.append({
                "id": "rel:" + sha256_text(f"{parent_id}|{object_id}|CONTAINS")[:24],
                "sourceObjectId": parent_id, "targetObjectId": object_id,
                "relationshipType": "CONTAINS", "sourceLocator": locator,
            })
        if object_type != "APPLICATION":
            stack.append((indent, object_id))
        for reference_value in sorted(set(REFERENCE_RE.findall(_mask_non_code(raw_body or "")))):
            reference_id = "ref:" + sha256_text(f"{object_id}|{reference_value}")[:24]
            references.append({
                "id": reference_id, "sourceObjectId": object_id,
                "referenceType": "APEXLANG_AT_REFERENCE",
                "referenceValue": reference_value, "targetObjectId": None,
                "resolutionStatus": "PENDING", "scope": app_id,
                "sourceLocator": locator, "candidateObjectIds": [],
            })

    if not declarations:
        diagnostics.append(_diagnostic(
            "SRC003", "WARNING", "EXTRACTION",
            "No supported APEXLang declarations were found; the source may use unsupported syntax.",
        ))
    if inventory.get("apexlang_mmd_version"):
        diagnostics.append(_diagnostic(
            "SRC002", "INFO", "SOURCE_VERSION",
            "APEXLang metadata version was found; Oracle APEX runtime version remains unverified.",
            details={"metadataVersion": inventory["apexlang_mmd_version"], "runtimeVersion": None},
        ))
    for item in inventory.get("diagnostics", []):
        diagnostics.append(_diagnostic(
            item.get("code", "APEXLANG000"), item.get("severity", "WARNING"),
            "SOURCE_PARSER", item.get("message", "APEXLang parser diagnostic"),
            locator={"file": item.get("file"), "line": item.get("line"), "column": None},
        ))
    return _document(
        "APEXLANG", application, objects, relationships, references, diagnostics,
        list(hashes.values()),
    )


def adapt_apex_export(source_text: str, source_name: str = "<memory>") -> dict[str, Any]:
    """Convert supported static APEX import API calls into Normalized IR."""
    artifact_hash = sha256_text(source_text)
    parsed = extract_export(source_text)
    calls = parsed.get("calls", [])
    flow_call = next((c for c in calls if c.get("object_type") == "APPLICATION"), None)
    flow_args = (flow_call or {}).get("arguments", {})
    app_native_id = flow_args.get("p_id") or source_name
    app_id = stable_identity("APEX_SQL_EXPORT", "APPLICATION", app_native_id)
    app_name = flow_args.get("p_name")
    application = {
        "id": app_id, "name": app_name, "sourceFormat": "APEX_SQL_EXPORT",
        "sourceVersion": {"metadataVersion": None, "runtimeVersion": None},
    }
    objects: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    occurrence: dict[tuple[str, str], int] = {}
    for call in calls:
        object_type = call.get("object_type", "OTHER")
        canonical_type = object_type if object_type in {
            "APPLICATION", "PAGE", "REGION", "ITEM", "BUTTON", "BRANCH",
            "VALIDATION", "PROCESS", "DYNAMIC_ACTION", "DYNAMIC_ACTION_ACTION",
            "LIST", "LIST_ITEM", "LOV", "AUTHENTICATION", "AUTHORIZATION",
            "THEME", "PLUGIN",
        } else "UNKNOWN"
        args = call.get("arguments", {})
        raw_args = call.get("raw_arguments", {})
        native_id = args.get("p_id") or args.get("p_plug_id") or args.get("p_button_id")
        name = next((args.get(key) for key in (
            "p_name", "p_plug_name", "p_item_name", "p_button_name", "p_process_name"
        ) if args.get(key) is not None), None)
        group_key = (canonical_type, str(native_id or name or ""))
        occurrence[group_key] = occurrence.get(group_key, 0) + 1
        fallback = f"{source_name}:{call.get('line')}:{occurrence[group_key]}"
        identity_parent_id = None if canonical_type == "APPLICATION" else app_id
        object_id = stable_identity(
            "APEX_SQL_EXPORT", canonical_type, native_id,
            parent_id=identity_parent_id, name=str(name) if name is not None else None,
            fallback=fallback,
        )
        locator = {
            "file": source_name, "line": call.get("line"), "column": call.get("column"),
            "artifactHash": "sha256:" + artifact_hash,
            "sourceNativeId": native_id, "apiRoutine": call.get("routine"),
        }
        properties: dict[str, Any] = {}
        for key, value in sorted(args.items()):
            raw = raw_args.get(key)
            if isinstance(value, dict) and "expression" in value:
                prop = {"valueType": "UNKNOWN", "rawExpression": value["expression"], "preserved": True}
            else:
                prop = _property(value, raw)
            properties[key] = prop
        obj = {
            "id": object_id, "type": canonical_type, "sourceType": call.get("routine", "unknown"),
            "name": str(name) if name is not None else None,
            "parentId": None if canonical_type == "APPLICATION" else app_id,
            "properties": properties, "source": locator,
            "fingerprint": object_fingerprint(
                canonical_type, call.get("routine", "unknown"),
                str(name) if name is not None else None, properties,
            ),
            "status": {"parse": "SUCCESS", "resolve": "PENDING", "conversion": "PENDING"},
            "extensions": {"rawArguments": raw_args},
        }
        objects.append(obj)
        if canonical_type == "UNKNOWN":
            diagnostics.append(_diagnostic(
                "IR002", "WARNING", "UNSUPPORTED_SOURCE_OBJECT",
                f"Unmapped APEX import API routine preserved as UNKNOWN: {call.get('routine')}",
                locator=locator, object_id=object_id,
                details={"routine": call.get("routine"), "rawArguments": raw_args},
            ))
    for item in parsed.get("diagnostics", []):
        diagnostics.append(_diagnostic(
            item.get("code", "APEXEXP000"), item.get("severity", "WARNING"),
            "SOURCE_PARSER", item.get("message", "APEX export parser diagnostic"),
            locator={"file": source_name, "line": item.get("line"), "column": None,
                     "artifactHash": "sha256:" + artifact_hash},
        ))
    if not calls:
        diagnostics.append(_diagnostic(
            "SRC003", "WARNING", "EXTRACTION",
            "No supported APEX import API calls were found in the supplied export text.",
            locator={"file": source_name, "artifactHash": "sha256:" + artifact_hash},
        ))
    return _document(
        "APEX_SQL_EXPORT", application, objects, [], [], diagnostics, [artifact_hash]
    )



def resolve_references(document: dict[str, Any]) -> dict[str, Any]:
    """Resolve exact source-native references without guessing; return a new IR document."""
    import copy

    resolved_document = copy.deepcopy(document)
    objects = resolved_document.get("objects", [])
    references = resolved_document.get("references", [])
    object_by_id = {obj.get("id"): obj for obj in objects if obj.get("id")}
    application_id = resolved_document.get("application", {}).get("id")

    def in_scope(candidate: dict[str, Any], scope: str | None) -> bool:
        if not scope:
            return True
        current = candidate
        visited: set[str] = set()
        while current:
            current_id = current.get("id")
            if current_id == scope or current.get("parentId") == scope:
                return True
            if not current_id or current_id in visited:
                return False
            visited.add(current_id)
            current = object_by_id.get(current.get("parentId"))
        return False

    by_native_id: dict[str, list[dict[str, Any]]] = {}
    for obj in objects:
        native_id = obj.get("source", {}).get("sourceNativeId")
        if native_id not in (None, ""):
            by_native_id.setdefault(str(native_id), []).append(obj)

    resolver_codes = {"REF001", "REF002", "REF003", "REF004"}
    diagnostics = [
        item for item in resolved_document.get("diagnostics", [])
        if item.get("code") not in resolver_codes
    ]
    dependencies = [
        item for item in resolved_document.get("dependencies", [])
        if not (
            item.get("origin") == "EXPLICIT"
            and item.get("dependencyType") == "APEXLANG_AT_REFERENCE"
        )
    ]
    resolution_by_source: dict[str, list[str]] = {}

    for reference in references:
        source_id = reference.get("sourceObjectId")
        reference_value = reference.get("referenceValue", "")
        reference_type = reference.get("referenceType", "")
        scope = reference.get("scope") or application_id
        status = "PENDING"
        target_id: str | None = None
        candidates: list[dict[str, Any]] = []

        if source_id not in object_by_id or not reference_value:
            status = "INVALID"
            diagnostics.append(_diagnostic(
                "REF004", "ERROR", "REFERENCE_INVALID",
                "Reference has a missing source object or empty reference value.",
                locator=reference.get("sourceLocator"), details={"referenceId": reference.get("id")},
            ))
        elif reference_type != "APEXLANG_AT_REFERENCE":
            status = "UNSUPPORTED"
            diagnostics.append(_diagnostic(
                "REF003", "WARNING", "REFERENCE_UNSUPPORTED",
                f"Reference syntax is not supported by this resolver: {reference_type}",
                locator=reference.get("sourceLocator"), details={"referenceId": reference.get("id")},
            ))
        elif scope and scope != application_id:
            status = "INVALID"
            diagnostics.append(_diagnostic(
                "REF004", "ERROR", "REFERENCE_INVALID",
                "Reference scope does not match the current application snapshot.",
                locator=reference.get("sourceLocator"),
                details={"referenceId": reference.get("id"), "scope": scope},
            ))
        else:
            candidates = [
                candidate for candidate in by_native_id.get(str(reference_value), [])
                if in_scope(candidate, scope)
            ]
            candidate_ids = sorted({candidate["id"] for candidate in candidates})
            if len(candidates) == 1:
                status = "RESOLVED"
                target_id = candidates[0]["id"]
                dependency_id = "dep:" + sha256_text(
                    f"{source_id}|{target_id}|{reference_type}|EXPLICIT"
                )[:24]
                dependencies.append({
                    "id": dependency_id,
                    "sourceObjectId": source_id,
                    "targetObjectId": target_id,
                    "dependencyType": reference_type,
                    "origin": "EXPLICIT",
                    "confidence": 1.0,
                    "sourceLocator": reference.get("sourceLocator"),
                })
            elif len(candidates) == 0:
                status = "DANGLING"
                diagnostics.append(_diagnostic(
                    "REF001", "ERROR", "REFERENCE_DANGLING",
                    f"No in-scope object matches reference: {reference_value}",
                    locator=reference.get("sourceLocator"),
                    details={"referenceId": reference.get("id"), "scope": scope},
                ))
            else:
                status = "AMBIGUOUS"
                diagnostics.append(_diagnostic(
                    "REF002", "ERROR", "REFERENCE_AMBIGUOUS",
                    f"Multiple in-scope objects match reference: {reference_value}",
                    locator=reference.get("sourceLocator"),
                    details={"referenceId": reference.get("id"), "candidateObjectIds": candidate_ids},
                ))

        reference["resolutionStatus"] = status
        reference["targetObjectId"] = target_id
        reference["candidateObjectIds"] = sorted({candidate["id"] for candidate in candidates})
        if source_id:
            resolution_by_source.setdefault(source_id, []).append(status)

    for obj in objects:
        statuses = resolution_by_source.get(obj.get("id"), [])
        if not statuses:
            obj.setdefault("status", {})["resolve"] = "SUCCESS"
        else:
            if all(status == "RESOLVED" for status in statuses):
                obj.setdefault("status", {})["resolve"] = "SUCCESS"
            elif any(status == "INVALID" for status in statuses):
                obj.setdefault("status", {})["resolve"] = "FAILED"
            else:
                obj.setdefault("status", {})["resolve"] = "PARTIAL"

    unique_dependencies = {item["id"]: item for item in dependencies}
    resolved_document["dependencies"] = [
        unique_dependencies[key] for key in sorted(unique_dependencies)
    ]
    resolved_document["diagnostics"] = sorted(
        diagnostics,
        key=lambda d: (
            d.get("sourceLocator", {}).get("file", ""),
            d.get("sourceLocator", {}).get("line") or 0,
            d["code"], d["message"],
        ),
    )
    resolved_document.setdefault("metadata", {})["resolverVersion"] = "0.1.0"
    return resolved_document
