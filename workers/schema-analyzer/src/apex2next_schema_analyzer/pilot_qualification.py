"""Offline WP9 pilot qualification assessor; validates declared evidence only."""
from __future__ import annotations
import argparse, hashlib, json, math, re, sys
from pathlib import Path
from typing import Any

INPUT_VERSION="apex2next.wp9-pilot-input.v1"
REPORT_VERSION="apex2next.wp9-pilot-qualification.v1"
SHA=re.compile(r"^sha256:[0-9a-f]{64}$")
GATES=(
("WP9-001","Source package intake and integrity"),
("WP9-002","APEX runtime/version and scope confirmed"),
("WP9-003","Extraction and normalized IR reviewed"),
("WP9-004","Oracle schema and metadata inventory reconciled"),
("WP9-005","PL/SQL and dependency dispositions reviewed"),
("WP9-006","Target schema and generated runtime reviewed"),
("WP9-007","Data migration rehearsal and reconciliation"),
("WP9-008","Critical journey functional parity"),
("WP9-009","Security and authorization parity"),
("WP9-010","Performance and operational acceptance"),
("WP9-011","Backup restore and rollback rehearsal"),
("WP9-012","Business and technical owner acceptance"),
)
def _canonical(v:Any)->str:
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)
def _digest(v:Any)->str:
    return "sha256:"+hashlib.sha256(_canonical(v).encode()).hexdigest()
def _text(v:Any)->bool:
    return isinstance(v,str) and bool(v.strip())
def _source(source:Any)->list[dict[str,Any]]:
    s=source if isinstance(source,dict) else {}
    out=[]
    fmt=s.get("format")
    out.append({"id":"SRC-001","status":"PASS" if fmt in {"APEX_SQL_EXPORT","APEXLANG_DIRECTORY"} else "FAIL","message":"Supported source format declared." if fmt in {"APEX_SQL_EXPORT","APEXLANG_DIRECTORY"} else "Unsupported or missing source format."})
    sanitized=s.get("sanitized")
    out.append({"id":"SRC-002","status":"PASS" if sanitized is True else "FAIL" if sanitized is False else "NOT_VERIFIED","message":"Sanitization attested by submitter." if sanitized is True else "Source package must be explicitly confirmed sanitized."})
    for key,code in (("applicationId","SRC-003"),("apexRuntimeVersion","SRC-004"),("snapshotId","SRC-005")):
        out.append({"id":code,"status":"PASS" if _text(s.get(key)) else "NOT_VERIFIED","message":key+" declared." if _text(s.get(key)) else key+" missing."})
    artifacts=s.get("artifacts")
    if not isinstance(artifacts,list) or not artifacts:
        out.append({"id":"SRC-006","status":"NOT_VERIFIED","message":"Source artifact inventory missing."})
    else:
        seen=set(); bad=[]
        for a in artifacts:
            if not isinstance(a,dict): bad.append("malformed artifact"); continue
            p,h,z=a.get("path"),a.get("sha256"),a.get("sizeBytes")
            if not _text(p) or p.startswith(("/","\\")) or ".." in Path(p).parts or p in seen: bad.append(str(p)+": unsafe/duplicate path")
            if not isinstance(h,str) or not SHA.fullmatch(h): bad.append(str(p)+": invalid SHA-256")
            if not isinstance(z,int) or isinstance(z,bool) or z<0: bad.append(str(p)+": invalid size")
            if _text(p): seen.add(p)
        out.append({"id":"SRC-006","status":"FAIL" if bad else "PASS","message":"; ".join(bad[:8]) if bad else "Artifact paths, sizes, and hash declarations are structurally valid."})
    return out
