"""Retain a verified continuation checkpoint with actual source and runtime limits."""
import copy
import json
import subprocess
import httpx
import huce_document_pipeline as p


def main():
    p.event('preflight',p.preflight())
    ready_file=p.PUB/'reviewed-corrections-20261021-v31.ready.json';ready=p.read(ready_file)
    assert ready['index_sha256']==p.sha(p.checked(p.ROOT/ready['index']).read_bytes())
    assert ready['release_sha256']==p.sha((p.PUB/'reviewed-corrections-20261021-v31.json').read_bytes())
    verification=max((p.BASE/'events').glob('*-verification.json'));verified=p.read(verification)
    assert verified['baseline_fingerprint']==ready['fingerprint']
    groups=[('support','20261022T151049013110Z-retrieval-source-probes.json',8),
            ('ict','20261022T150828594989Z-retrieval-source-probes.json',4),
            ('conference_regression','20261022T151228654801Z-retrieval-source-probes.json',6),
            ('graduation_comparison','20261022T152147798286Z-retrieval-source-probes.json',2)]
    probes=[]
    for label,name,count in groups:
        file=p.BASE/'events'/name;receipt=p.read(file)
        assert receipt['passed'] and len(receipt['results'])==count
        probes.append({'group':label,'receipt':p.rel(file),'sha256':p.sha(file.read_bytes()),'queries':count,'fingerprint':receipt['fingerprint']})
    health=httpx.get('http://127.0.0.1:8006/health/entry',trust_env=False,timeout=10);health.raise_for_status()
    assert health.json()['generation']=='retained_live' and health.json()['storage']=='durable_local_copy'
    from multi_agent_live_resources import native_directory_snapshot
    native=native_directory_snapshot(p.ROOT/'infra/local/rag-advanced-models-20261013-16')
    priority=copy.deepcopy(p.read(p.BASE/'it-common-priority-20261022-70.json'))
    priority.update(at=p.now(),predecessor=p.rel(p.BASE/'it-common-priority-20261022-70.json'),
        current_catalog=p.rel(p.CATALOG),current_catalog_sha256=p.sha(p.CATALOG.read_bytes()),
        current_ready_release=31,current_ready_marker=p.rel(ready_file),current_index_fingerprint=ready['fingerprint'],
        full_verification_receipt=p.rel(verification),current_retrieval_probe_receipts=probes,
        common_status='Ready28:49support excerpts from2officialHTML,2distinctDrivePDFidentities sharing one5pagepayload,and3unfilledDOCXforms.17annex units perPDFbind original columns and merged-cell inheritance. Eight unchanged realBGEqueries pass onready30. Deadline29/09–20/10/2026expired; legal citations,LôLô/LôTô,and source wording variants remain explicit. DOCXlayoutnotverified.',
        common_core_status='Audit74binds5handbook images,6regulation images and2official tuition scans. Verified924signed10/06/2026; legacy15/08dateand1486scope corrected in catalogverifiedmetadata while observations retained. Ready30replaced unannotated handbook31summary with conflict note, retaining oldcitation. Ready31adds explicitVietnamese scope/threshold comparison and retains30too. Two unchanged graduation queries passon31. Full116pagehandbook/26pageregulation review and missing referenced appendices remain open.',
        ict_rules_status='Two linkedPDFs acquired;all19originalimages and fullnative/OCRtext read. Ready29:50units retaining19securityarticles and12labclauses, including multi-page continuations. Four unchanged realBGEqueries passonready30. Securityarticle17duplicatesnumber4; labhandwritten decision number unresolved. Bothsourcesincomplete.',
        backend={'pid':10872,'session':43384,'launcher':'scripts/campus_backend.py','health':health.json(),
            'loaded_release_on_startup':31,'fingerprint_basis':'Ready31 was latest before startup; campus_backend loads latestready store. Health does not expose fingerprint.',
            'storage':'.tooling/campus-single-entry-20261015-01/runtime','gateway_and_history_preserved':True,
            'paid_generation_calls_this_work':0,'budget_or_controls_changed':False,
            'failed_wrong_launcher_attempt':'run_advanced_rag.py refused UNAUTHORIZED_CAP. No control bypassed; corrected to existing campus_backend composition.'},
        native_runtime={'state':'infra/local/rag-advanced-models-20261013-16','pid':18548,'session':43865,
            'predecessor':'infra/local/rag-advanced-models-20261013-15','snapshot':native,
            'caps_changed':False,'remaining_native_inferences':native['caps']['inference']-native['counts']['inference']},
        validations={'regression':{'passed':60,'tool_session':69749,'command':'pytest common-core-slices common-support ict-rules conference english-primary public-hybrid-advanced public-knowledge; workspace basetemp04'},
            'additional_comparison_tests':{'passed':7,'tool_session':39595,'scope':'Core comparison tests after ready31 Vietnamese wording; overlaps6of prior60, do not sum as67unique tests.'},
            'real_queries':20,'probe_scope':'18selectedprobesonready30,2graduationprobesonready31. No claim all20rerunon31 or fullcorpusansweracceptance.',
            'full_verification':{'receipt':p.rel(verification),'original_pdfs':verified['verified_original_pdfs'],'page_pairs':verified['verified_page_pairs'],
                                 'reviewed_curricula':verified['reviewed_documents_reconciled']},
            'failed_evidence_preserved':['20261022T144726675091Z-retrieval-source-probes.json','20261022T150500873930Z-retrieval-source-probes.json','20261022T151714532015Z-retrieval-source-probes.json'],
            'stalled_sandbox_test':'Owned pytest process5532was verified by exact command and stopped after stalling in basetemp01; files retained. Elevated rerun basetemp02/03/04passed.'},
        common_support_bundle=p.rel(p.BASE/'common-support-review-bundle-20261022-71.json'),
        common_core_audit=p.rel(p.BASE/'common-core-source-audit-20261022-74.json'),
        ict_rule_bundle=p.rel(p.BASE/'ict-rules-review-bundle-20261022-78.json'),
        renderer={'status':'not_available_in_bundled_runtime','layout_verified':False,
            'evidence':'load_workspace_dependencies returned no LibreOffice; native executable manifest lists only image/Poppler tools; rgfiles over bundlednative found no soffice/libreoffice. Prior failedrender evidence retained. No install outsideworkspace,noACLchange,no cleanup.'},
        next_priority='Continue common handbook and training regulations full page review, find referenced appendices1/2/4/5, and verify current registration/graduation notices. Preserve source conflict about handbook31andQĐ94/Điều13. Resolve DOCXlayoutonlywith authorized workspace renderer. Continue remaining FIT60candidate bodies after existing source questions; TTCNTT HTML uses different article container and FIT giáo-vụ body includes embeddedCSS, so do not feed either through current Article parser without scoped review. Other-major-specific sources deferred; keep all originaldata/history. Native inference cap unchanged and nearly reached; inspect exact remaining headroom before any further model work.')
    target=p.BASE/'it-common-priority-20261022-81.json';p.save(target,priority)
    p.event('ready31-delivery-verified',{'priority':p.rel(target),'catalog':p.rel(p.CATALOG),'ready':ready,'probes':probes,
        'health':health.json(),'backend_pid':10872,'native_counts':native['counts'],'generation_calls':0,'whole_catalog_complete':False})
    p.checkpoint(None)
    folder=p.checked(p.ROOT/'.tooling/huce-document-pipeline-20261022-10');folder.mkdir(exist_ok=False)
    file=p.checked(folder/'CHECKPOINT-IT-COMMON-v31.md')
    text=f'''# Bàn giao CNTT và tài liệu chung sau ready31

Ưu tiên của người dùng: tài liệu CNTT và tài liệu chung; tài liệu riêng ngành khác tạm hoãn. Chưa hoàn tất toàn bộ phạm vi. Giữ nguyên bản gốc, quan sát cũ, lịch sử, ngân sách và kiểm soát bảo vệ.

## Trạng thái đã kiểm chứng

- Catalog v11: 2.193 định danh nguồn, 15 complete, 2.056 incomplete, 122 blocked. Thêm 7 định danh; hai Drive ID hỗ trợ học phí có cùng payload vẫn được giữ riêng.
- Ready31: fingerprint 5d0cc896e688d54210154d1c0a83787740ae19ad8a174457eda4e83dc6d12093; 1.009 đoạn đang dùng, 2.830 vector, 531 dòng lịch sử.
- Ready28/29/30/31 lần lượt thêm 49/50/2/1 đoạn. Đoạn sổ tay 31 gốc và đoạn đối chiếu ở release30 được giữ trong lịch sử có thể đọc lại.
- 60 kiểm thử hồi quy đạt. Sau bổ sung tiếng Việt ở release31, 7 kiểm thử đối chiếu đạt; có 6 kiểm thử trùng với bộ60, không cộng thành67 kiểm thử độc lập.
- 20 truy vấn thực đạt: 8 hỗ trợ học phí, 4 nội quy/CNTT, 6 hồi quy hội nghị trên ready30; 2 truy vấn tốt nghiệp trên ready31. Không khẳng định cả20 đã chạy trên31 hoặc mọi câu trả lời sinh ra đã được kiểm chứng.
- Full verifier sau31 đạt: 84 PDF gốc, 133 cặp trang, 42 hồ sơ rà soát chương trình đào tạo; kiểm tra release14–31, lịch sử, 5 hồ sơ sai và các release8–13 đã withdrawn. Receipt và SHA nằm trong priority81.

## Runtime

Backend đúng là scripts/campus_backend.py, PID10872, tool session43384, cổng8006 trả health200. Dùng cùng SQLite ở .tooling/campus-single-entry-20261015-01/runtime và cùng gateway/lịch sử. retained_live/accounting_only có sẵn từ trước; không thay ngân sách hoặc kiểm soát. Không có cuộc gọi sinh trả lời trả phí trong công việc này.

Health không trả fingerprint. Ready31 là bản mới nhất trước khi backend khởi động, và constructor dùng latest-ready. Một lần thử nhầm run_advanced_rag.py bị UNAUTHORIZED_CAP; không sửa hoặc vượt bộ kiểm soát, đã chuyển về đúng campus_backend.

BGE worker18548, tool session43865, namespace infra/local/rag-advanced-models-20261013-16, kế thừa bộ đếm/caps của15. Trần10.000 native inferences không đổi; còn {priority['native_runtime']['remaining_native_inferences']} tại thời điểm checkpoint. Đọc snapshot mới trước mọi việc dùng mô hình; không reset, cleanup hay tự tăng trần.

## Hỗ trợ học phí

Bundle71 có hai HTML công bố, hai định danh Drive PDF dùng chung payload5 trang và ba mẫu đơn chưa điền. Đã xem lại toàn bộ5 ảnh; mỗi PDF có17 mục phụ lục với điều kiện, giấy tờ, ghi chú và kế thừa ô gộp được đối chiếu theo cột và hình học PDF.

Giữ đúng các mức100/70/50%, các ngoại lệ ở II.1 và ô ghi chú trống ở II.2. Không tự thêm điều kiện hộ nghèo cho II.2. Hạn29/09–20/10/2026 đã qua tại22/10/2026.

Các khác biệt chưa giải quyết: thông báo dẫn238/2025, mẫu cũ dẫn81/2021; Lô Lô/Lô Tô; “hoặc” trong phụ lục so với “và” ở mẫu hộ nghèo/cận nghèo; cử tuyển so với chương trình/đề án; yêu cầu hộ khẩu/giấy khai sinh trong mẫu. Không tự xác nhận hiệu lực mẫu cũ.

Bố cục Word chưa kiểm chứng: bundled runtime không có LibreOffice/soffice. Giữ DOCX gốc, XML và bằng chứng render thất bại. Không cài ngoài workspace, đổi ACL hay dọn tệp. Chỉ tiếp tục render khi xác minh được renderer trong phạm vi cho phép.

## Sổ tay và quy chế chung

Audit74 gắn với năm trang sổ tay26/30/31/49/55, sáu trang quy chế1/2/9/10/18/19 và hai ảnh học phí924. Pixel render2.5 đã khớp bản PDF gốc. Chưa đọc lại toàn bộ116 trang sổ tay và26 trang quy chế.

Catalog bổ sung verified_metadata về phạm vi1486 và ngày ký924 là10/06/2026. Giữ ngày15/08 cũ trong quan sát lịch sử. Đây là đối chiếu nguồn, không phải xác nhận pháp lý hiện hành.

Sổ tay31 ghi khối đại cương bị điểm F ở ngưỡng≥5% và thêm mốc thời gian chuẩn>45 ngày. Điều13.3 quy chế ghi học phần phải học lại vượt quá5% tổng tín chỉ toàn chương trình, áp dụng giảm hạng xuất sắc/giỏi. Mốc45 ngày làm việc là thời hạn công nhận/cấp bằng sau khi đủ điều kiện và hoàn thành nghĩa vụ.

Release31 bổ sung đối chiếu tiếng Việt đủ phạm vi và dấu ngưỡng. Ngoại ngữ ở sổ tay31 không thay QĐ94 áp dụng từK70. Phụ lục quy trình1/2/4/5 được1486 dẫn còn cần tìm và kiểm chứng riêng.

## Hai nguồn CNTT mới

Receipt: it-english-acquisition-20261022T145232183582Z.json. Bundle78 giữ toàn bộ19 ảnh và văn bản đã đọc.

- Quyết định2114 ngày31/12/2024, Drive18p4WnkILh7N86o2h8kEVxyAMmYNW0Lhy:17 trang và19 điều, giữ các phần nối qua trang.
- Nội quy phòng máy, Drive17fHGSp05BTd0tp2qwJKtX_wdO6ykJu1G:2 trang và12 khoản. OCR gốc ở76, bản đọc tay ở77. Ngày ký đọc là09/4/2024; số quyết định viết tay chưa chắc chắn, không gán theo OCR.

Điều17 của2114 đánh số4 hai lần. Một số căn cứ/ngày và mô tảTier2 cần nguồn pháp luật/tiêu chuẩn riêng; không tự coi cách diễn giải trong văn bản là chuẩn bên ngoài. Không thực thi các thao tác quản trị/xóa dữ liệu được nguồn mô tả.

## Tiếp tục

Đọc priority81 và machine checkpoint mới nhất. Tiếp tục toàn bộ sổ tay, quy chế và phụ lục, thông báo đăng ký học/tốt nghiệp thực tế, rồi những body FIT còn thiếu; giữ các câu hỏi cũ về CTĐT và ngoại ngữ.

HTML TTCNTT không dùng post-content-area; body giáo vụ FIT có CSS nhúng. Chưa chuẩn hóa/index các HTML này bằng parser hiện tại. Không làm lại bộ hội nghị nếu không có bằng chứng lỗi mới. Không dùng subagent; không điền/gửi đơn hoặc nhắn ra ngoài.
'''
    with file.open('x',encoding='utf8') as stream:stream.write(text)
    print(json.dumps({'priority':p.rel(target),'checkpoint':p.rel(file),'full_verification':p.rel(verification),
                      'remaining_native_inferences':priority['native_runtime']['remaining_native_inferences']}))


if __name__=='__main__':main()
