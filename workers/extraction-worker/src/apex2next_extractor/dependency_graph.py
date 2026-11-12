"""Deterministic dependency graph analysis for Normalized IR v1."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any

GRAPH_VERSION = "0.1.0"


def _stable_id(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "dep:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _diagnostic(code: str, severity: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "severity": severity, "category": "DEPENDENCY_GRAPH",
            "message": message, **({"details": details} if details else {})}


def analyze_dependency_graph(document: dict[str, Any]) -> dict[str, Any]:
    """Analyze explicit resolved dependencies; never infer edges from names or source text.

    Edges point from dependent/source to prerequisite/target. migrationOrder is
    therefore dependency-first. A cycle blocks its members and downstream dependents.
    """
    objects = document.get("objects", [])
    counts: dict[str, int] = defaultdict(int)
    by_id: dict[str, dict[str, Any]] = {}
    for obj in objects:
        if obj.get("id"):
            counts[obj["id"]] += 1
            by_id[obj["id"]] = obj
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    valid = set(by_id) - set(duplicates)
    diagnostics = [
        _diagnostic("DEP001", "ERROR", "Duplicate object identity prevents safe graph construction.",
                    objectId=key, occurrences=counts[key]) for key in duplicates
    ]

    edge_map: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    def add_edge(source: Any, target: Any, kind: str, origin: str,
                 confidence: Any = None, rule_id: Any = None, locator: Any = None,
                 edge_id: Any = None) -> None:
        if source not in valid or target not in valid:
            diagnostics.append(_diagnostic(
                "DEP002", "ERROR",
                "Dependency endpoint is missing, duplicated, or outside this IR snapshot.",
                dependencyId=edge_id, sourceObjectId=source, targetObjectId=target,
                dependencyType=kind,
            ))
            return
        key = (source, target, kind, origin)
        if key not in edge_map:
            edge_map[key] = {
                "id": edge_id or _stable_id(key), "sourceObjectId": source,
                "targetObjectId": target, "dependencyType": kind, "origin": origin,
                "confidence": confidence, "ruleId": rule_id,
                **({"sourceLocator": locator} if locator is not None else {}),
            }
        elif locator is not None:
            edge = edge_map[key]
            locators = edge.setdefault("sourceLocators", [])
            candidates = locators + ([edge["sourceLocator"]] if edge.get("sourceLocator") else []) + [locator]
            edge.pop("sourceLocator", None)
            edge["sourceLocators"] = sorted(
                {json.dumps(x, sort_keys=True, ensure_ascii=False): x for x in candidates}.values(),
                key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False),
            )

    for dep in document.get("dependencies", []):
        add_edge(dep.get("sourceObjectId"), dep.get("targetObjectId"),
                 str(dep.get("dependencyType") or "UNKNOWN"),
                 str(dep.get("origin") or "UNKNOWN"), dep.get("confidence"),
                 dep.get("ruleId"), dep.get("sourceLocator"), dep.get("id"))

    for ref in document.get("references", []):
        status = ref.get("resolutionStatus", "PENDING")
        if status != "RESOLVED":
            severity = "WARNING" if status in {"PENDING", "UNSUPPORTED"} else "ERROR"
            diagnostics.append(_diagnostic(
                "DEP003", severity,
                "Unresolved reference is excluded from migration-order edges.",
                referenceId=ref.get("id"), sourceObjectId=ref.get("sourceObjectId"),
                referenceValue=ref.get("referenceValue"), resolutionStatus=status,
            ))
            continue
        add_edge(ref.get("sourceObjectId"), ref.get("targetObjectId"),
                 str(ref.get("referenceType") or "REFERENCE"), "EXPLICIT",
                 1.0, "RESOLVED_REFERENCE_V1", ref.get("sourceLocator"), ref.get("id"))

    edges = [edge_map[key] for key in sorted(edge_map)]
    adjacency = {node: set() for node in sorted(valid)}
    reverse = {node: set() for node in sorted(valid)}
    indegree = {node: 0 for node in valid}
    for edge in edges:
        source, target = edge["sourceObjectId"], edge["targetObjectId"]
        if target not in adjacency[source]:
            adjacency[source].add(target)
            reverse[target].add(source)
            indegree[source] += 1

    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for dependent in sorted(reverse[node]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
                ready.sort()

    blocked = sorted(valid - set(order))
    cycles: list[list[str]] = []
    if blocked:
        # Tarjan SCC distinguishes actual cycle members from nodes merely blocked by them.
        index = 0
        indices: dict[str, int] = {}
        low: dict[str, int] = {}
        stack: list[str] = []
        on_stack: set[str] = set()

        def visit(node: str) -> None:
            nonlocal index
            indices[node] = low[node] = index
            index += 1
            stack.append(node)
            on_stack.add(node)
            for neighbor in sorted(adjacency[node]):
                if neighbor not in blocked:
                    continue
                if neighbor not in indices:
                    visit(neighbor)
                    low[node] = min(low[node], low[neighbor])
                elif neighbor in on_stack:
                    low[node] = min(low[node], indices[neighbor])
            if low[node] == indices[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.remove(member)
                    component.append(member)
                    if member == node:
                        break
                component.sort()
                if len(component) > 1 or node in adjacency[node]:
                    cycles.append(component)

        for node in blocked:
            if node not in indices:
                visit(node)
        cycles.sort()
        for cycle in cycles:
            diagnostics.append(_diagnostic(
                "DEP005", "ERROR", "Circular dependency prevents a complete migration order.",
                cycleObjectIds=cycle,
            ))
        cycle_members = {node for cycle in cycles for node in cycle}
        downstream = sorted(set(blocked) - cycle_members)
        if downstream:
            diagnostics.append(_diagnostic(
                "DEP006", "ERROR", "Objects are blocked by one or more dependency cycles.",
                blockedObjectIds=downstream,
            ))

    impact = []
    for node in sorted(valid):
        visited: set[str] = set()
        pending = list(sorted(reverse[node]))
        while pending:
            candidate = pending.pop(0)
            if candidate in visited:
                continue
            visited.add(candidate)
            pending.extend(sorted(reverse[candidate] - visited))
        obj = by_id[node]
        impact.append({
            "objectId": node, "objectType": obj.get("type", "UNKNOWN"),
            "directDependentCount": len(reverse[node]),
            "transitiveDependentCount": len(visited),
            "transitiveDependentObjectIds": sorted(visited),
        })

    nodes = [{
        "objectId": node, "objectType": by_id[node].get("type", "UNKNOWN"),
        "name": by_id[node].get("name"), "sourceLocator": by_id[node].get("source"),
    } for node in sorted(valid)]
    return {
        "graphVersion": GRAPH_VERSION, "schema": "apex2next.dependency-graph.v1",
        "applicationId": document.get("application", {}).get("id"),
        "nodes": nodes, "edges": edges, "cycles": cycles,
        "migrationOrder": order, "blockedObjectIds": blocked,
        "impact": impact,
        "diagnostics": sorted(diagnostics, key=lambda item: (
            item["code"], json.dumps(item.get("details", {}), sort_keys=True, ensure_ascii=False),
            item["message"],
        )),
        "metadata": {
            "nodeCount": len(nodes), "edgeCount": len(edges), "cycleCount": len(cycles),
            "orderedNodeCount": len(order), "blockedNodeCount": len(blocked),
            "ordering": "DEPENDENCY_FIRST", "edgeDirection": "SOURCE_DEPENDS_ON_TARGET",
        },
    }
