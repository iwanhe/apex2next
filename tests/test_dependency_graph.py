from __future__ import annotations

from apex2next_extractor.dependency_graph import analyze_dependency_graph


def _document(edges: list[tuple[str, str]], *, references: list[dict] | None = None) -> dict:
    nodes = ["A", "B", "C", "D"]
    return {
        "application": {"id": "app:1"},
        "objects": [{"id": node, "type": "PAGE", "name": node} for node in nodes],
        "dependencies": [
            {"id": f"dep:{source}:{target}", "sourceObjectId": source,
             "targetObjectId": target, "dependencyType": "USES",
             "origin": "EXPLICIT", "confidence": 1.0}
            for source, target in edges
        ],
        "references": references or [],
    }


def test_graph_order_is_dependency_first_and_deterministic() -> None:
    document = _document([("A", "B"), ("B", "C")])
    first = analyze_dependency_graph(document)
    second = analyze_dependency_graph(document)

    assert first == second
    assert first["migrationOrder"].index("C") < first["migrationOrder"].index("B")
    assert first["migrationOrder"].index("B") < first["migrationOrder"].index("A")
    assert first["metadata"]["edgeDirection"] == "SOURCE_DEPENDS_ON_TARGET"
    assert first["blockedObjectIds"] == []


def test_impact_analysis_returns_transitive_dependents() -> None:
    graph = analyze_dependency_graph(_document([("A", "B"), ("B", "C"), ("D", "C")]))
    impact = {item["objectId"]: item for item in graph["impact"]}

    assert impact["C"]["directDependentCount"] == 2
    assert impact["C"]["transitiveDependentObjectIds"] == ["A", "B", "D"]
    assert impact["C"]["transitiveDependentCount"] == 3


def test_cycles_and_downstream_blocking_are_reported_separately() -> None:
    graph = analyze_dependency_graph(_document([("A", "B"), ("B", "A"), ("C", "A")]))
    assert graph["cycles"] == [["A", "B"]]
    assert graph["blockedObjectIds"] == ["A", "B", "C"]
    cycle_diag = next(item for item in graph["diagnostics"] if item["code"] == "DEP005")
    blocked_diag = next(item for item in graph["diagnostics"] if item["code"] == "DEP006")
    assert cycle_diag["details"]["cycleObjectIds"] == ["A", "B"]
    assert blocked_diag["details"]["blockedObjectIds"] == ["C"]
    assert "D" in graph["migrationOrder"]


def test_unresolved_references_are_diagnostics_not_graph_edges() -> None:
    reference = {
        "id": "ref:1", "sourceObjectId": "A", "referenceType": "APEXLANG_AT_REFERENCE",
        "referenceValue": "missing", "resolutionStatus": "DANGLING",
    }
    graph = analyze_dependency_graph(_document([], references=[reference]))
    assert graph["edges"] == []
    diagnostic = next(item for item in graph["diagnostics"] if item["code"] == "DEP003")
    assert diagnostic["severity"] == "ERROR"
    assert graph["migrationOrder"] == ["A", "B", "C", "D"]


def test_resolved_reference_becomes_explicit_dependency_edge() -> None:
    reference = {
        "id": "ref:1", "sourceObjectId": "A", "targetObjectId": "C",
        "referenceType": "APEXLANG_AT_REFERENCE", "referenceValue": "C",
        "resolutionStatus": "RESOLVED",
    }
    graph = analyze_dependency_graph(_document([], references=[reference]))
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["sourceObjectId"] == "A"
    assert graph["edges"][0]["targetObjectId"] == "C"
    assert graph["edges"][0]["origin"] == "EXPLICIT"
    assert graph["migrationOrder"].index("C") < graph["migrationOrder"].index("A")


def test_invalid_endpoints_and_duplicate_object_ids_are_not_silently_used() -> None:
    document = _document([("A", "missing")])
    document["objects"].append({"id": "A", "type": "REGION"})
    graph = analyze_dependency_graph(document)
    codes = {item["code"] for item in graph["diagnostics"]}
    assert "DEP001" in codes
    assert "DEP002" in codes
    assert "A" not in {item["objectId"] for item in graph["nodes"]}
