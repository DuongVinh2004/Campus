"""Real selected-source checks; never a claim that all HUCE sources are ready."""
import json
import re
import argparse
from datetime import UTC, datetime

import httpx

from knowledge_platform import ROOT, STATE, checked_path, retain, model_budget

API="/v1/knowledge/platform"
CASES=[
    ("cn_k71","CNTT chương trình cử nhân chính quy K71 năm học 2026-2027 học phí mỗi tín chỉ và phụ thu Anh ngữ bao nhiêu?"),
    ("missing_scope","học phí ngành công nghệ thông tin"),
    ("ks_k69","CNTT chương trình kỹ sư chính quy từ K69 năm học 2026-2027 học phí mỗi tín chỉ bao nhiêu?"),
    ("security_2114","Theo Quyết định 2114/QĐ-ĐHXDHN, người dùng phải thay đổi mật khẩu ít nhất bao lâu một lần?"),
    ("lab_late","Theo nội quy phòng thực hành máy tính Trung tâm CNTT và CSDL HUCE, sinh viên đến muộn sau bao nhiêu phút thì không được vào phòng máy?"),
    ("lab_usb","Theo nội quy phòng thực hành máy tính Trung tâm CNTT và CSDL HUCE, sinh viên muốn cắm USB thì cần ai đồng ý?"),
    ("fixture_absent","Phòng Sao Mai mở cửa mấy giờ?"),
    ("schedule_unavailable","Xem lịch học cá nhân của tôi tuần này"),
    ("wrong_year","CNTT chương trình cử nhân chính quy K71 năm học 2024-2025 học phí mỗi tín chỉ bao nhiêu?")]


def native_count():
    budget=model_budget()
    if budget.get("status")=="ACCOUNTING_ONLY":
        return budget["usage_counts"]["inference"]
    paths=(ROOT/"infra/local/rag-advanced-models-20261013-18").glob("native-*-reservation.json")
    return max((int(p.name.split("-")[1]) for p in paths),default=0)


def final(stream):
    for block in stream.split("\n\n"):
        if "event: message.completed\n" in block:
            return json.loads(next(line[6:] for line in block.splitlines() if line.startswith("data: ")))
    return None


def main():
    import sys
    if hasattr(sys.stdout,"reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser=argparse.ArgumentParser()
    parser.add_argument("--cases",nargs="+",choices=[name for name,_ in CASES])
    args=parser.parse_args()
    report={"at":datetime.now(UTC).isoformat(),"scope":"selected real QD924/QD2114/lab rules; not full-corpus acceptance", "cases":{},"native_before":native_count()}
    with httpx.Client(base_url="http://127.0.0.1:8015",trust_env=False,timeout=90) as client:
        credentials=json.loads((STATE/"owner-credentials.json").read_text(encoding="utf-8"))
        login=client.post(API+"/session",json={k:credentials[k] for k in ("username","password")})
        assert login.status_code==200
        token=login.json()["token"]
        state=client.get(API+"/state").json()
        report["desired"]=state["desired"];report["serving"]=state["serving"]
        report["availability"]=client.get(API+"/availability").json()
        report["catalog_fixture_absent"]=all("Sao Mai" not in s["title"] and not s["canonical_uri"].startswith("urn:") for s in state["sources"])
        report["demo_login_status"]=client.get("/v1/auth/demo-session").status_code
        report["legacy_login_status"]=client.post(API+"/local-session",json={"account":"KA02"}).status_code
        for name,question in CASES:
            if args.cases and name not in args.cases:continue
            remaining=model_budget()["remaining_inferences"]
            if remaining is not None and remaining<4:
                report["cases"][name]={"not_run":"Insufficient bounded model budget"};continue
            before=native_count()
            created=client.post("/v1/conversations",json={"mode":"temporary"})
            assert created.status_code==201
            cid=created.json()["id"]
            response=client.post(f"/v1/conversations/{cid}/messages:stream",json={"content":question})
            result=final(response.text)
            case={"question":question,"conversation_id":cid,"http_status":response.status_code,"final":result,
                "native_before":before,"native_after":native_count()}
            if result and result.get("citations"):
                citation=result["citations"][0]["citation"]
                path=f"/v1/conversations/{cid}/messages/{result['message_id']}/citations/{citation['citation_id']}/source"
                source=client.get(path)
                case["source_status"]=source.status_code
                case["source"]=source.json()
                with httpx.Client(base_url="http://127.0.0.1:8015",trust_env=False,timeout=15) as anonymous:
                    case["anonymous_source_status"]=anonymous.get(path).status_code
            content=(result or {}).get("content","")
            if name=="cn_k71":case["passed"]=bool(result and result["status"]=="answered" and all(v in content for v in ("592.500","17.000.000")) and case.get("source_status")==200 and case.get("anonymous_source_status")==401)
            elif name=="ks_k69":case["passed"]=bool(result and result["status"]=="answered" and "547.000" in content and case.get("source_status")==200)
            elif name=="missing_scope":case["passed"]=bool(result and result["response_class"]=="clarification_request" and all(v in content for v in ("khóa học","chương trình","năm học")) and before==native_count())
            elif name=="security_2114":case["passed"]=bool(result and result["status"]=="answered" and re.search(r"0?6\s*tháng",content) and case.get("source_status")==200)
            elif name in {"lab_late","lab_usb"}:
                correct_answer="15" in content if name=="lab_late" else "cán bộ phòng máy" in content.lower()
                source=case.get("source",{})
                bound=next((v for v in state["versions"] if v["version_id"]==source.get("citation",{}).get("document_version_id")),{})
                case["passed"]=bool(result and result["status"]=="answered" and correct_answer and case.get("source_status")==200
                    and bound.get("original_sha256")=="8a0bc59b2cc844d7f606204f8b4c3cbf6c99e023033493057f923929221810c7"
                    and source["citation"]["locator"]["page_start"]==2
                    and source["content_sha256"]==source["citation"]["evidence_sha256"])
            else:case["passed"]=bool(result and result["status"]=="abstained" and not result["citations"] and "592.500" not in content and "Giải tích 1" not in content)
            report["cases"][name]=case
            retain(STATE/("huce-case-"+name+"-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"),case)
            print(json.dumps({"case":name,"passed":case["passed"],"content":content,"source_status":case.get("source_status"),"native_after":case["native_after"]},ensure_ascii=False),flush=True)
        client.post("/v1/auth/logout")
        report["revoked_session_status"]=client.get(API+"/state",headers={"Authorization":"Bearer "+token}).status_code
        report["native_after"]=native_count()
    report["all_selected_checks_passed"]=all(c.get("passed",False) for c in report["cases"].values())
    target=checked_path(STATE/("huce-acceptance-"+datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")+".json"),ROOT)
    retain(target,report)
    print(json.dumps({"report":str(target),"all_selected_checks_passed":report["all_selected_checks_passed"],"native_after":report["native_after"]}))


if __name__=="__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
