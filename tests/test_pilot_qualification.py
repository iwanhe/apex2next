from copy import deepcopy
import pytest
from apex2next_schema_analyzer.pilot_qualification import INPUT_VERSION, assess_pilot

def fixture():
    ids=[f"WP9-{i:03d}" for i in range(1,13)]
    return {"manifestVersion":INPUT_VERSION,"project":{"id":"orders-pilot","name":"Synthetic Orders"},
      "source":{"format":"APEX_SQL_EXPORT","sanitized":True,"applicationId":"100","apexRuntimeVersion":"24.2","snapshotId":"fixture:scn-123",
      "artifacts":[{"path":"f100.sql","sizeBytes":1024,"sha256":"sha256:"+"a"*64}]},
      "gates":{i:{"status":"PASS","evidenceRef":"fixture:"+i} for i in ids},
      "acceptance":{"maxCriticalDefects":0,"maxHighDefects":0,"rtoMinutes":60,"rpoMinutes":15}}

def test_all_pass_is_qualified_and_deterministic():
    m=fixture(); original=deepcopy(m); r=assess_pilot(m)
    assert r==assess_pilot(m) and m==original
    assert r["status"]=="QUALIFIED" and r["productionQualification"]["eligible"]

def test_missing_gate_is_incomplete():
    m=fixture(); del m["gates"]["WP9-008"]
    r=assess_pilot(m)
    assert r["status"]=="INCOMPLETE"
    assert next(x for x in r["checks"] if x["id"]=="WP9-008")["status"]=="NOT_VERIFIED"

def test_warn_is_conditional_and_fail_is_blocked():
    m=fixture(); m["gates"]["WP9-010"]["status"]="WARN"
    assert assess_pilot(m)["status"]=="CONDITIONAL"
    m["gates"]["WP9-010"]["status"]="FAIL"
    assert assess_pilot(m)["status"]=="BLOCKED"

def test_pass_requires_evidence():
    m=fixture(); del m["gates"]["WP9-003"]["evidenceRef"]
    assert assess_pilot(m)["status"]=="INCOMPLETE"

@pytest.mark.parametrize("change",[
 lambda m:m["source"].update(sanitized=False),
 lambda m:m["source"].update(format="UNKNOWN"),
 lambda m:m["source"]["artifacts"][0].update(path="../secret.env"),
 lambda m:m["source"]["artifacts"][0].update(sha256="bad"),
 lambda m:m["source"]["artifacts"][0].update(sizeBytes=True),
 lambda m:m["acceptance"].update(maxCriticalDefects=1),
 lambda m:m["acceptance"].update(maxHighDefects=True),
 lambda m:m["acceptance"].update(rtoMinutes=-1),
])
def test_invalid_source_or_acceptance_blocks_or_incompletes(change):
    m=fixture(); change(m)
    assert assess_pilot(m)["status"] in {"BLOCKED","INCOMPLETE"}

def test_runtime_version_is_required():
    m=fixture(); m["source"]["apexRuntimeVersion"]=""
    assert assess_pilot(m)["status"]=="INCOMPLETE"

def test_duplicate_artifact_paths_fail():
    m=fixture(); m["source"]["artifacts"].append(dict(m["source"]["artifacts"][0]))
    assert assess_pilot(m)["status"]=="BLOCKED"

def test_invalid_manifest_and_project_rejected():
    m=fixture(); m["manifestVersion"]="unknown"
    with pytest.raises(ValueError,match="manifestVersion"): assess_pilot(m)
    m=fixture(); m["project"]["id"]=""
    with pytest.raises(ValueError,match="project.id"): assess_pilot(m)
