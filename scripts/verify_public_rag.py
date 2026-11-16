"""Exercise screen prompts and ordinary Vietnamese through actual HTTP/SSE."""
import hashlib
import json
import re
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "infra/local/public-rag-20261013"
CASES = [
    ("Điều kiện xét học bổng", ["học", "bổng"]),
    ("Thủ tục xin cấp bảng điểm", ["bảng điểm", "một cửa"]),
    ("Quy chế hoãn thi học kỳ", ["thi"]),
    ("Quy chế chuyển ngành", ["năm thứ nhất", "Hiệu trưởng"]),
    ("Tư vấn quy chế & học vụ HUCE", ["học"]),
    ("Điều kiện xét học bổng kỳ này", ["học", "bổng"]),
    ("Thủ tục xin cấp bảng điểm Một cửa", ["bảng điểm", "một cửa"]),
    ("Tra cứu phòng tự học thư viện", ["tầng 2"]),
    ("Cho em hỏi xin bảng điểm ở đâu và cần làm gì ạ?", ["bảng điểm", "một cửa"]),
    ("hoc bong can dieu kien gi vay", ["học", "bổng"]),
    ("Thư viện có chỗ để em tự học với nhóm bạn không?", ["tầng 2"]),
    ("Em đang năm nhất, có được chuyển ngành không?", ["năm thứ nhất"]),
    ("Nếu em ốm đúng ngày thi thì làm sao xin hoãn thi?", ["thi"]),
    ("Xin bảng điểm có phải đến trường không hay làm online được?", ["một cửa"]),
]
FAQ_SAMPLE_CASES = [
    ("Một tín chỉ tương đương bao nhiêu giờ học?", ["50"]),
    ("Học phần tiên quyết là gì?", ["đạt"]),
    ("Cử nhân chính quy được kéo dài việc học tối đa bao lâu?", ["8"]),
    ("Chọn lớp xong rồi có cần bấm lưu không?", ["lưu"]),
    ("Một học kỳ chính có ít nhất bao nhiêu tuần học?", ["15"]),
    ("Điểm D có được coi là qua môn không?", ["đạt", "4"]),
    ("Học cải thiện bị thấp hơn điểm cũ thì lấy điểm nào?", ["cao nhất"]),
    ("GPA học kỳ có tính theo số tín chỉ của từng môn không?", ["tín chỉ"]),
    ("Hạn đăng ký phúc khảo là bao lâu sau khi có điểm?", ["10", "ngày làm việc"]),
    ("Muốn học cùng lúc hai chương trình thì sớm nhất từ năm nào?", ["năm thứ hai"]),
    ("Không dự lễ trao bằng thì nhận bằng ở đâu?", ["303", "A1"]),
    ("Mất thẻ sinh viên thì đăng ký làm lại như thế nào?", ["motcua.huce.edu.vn"]),
    ("Mượn và trả giáo trình ở đâu trong thư viện?", ["tầng 5"]),
    ("Có được tự đổi chỗ ở với bạn trong ký túc xá không?", ["không", "tự ý"]),
]
GRADUATION_CASES = [
    ("Điều kiện để được xét tốt nghiệp HUCE là gì?", ["2.0", "đình chỉ"]),
    ("Chưa tốt nghiệp thì có được chứng nhận các môn đã học không?", ["chứng nhận", "tích luỹ"]),
]


def comparable(text):
    # Decimal comma/dot and the two Vietnamese spellings are equivalent here;
    # the actual final answer and original source are retained unchanged.
    return re.sub(r"(?<=\d),(?=\d)", ".", text.lower()).replace("tích lũy", "tích luỹ")


