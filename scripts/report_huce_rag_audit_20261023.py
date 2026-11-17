"""Build the human-readable verdict from immutable live-audit receipts."""
import argparse
import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from knowledge_platform import ROOT, STATE, checked_path, retain


def read(name):
    return json.loads(checked_path(STATE / name, ROOT).read_text(encoding="utf-8"))


def link(path, label=None):
    p = checked_path(Path(path), ROOT)
    return f"[{label or p.name}](<{p.as_posix()}>)"


EXPECTED = {
    "tuition_k64": ("QĐ924, trang 2, I.1: KS chính quy K64 trở về trước; 580.500 đồng/tín chỉ, khác CDIO.", ("580.500",)),
    "tuition_cdio": ("QĐ924, trang 2, I.2: CDIO K64, 649.000 đồng/tín chỉ.", ("649.000",)),
    "tuition_clc": ("QĐ924, trang 2, I.3: K66 trở về trước 336.000 đồng/ĐVHT; từ K67 533.000 đồng/tín chỉ.", ("336.000 đồng/ĐVHT", "533.000 đồng/tín chỉ")),
    "tuition_vlvh": ("QĐ924, trang 2, II: vừa làm vừa học CN 964.500; KS/KTS 870.500 đồng/tín chỉ.", ("964.500", "870.500")),
    "tuition_surcharge": ("QĐ924, trang 2, I.8: K70 trở về trước 15 triệu; K71 17 triệu; liên kết quốc tế 19,5 triệu/năm, trong thời gian đào tạo chuẩn.", ("15.000.000", "17.000.000", "19.500.000")),
    "password_new": ("QĐ2114, trang PDF 8, Điều10.1.e: ít nhất 01 lần/06 tháng.", ("06 tháng",)),
    "lab_damage": ("Nội quy phòng máy, trang 2, khoản7: báo ngay giảng viên phụ trách lớp.", ("giảng viên phụ trách lớp",)),
    "lab_end": ("Nội quy phòng máy, trang 2, khoản11: tắt máy, sắp xếp, vệ sinh; cán bộ lớp bàn giao giảng viên hướng dẫn.", ("tắt máy", "vệ sinh", "giảng viên hướng dẫn")),
    "lab_food": ("Nội quy phòng máy, trang 2, khoản5 và6: cấm nước uống và dùng máy tính xách tay.", ("không được mang nước uống", "không được sử dụng máy tính xách tay")),
    "lab_sanction": ("Nội quy phòng máy, trang 2, khoản12: đình chỉ học tại phòng máy, kỷ luật theo quy chế; mất/hỏng thiết bị phải bồi thường. Chỉ hỏi quy định chung.", ("đình chỉ", "bồi thường")),
    "missing_conditions": ("Chưa đủ khóa/chương trình/năm để chọn một mức; hỏi làm rõ, không chọn tiền, không gọi BGE.", ()),
    "conditions_followup": ("Tiếp câu học phí CNTT, user bổ sung CN chính quy K71, 2026–2027: áp dụng dòng I.5 từ K69, 592.500 đồng/tín chỉ; không dùng dòng K65–K68.", ("592.500",)),
    "surcharge_followup": ("Giữ K71 từ lời user vừa bổ sung: phụ thu Anh ngữ 17.000.000 đồng/năm trong thời gian chuẩn.", ("K71", "17.000.000")),
    "wrong_year_new": ("Release có bảng năm 2026–2027; không xác nhận mức năm 2025–2026 từ bảng này.", ()),
    "out_of_corpus": ("Không có nguồn học bổng trong release 3 tài liệu; từ chối có căn cứ, không bịa GPA.", ()),
    "personal_unconnected": ("Chưa có SSO/API học vụ theo xác nhận chủ hệ thống; không đọc hồ sơ/lịch/nợ học phí giả.", ()),
    "fixture_sao_mai": ("Nguồn Sao Mai đã thu hồi, không thành viên release; không bịa giờ mở cửa.", ()),
}