def assess_pilot(manifest:dict[str,Any])->dict[str,Any]:
    if not isinstance(manifest,dict): raise ValueError("manifest must be an object")
    if manifest.get("manifestVersion")!=INPUT_VERSION: raise ValueError("manifestVersion must be "+INPUT_VERSION)
    project=manifest.get("project")
    if not isinstance(project,dict) or not _text(project.get("id")): raise ValueError("project.id must be a non-empty string")
    checks=_source(manifest.get("source"))
    gates=manifest.get("gates") if isinstance(manifest.get("gates"),dict) else {}
    for gid,desc in GATES:
        item=gates.get(gid)
        if not isinstance(item,dict):
            status,code,msg="NOT_VERIFIED","WP9001","Gate evidence missing."
        else:
            state,ref=item.get("status"),item.get("evidenceRef")
            if state not in {"PASS","WARN","FAIL","NOT_VERIFIED"}: status,code,msg="NOT_VERIFIED","WP9002","Gate status invalid or missing."
            elif state=="PASS" and not _text(ref): status,code,msg="NOT_VERIFIED","WP9003","PASS requires evidence reference."
            elif state=="PASS": status,code,msg="PASS",None,"Evidence reference supplied."
            elif state=="FAIL": status,code,msg="FAIL","WP9004","Gate explicitly failed."
            elif state=="WARN": status,code,msg="WARN","WP9005","Unresolved warning."
            else: status,code,msg="NOT_VERIFIED","WP9006","Gate not verified."
        checks.append({"id":gid,"description":desc,"status":status,"diagnostic":code,"message":msg,"evidenceRef":item.get("evidenceRef") if isinstance(item,dict) and _text(item.get("evidenceRef")) else None})
    acceptance=manifest.get("acceptance") if isinstance(manifest.get("acceptance"),dict) else {}
    for key,code in (("maxCriticalDefects","ACC-001"),("maxHighDefects","ACC-002")):
        v=acceptance.get(key); valid=isinstance(v,int) and not isinstance(v,bool) and v>=0
        checks.append({"id":code,"status":"PASS" if valid and v==0 else "FAIL" if valid else "NOT_VERIFIED","message":f"{key}={v}" if valid else f"{key} must be an explicit non-negative integer."})
    for key,code in (("rtoMinutes","ACC-003"),("rpoMinutes","ACC-004")):
        v=acceptance.get(key); valid=isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0
        checks.append({"id":code,"status":"PASS" if valid else "NOT_VERIFIED","message":key+" declared." if valid else key+" must be finite and non-negative."})
    counts={s:sum(x["status"]==s for x in checks) for s in ("PASS","WARN","FAIL","NOT_VERIFIED")}
    qualified=all(counts[s]==0 for s in ("WARN","FAIL","NOT_VERIFIED"))
    status="QUALIFIED" if qualified else "BLOCKED" if counts["FAIL"] else "CONDITIONAL" if counts["WARN"] else "INCOMPLETE"
    return {"reportVersion":REPORT_VERSION,"project":{"id":project["id"],"name":project.get("name")},"inputSha256":_digest(manifest),"status":status,"summary":{"total":len(checks),**counts},"checks":checks,"productionQualification":{"eligible":qualified,"rule":"All source intake checks, twelve WP9 gates, zero critical/high defects, and explicit RTO/RPO must PASS.","authorization":"Advisory evidence only; not production change approval or independent evidence verification."},"limitations":["Artifact hashes are format-checked but not recomputed from files by this assessor.","Evidence references and gate statuses are supplied assertions, not independently witnessed evidence.","Synthetic fixtures validate the assessor contract only; they cannot qualify a real APEX application.","Real source exports, consistent Oracle snapshots, target pilot, witnessed rehearsals, and owner approvals are required."]}
def assess_pilot_file(input_path:str|Path,output_path:str|Path)->dict[str,Any]:
    m=json.loads(Path(input_path).read_text(encoding="utf-8")); r=assess_pilot(m)
    p=Path(output_path); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    return r
def main()->int:
    p=argparse.ArgumentParser(description="Assess WP9 APEX pilot qualification evidence.")
    p.add_argument("manifest"); p.add_argument("--output",required=True); a=p.parse_args()
    try: r=assess_pilot_file(a.manifest,a.output)
    except (OSError,json.JSONDecodeError,ValueError) as e:
        print(f"pilot qualification error: {e}",file=sys.stderr); return 2
    print(json.dumps({"status":r["status"],"summary":r["summary"],"output":a.output},sort_keys=True))
    return {"QUALIFIED":0,"BLOCKED":1,"CONDITIONAL":3,"INCOMPLETE":4}[r["status"]]
if __name__=="__main__": raise SystemExit(main())