def frames(text):
    result = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        fields = dict(line.split(":", 1) for line in block.splitlines() if ":" in line)
        if "data" in fields:
            result.append((fields.get("event", "").strip(), json.loads(fields["data"])))
    return result


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    target = OUT / (sys.argv[1] if len(sys.argv) > 1 else "natural-language-verification.json")
    if not target.resolve().is_relative_to(OUT.resolve()) or target.exists():
        raise ValueError("fresh verification target required")
    results = []
    excluded = []
    cases = CASES
    scope = "screen_prompts_and_natural_questions"
    if "--faq-sample" in sys.argv:
        cases = FAQ_SAMPLE_CASES
        scope = "cross_topic_faq_sample"
    elif "--graduation" in sys.argv:
        cases = GRADUATION_CASES
        scope = "graduation_public_rules"
    elif "--faq-service-recheck" in sys.argv:
        cases = FAQ_SAMPLE_CASES[-2:]
        scope = "library_and_dormitory_recheck"
    elif "--only-scholarship" in sys.argv:
        cases = [(q, expected) for q, expected in CASES if "học bổng" in q or "hoc bong" in q]
        scope = "scholarship_output_guard_audit"
    elif "--except-scholarship" in sys.argv:
        excluded = [q for q, _ in CASES if "học bổng" in q or "hoc bong" in q]
        cases = [(q, expected) for q, expected in CASES if q not in excluded]
    with httpx.Client(base_url="http://127.0.0.1:8000", trust_env=False, timeout=25) as client:
        auth = client.get("/v1/auth/demo-session"); auth.raise_for_status()
        headers = {"Authorization": "Bearer " + auth.json()["token"]}
        created = client.post("/v1/conversations", headers=headers, json={}); created.raise_for_status()
        cid = created.json()["id"]
        for question, required in cases:
            started = time.monotonic()
            response = client.post(f"/v1/conversations/{cid}/messages:stream", headers=headers, json={"content": question})
            events = frames(response.text)
            final = next((v for event, v in reversed(events) if event == "message.completed"), None)
            failed = next((v.get("code") for event, v in events if event == "message.failed"), None)
            clarification = question == "Tư vấn quy chế & học vụ HUCE"
            success = (response.status_code == 200 and final is not None
                       and final["response_class"] == ("clarification_request" if clarification else "grounded_answer")
                       and all(comparable(term) in comparable(final["content"]) for term in required)
                       and not any(term in final["content"].lower() for term in ["mô phỏng", "syn-", "xác thực không hợp lệ"]))
            opened = []
            if final:
                for mapping in final["citations"]:
                    citation = mapping["citation"]
                    source = client.get(f"/v1/conversations/{cid}/messages/{final['message_id']}/citations/{citation['citation_id']}/source", headers=headers)
                    if source.status_code == 200:
                        value = source.json()
                        valid = hashlib.sha256(value["content_text"].encode()).hexdigest() == value["content_sha256"]
                    else:
                        valid = False
                    opened.append(valid)
                success = success and (clarification or bool(opened)) and all(opened)
            result = {"question": question, "passed": bool(success), "HTTP": response.status_code,
                "latency_ms": round((time.monotonic() - started) * 1000), "failure_code": failed,
                "final": final, "source_checks": opened}
            results.append(result)
            print(json.dumps({"question": question, "passed": bool(success), "response_class": final["response_class"] if final else None,
                "content": final["content"] if final else None, "failure": failed}, ensure_ascii=False), flush=True)
            # The application preserves its request-rate bound. Each source
            # open counts too, so space tests instead of weakening that bound.
            time.sleep(7)
        history = client.get(f"/v1/conversations/{cid}/messages?limit=100", headers=headers)
        history.raise_for_status()
        stored = history.json()["items"]
        persisted = all(any(m["id"] == r["final"]["message_id"] and m.get("final_result") == r["final"] for m in stored)
                        for r in results if r["final"])
    with target.open("x", encoding="utf-8") as stream:
        json.dump({"conversation_id": cid, "results": results, "persisted_finals_verified": persisted,
            "passed": sum(r["passed"] for r in results), "total": len(results),
            "verification_scope": scope,
            "excluded_questions": excluded, "full_request_completed": not excluded and all(r["passed"] for r in results)}, stream, ensure_ascii=False, indent=2)
    raise SystemExit(0 if all(r["passed"] for r in results) and persisted else 1)


if __name__ == "__main__":
    main()