def assess(case):
    name, result = case["name"], case.get("final") or {}
    content = result.get("content", "")
    if name == "missing_conditions":
        correct = result.get("response_class") == "clarification_request" and not result.get("citations")
    elif name in {"wrong_year_new", "out_of_corpus", "personal_unconnected", "fixture_sao_mai"}:
        correct = result.get("status") == "abstained" and not result.get("citations") and "592.500" not in content
        if name == "personal_unconnected":
            correct = correct and "chưa kết nối" in content
    else:
        correct = result.get("status") == "answered" and all(value in content for value in EXPECTED[name][1])
        if name == "conditions_followup":
            correct = correct and ("K71" in content or re.search(r"từ\s+K69", content, re.I)) and not re.search(r"K65\s+đến\s+K68", content)
        if name in {"tuition_k64", "tuition_cdio", "conditions_followup"}:
            correct = correct and "ĐVHT" not in content
        expected_version = ("01a167eb-e62e-71d9-91ea-a9aedc888f0d" if name == "password_new" else
            "01a168c6-d1c7-7ddb-9590-f7a141f31698" if name.startswith("lab_") else "01a167c6-b6ca-77b2-a2a6-cefd66345d5d")
        correct = correct and bool(case["sources"]) and all(s["status"] == 200 and s["anonymous_status"] == 401 and s["hash_verified"]
            and s["body"]["citation"]["document_version_id"] == expected_version
            and s["body"]["citation"]["release_id"] == "01a168c6-dce3-7b72-bcbd-b5797b9452b8"
            and s["body"]["citation"]["release_generation"] == 12 for s in case["sources"])
    return bool(correct)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", required=True)
    args = parser.parse_args()
    data = read(args.questions)
    sources = read("independent-sources-20261023T125049141884.json")
    integrity = read("independent-integrity-20261023T130939043735.json")
    security = read("independent-security-20261023T133320853632.json")
    faults = read("independent-faults-20261023T130740658290.json")
    concurrent = read("independent-concurrent-20261023T132448893932.json")
    concurrent_full = read("independent-concurrent-20261023T133308201119.json")
    snapshot = read("independent-snapshot-20261023T133515361568.json")
    verdicts = [{"name": case["name"], "passed": assess(case)} for case in data["cases"]]
    passed = sum(row["passed"] for row in verdicts)
    times = sorted(case["latency_seconds"] for case in data["cases"])
    native_delta = data["after"]["native"]["usage_counts"]["inference"] - data["before"]["native"]["usage_counts"]["inference"]
    paid_delta = data["after"]["paid"]["calls"] - data["before"]["paid"]["calls"]
    now = datetime.now(timezone(timedelta(hours=7))).isoformat()
    lines = ["# Kiểm định RAG HUCE độc lập — 23/10/2026", "", f"Cập nhật: {now} (UTC+7).",
        "", f"**Kết luận: CHƯA ĐẠT nghiệm thu đầu cuối. {passed}/{len(verdicts)} ca chính đạt nội dung, điều kiện và citation theo bản gốc.** "
        "Hệ thống có truy xuất/generation thật và dùng đúng ba tài liệu HUCE đã đối chiếu. Kết quả này không chứng minh toàn kho hoặc production sẵn sàng.",
        "", "## Phạm vi và trạng thái thực tế", "",
        "API 8015, frontend snapshot v11 cổng3015 qua proxy8015; PostgreSQL local55437, DB campus247_knowledge_local_20261023, tenant huce-local-public. "
        "Desired/serving/ack cùng release `01a168c6-dce3-7b72-bcbd-b5797b9452b8`, generation12, policy_generation3. "
        "Có117 nguồn/126version, 3 nguồn phục vụ và122version NEEDS_REVIEW, gồm predecessor. Không đưa122version qua review hàng loạt.",
        "", "Review là kiểm kỹ thuật tự động theo ủy quyền chủ hệ thống, không giả cán bộ HUCE phê duyệt. Chưa có SSO/OIDC hoặc API học vụ cá nhân. "
        "Không tạo sinh viên/lịch/hồ sơ giả. Không đổi release hoặc dữ liệu nguồn trong kiểm định này.",
        "", "## Original, provenance, hiệu lực và evidence", "",
        "Đã kiểm lại hash original/rendition/metadata, acquisition receipt và ảnh scan embedded; giữ original QĐ924 là HTML công bố, không thay bằng PDF dựng lại. "
        "Đối chiếu trực tiếp hai ảnh học phí và hai ảnh phòng máy. QĐ2114 có text PDF gốc, kiểm36span tại locator và xem ảnh render trang hiệu lực/mật khẩu. "
        "13đoạn phòng máy (12khoản và toàntrang2) khớp transcript/ảnh đã gắn original hash. Không có dòng `Loại nguồn:` hoặc `Phạm vi đã đối chiếu:` trong evidence đang phục vụ.",
        "", "| Nguồn / phiên bản | Original SHA256 | Hiệu lực đã đối chiếu |", "|---|---|---|"]
    for source in sources["originals"]:
        date = {"01a167c6-b6ca-77b2-a2a6-cefd66345d5d": "10/06/2026; Điều2; bảng chỉ năm2026–2027",
            "01a167eb-e62e-71d9-91ea-a9aedc888f0d": "31/12/2024; Điều2, trang PDF2",
            "01a168c6-d1c7-7ddb-9590-f7a141f31698": "09/04/2024; Điều2; evidence chỉ trang2"}[source["version_id"]]
        lines.append(f"| {link(source['original_path'],source['title'])}<br>`{source['version_id']}` | `{source['original_sha256']}` | {date} |")
    lines += ["", "Không suy ra ngày kết thúc năm học; số quyết định viết tay phòng máy còn chưa xác minh. Không xác minh độc lập mọi luật/văn bản được nguồn dẫn hoặc mọi sửa đổi ngoài snapshot. "
        "Hash chứng minh bytes giữ nguyên; đối chiếu ảnh/text/locator mới là căn cứ nội dung. Chi tiết: " + link(STATE / "independent-integrity-20261023T130939043735.json") + ".",
        "", "## Câu hỏi, kỳ vọng từ bản gốc và kết quả", "",
        "Đánh giá theo nội dung/khóa/chương trình/năm/đơn vị và source readback; `answered` hoặc có citation không tự động là đạt. "
        "Các cột Δnative/Δpaid lấy từ ledger trước/sau từng ca, không từ nội dung câu trả lời.",
        "", "| Ca | Đánh giá | Status | Giây | Δnative | Δpaid |", "|---|---|---|---:|---:|---:|"]
    for case, verdict in zip(data["cases"], verdicts, strict=True):
        native = case["counters_after"]["native"]["usage_counts"]["inference"] - case["counters_before"]["native"]["usage_counts"]["inference"]
        paid = case["counters_after"]["paid"]["calls"] - case["counters_before"]["paid"]["calls"]
        lines.append(f"| {case['name']} | {'ĐẠT' if verdict['passed'] else 'CHƯA ĐẠT'} | {(case.get('final') or {}).get('status','no completion')} | {case['latency_seconds']} | {native} | {paid} |")
    for case, verdict in zip(data["cases"], verdicts, strict=True):
        lines += ["", f"### {case['name']} — {'ĐẠT' if verdict['passed'] else 'CHƯA ĐẠT'}", "", "Câu hỏi: " + case["question"],
            "", "Căn cứ/kỳ vọng: " + EXPECTED[case["name"]][0], "", "Observed:", "",
            "> " + ((case.get("final") or {}).get("content", "Không có message.completed.")).replace("\n", "\n> "),
            "", f"HTTP{case['http_status']}; {case['latency_seconds']}giây; conversation `{case['conversation_id']}`."]
        for item in case["sources"]:
            cit = item["body"]["citation"]
            lines.append(f"Source HTTP{item['status']}, anonymous{item['anonymous_status']}, hash_verified={item['hash_verified']}; "
                f"version `{cit['document_version_id']}`, release `{cit['release_id']}`/generation{cit['release_generation']}, "
                f"locator `{json.dumps(cit['locator'],ensure_ascii=False)}`, evidence SHA256 `{cit['evidence_sha256']}`.")
    lines += ["", "## Lỗi đã xử lý và phần còn chưa đạt", "",
        "- Sai dòng học phí thật: KS chính quyK64 từng trả649.000 của CDIO; đã thêm guard chương trình/khóa/dòng/đơnvị và kiểm lại580.500. "
        "Guard chặn cả trường hợp đúng tiền nhưng sai khóa và cách ghi nhập nhằng tín chỉ(ĐVHT). Không hardcode câu trả lời thay generation.",
        "- Câu QĐ2114 có tiêu đề dài từng mất đoạn mật khẩu khỏi3ứng viên. Đã tập trung phần hỏi sau dẫn số văn bản, giữ nguyên câu đầy đủ để kiểm hiệu lực/claim; không áp dụng cắt scope phòngmáy. "
        "BGE và reranker vẫn chạy thật, ngưỡng relevance không đổi.",
        "- Follow-up phụ thu đã giữ điều kiện từ lời user; không lấy facts của trợ lý trước làm chứng cứ. "
        "Lượt cuối câu bổ sung CN/K71 đã chọn đúng dòng từK69 và592.500đồng/tínchỉ; lần lặp ngay trước trên cùng code còn bị từ chối do đơnvị. "
        "Vì vậy một lượt đạt chưa chứng minh ổn định; không tính các lần safe refusal trước đó là đạt. Receipt lần trước: independent-questions-20261023T132151094862.json.",
        "- Câu quy định xử lý vi phạm phòngmáy vẫn bị guard quy định kỷ luật từ chối. "
        "Nguồn nằm ở attachment Drive; guard hiện chỉ cho ngoại lệ rất hẹp với nguồn thuộc domain HUCE và mẫu claim chung. Không nới/tắt guard để qua test.",
        "- Các regression dùng index corpus99/118/123 đã trỏ sai điều khoản khi corpus thay đổi. Sửa sang source_id+section, giữ nguyên assertions/ngưỡng; các XML fail trước được giữ.",
        "- Runner đầu tiên chưa tôn trọng rate-limit30request/60s, nhận429; đã giữ kết quả đó và thêm chờ Retry-After cho request chưa được nhận. Không retry mù sau completion, không đổi rate-limit.",
        "", "## Quyền, binding và lỗi cô lập", "", "```json", json.dumps(security["checks"],ensure_ascii=False,indent=2), "```", "",
        "Owner đọc source/history200; anonymous401; principal kỹ thuật khác chủchat404; binding message/citation sai404; expired/tampered/revoked401; Origin không tin cậy403; demo/legacylogin404. "
        "Thử sửa hash/locator/version/bytes ở source được bao phủ thêm bằng API/frontend regression, không sửa message/DB đang phục vụ để thử.",
        "", "```json", json.dumps(faults["checks"],ensure_ascii=False,indent=2), "```", "",
        "Lỗi embedding/reranker được tiêm vào adapter của process audit và lỗi checksum vào bản sao row trong bộ nhớ. "
        "Cả hai model fault trả abstained/0candidate; checksum trả409SOURCE_INTEGRITY. Không thu hồi nguồn, dừng model thật hoặc sửaartifact/DB để tạo lỗi. "
        "Đây là bằng chứng guard xử lý fault cô lập, không phải bằng chứng chịu mọi sự cố production.",
        "", "## Latency, đồng thời và kế toán mô hình", "",
        f"17ca chính: min={times[0]}giây, median={statistics.median(times):.3f}giây, max={times[-1]}giây; "
        f"Δnative={native_delta}, Δpaid={paid_delta}. P95 chưa đáng tin với mẫu nhỏ. Receipt đầy đủ: " + link(STATE / args.questions) + ".",
        "", "Lượt2request đồng thời với câu viết ngắn:"]
    for case in concurrent["cases"]:
        lines.append(f"- {case['question']} → {case['final']['status']}, {case['latency_seconds']}giây: {case['final']['content']}")
    lines += ["", "Đối chiếu thêm2request đồng thời dùng đúng câu đầy đủ đã đạt khi chạy tuần tự:"]
    for case in concurrent_full["cases"]:
        lines.append(f"- {case['question']} → {case['final']['status']}, {case['latency_seconds']}giây: {case['final']['content']}")
    lines += ["", "Cặp câu đầy đủ đạt2/2, source200/hashđúng; cặp câu viếtngắn có completion nhưng chưa đạt0/2. "
        "Kết quả cho thấy chất lượng nhạy với cách hỏi; chưa phân lập toàn bộ ảnh hưởng cách diễn đạt và tải, không gọi đây là đạt SLO. "
        "Không tạo model thứ hai. BGE vẫn3ứng viên, pair envelope900, M3revision5617a9f61b028005a4858fdac845db406aefb181, rerankerrevision953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e. "
        "Không tăng deadline/outputbudget hoặc hạ ngưỡng để pass. Chưa đo tải kéo dài/soak/recall toàn corpus.",
        "", "BGE namespace accounting-only kế thừa counts, trần tổng=null; paidgateway cũng accounting-only. Giữ kế toán và reservation chưa xác định. "
        "Counter đầu kiểm định10057; snapshot cuối10449 native (+392 qua toàn bộ các lần thử lại/fault/browser/concurrency), không reset. "
        "Hai cổng BGE vẫn cùng PID17328; API17412, frontend1760 và PostgreSQL13956. RAM khả dụng tại snapshot3.53GB. "
        "Snapshot desired/serving/membership/models/caps: " + link(STATE / "independent-snapshot-20261023T133515361568.json") + ". Trong riêng campaign cuối:", "", "```json",
        json.dumps({"before":data["before"],"after":data["after"]},ensure_ascii=False,indent=2), "```",
        "", "## Browser và kiểm thử hồi quy", "",
        "Browser đăng nhập owner, gửi câu kết thúc ca phòngmáy thật, nhận đúng khoản11, reload khôi phục câu trả lời, mở citation và toàn đoạn nguồn trang2, hiệu lực09/04/2024. "
        "Receipt browser-after-20261023T132755891092.json lưu history/final_result; từ browser-before đến sau reload/source tăng đúng4native/4paid cho một câu hỏi. "
        "Ảnh sau được giữ; không có inference lặp khi reload/mởsource.",
        "", link(STATE / "ui-independent-chat-20261023.png"), "", link(STATE / "ui-independent-citation-20261023.png"),
        "", "Các bộ có phần trùng nhau, không cộng thành số test độc lập:",
        "- 77passed: independentregressions/relevance/followup/advancedRAG sau sửa sourceindex (XML02).",
        "- 85passed: generation/policy/citationsource/regression (XML04).",
        "- 79passed: knowledgeunit + feeunits + knowledgeadminAPI + chatSSE (XML05), không chạy lại4test PostgreSQL tạo namespace; thay vào đó kiểm trực tiếp DB/release đang dùng.",
        "- 73passed: tableexactspans + followup/reference + boundedregeneration trên code cuối (XML08). "
        "LầnXML06 thiếu PYTHONPATH fixturehistorical có1importfailure; XML07 đủpath đạt72. Không chỉnh accounting guard vì lỗi import.",
        "- 44frontendpassed: CitationSource, history-release, SSE, local-session, KnowledgePlatform; bao gồm tamperedhash/release/locator và previewconfirmation.",
        "", "Tái lập (PowerShell, workspace hiện tại):", "", "```powershell",
        "& 'infra/local/rag-fixture/.venv/Scripts/python.exe' scripts/audit_huce_rag_20261023.py questions --cases-file evals/datasets/huce-independent-20261023.json",
        "& 'infra/local/rag-fixture/.venv/Scripts/python.exe' scripts/audit_huce_rag_20261023.py integrity",
        "& 'infra/local/rag-fixture/.venv/Scripts/python.exe' scripts/audit_huce_rag_20261023.py security --question-report infra/local/knowledge-platform-20261023/" + args.questions,
        "& 'infra/local/rag-fixture/.venv/Scripts/python.exe' scripts/audit_huce_rag_20261023.py faults --question-report infra/local/knowledge-platform-20261023/" + args.questions,
        "$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'",
        "$env:PYTHONPATH='C:/Users/Duong Vinh/Vinh/infra/local/rag-fixture'",
        "& 'infra/local/rag-fixture/.venv/Scripts/python.exe' -m pytest tests/knowledge_platform/test_independent_audit_regressions.py tests/unit/conversation/test_followup_question_m2.py tests/unit/conversation/test_m2_reference_resolution_73.py tests/unit/retrieval/test_advanced_policy_regeneration.py -q -p pytest_asyncio.plugin",
        "```", "", "Chạy live cần quyền loopback; WinError10013 trong sandbox không chứng minh listener đã chết. "
        "Mỗi lần audit ghi receipt mới theo timestamp; không xóa/ghi đè chứng cứ cũ. Các receipt ở infra/local là runtimeignore, không chứa password/token/DSN.",
        "", "## Trạng thái cuối và giới hạn", "",
        "**Đạt:** ba original thật, hash/provenance/hiệu lực trong phạm vi đối chiếu; state/releasebinding; phần lớn ca đã nêu; quyền/ownership; browserreload/source; guardfault cô lập; kế toán không trần tổng.",
        "", "**Chưa đạt:** độ ổn định chuỗi hỏi học phí → bổ sung CN/K71 (lượt cuối đạt nhưng lần lặp trước từchối); quy định xử lý vi phạm phòngmáy; hai câu viếtngắn thửđồngthời. "
        "Không thể tuyên bố hệ thống đã trả lời tốt mọi câu trong ba nguồn.",
        "", "**Chưa kiểm chứng:** recall toàncorpus,122pendingversion, OCR/DOCX tổngquát, cập nhật tài liệu ngoài snapshot, SSO/API học vụ cá nhân, fault mạng/DBproduction, tải dài hạn và phục hồi vận hành liên tục. "
        "Không commit/push/deployproduction, không reset/clean/xóa nguồn/chat/DB/audit/snapshot; các runtime reload chỉ áp dụng code local."]
    output = checked_path(ROOT / "docs/HUCE_RAG_INDEPENDENT_AUDIT_20261023.md", ROOT)
    with output.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    retain(STATE / ("independent-verdict-" + datetime.now().strftime("%Y%m%dT%H%M%S%f") + ".json"),
        {"report":str(output),"questions_receipt":args.questions,"passed":passed,"total":len(verdicts),"verdicts":verdicts,
         "end_to_end_accepted":False,"integrity":integrity["checks"]})
    print(json.dumps({"report":str(output),"passed":passed,"total":len(verdicts),"end_to_end_accepted":False}))


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
