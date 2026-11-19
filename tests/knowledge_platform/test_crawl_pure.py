"""Pure crawler modules: HTML text, DOCX text, personal-data filter, URL rules, robots, sitemap. No network, no DB."""
import io
import zipfile

import pytest

from campus247.application.knowledge.crawl.docx_text import DocxError, docx_to_text
from campus247.application.knowledge.crawl.html_text import extract_page
from campus247.application.knowledge.crawl.pii import scan_personal_data
from campus247.application.knowledge.crawl.rules import RobotsPolicy, classify, normalize_url, parse_sitemap, wanted

ARTICLE = """<!doctype html><html><head><title>Thông báo nộp học phí học kỳ 1 - Trường Đại học Xây dựng Hà Nội</title>
<meta property="article:published_time" content="2026-09-01T08:00:00+07:00"><script>var tracker = 1;</script></head>
<body><header><a href="/">Trang chủ</a><a href="/gioi-thieu">Giới thiệu</a></header>
<nav><ul><li><a href="/tin-tuc">Tin tức</a></li><li><a href="/dao-tao">Đào tạo</a></li></ul></nav>
<div class="page"><article class="post-content"><h1>Thông báo nộp học phí học kỳ 1 năm học 2026-2027</h1>
<p>Phòng Kế hoạch - Tài chính thông báo sinh viên nộp học phí học kỳ 1 trước ngày 15/10/2026 qua ngân hàng hoặc cổng thanh toán của Trường.</p>
<p>Sinh viên nộp muộn sẽ bị xử lý theo quy định hiện hành của Nhà trường và có thể bị tạm dừng đăng ký học phần của học kỳ tiếp theo.</p>
<table><tr><th>Hệ đào tạo</th><th>Mức thu</th></tr><tr><td>Đại học chính quy</td><td>420.000 đồng/tín chỉ</td></tr></table>
<p>Tệp đính kèm: <a href="/files/huong-dan-nop-hoc-phi.pdf">Hướng dẫn nộp học phí (PDF)</a> và <a href="/files/mau-don.docx">Mẫu đơn</a>.</p>
</article></div><footer><p>© Trường Đại học Xây dựng Hà Nội</p><a href="/lien-he">Liên hệ</a></footer></body></html>"""

LISTING = """<html><body><nav><a href="/a">A</a></nav><main><ul>""" + "".join(
    f'<li><a href="/tin-tuc/bai-{i}">Tiêu đề bài viết số {i}</a></li>' for i in range(30)) + "</ul></main></body></html>"


def test_article_keeps_the_main_text_and_drops_menus_scripts_and_footers():
    page = extract_page(ARTICLE, "https://huce.edu.vn/thong-bao/hoc-phi")
    assert page.title == "Thông báo nộp học phí học kỳ 1 năm học 2026-2027"
    assert "trước ngày 15/10/2026" in page.text and "420.000 đồng/tín chỉ" in page.text
    assert "Đại học chính quy | 420.000" in page.text           # table rows keep their cells together
    for noise in ("Trang chủ", "Giới thiệu", "Tin tức", "tracker", "© Trường"):
        assert noise not in page.text
    assert page.published_at is not None and page.published_at.year == 2026 and page.published_at.month == 9
    assert "https://huce.edu.vn/files/huong-dan-nop-hoc-phi.pdf" in page.links and "https://huce.edu.vn/files/mau-don.docx" in page.links
    assert page.link_density < 0.4


def test_listing_page_has_high_link_density_so_it_is_not_treated_as_a_document():
    page = extract_page(LISTING, "https://huce.edu.vn/tin-tuc")
    assert page.link_density > 0.8 and len(page.links) >= 30


def test_unclosed_tags_and_legacy_encoding_do_not_break_extraction():
    html = "<html><body><div class='content'><p>Đoạn một<p>Đoạn hai</div></body></html>".encode("cp1258", "ignore")
    page = extract_page(html, "https://huce.edu.vn/x")
    assert "Đoạn" in page.text or page.text  # decoded without raising


def make_docx(body_xml):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                         + body_xml + "</w:body></w:document>")
    return buffer.getvalue()


def test_docx_paragraphs_and_tables_in_order():
    data = make_docx('<w:p><w:r><w:t>Quy định về đồ án</w:t></w:r></w:p>'
                     '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Học phần</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Tín chỉ</w:t></w:r></w:p></w:tc></w:tr>'
                     '<w:tr><w:tc><w:p><w:r><w:t>Đồ án tốt nghiệp</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>7</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
                     '<w:p><w:r><w:t>Hết.</w:t></w:r></w:p>')
    assert docx_to_text(data).splitlines() == ["Quy định về đồ án", "Học phần | Tín chỉ", "Đồ án tốt nghiệp | 7", "Hết."]


@pytest.mark.parametrize("data,code", [(b"not a zip", "DOCX_NOT_A_ZIP"), (b"", "DOCX_NOT_A_ZIP")])
def test_docx_rejects_bad_input(data, code):
    with pytest.raises(DocxError, match=code):
        docx_to_text(data)


def test_docx_without_document_xml_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("other.txt", "x")
    with pytest.raises(DocxError, match="DOCX_WITHOUT_DOCUMENT"):
        docx_to_text(buffer.getvalue())


STUDENT_LIST = "Danh sách sinh viên đủ điều kiện\nSTT | Mã sinh viên | Họ và tên | Ngày sinh\n" + "\n".join(
    f"{i} | 12{i:05d} | Nguyễn Văn An{chr(65 + i)} | 01/02/2004" for i in range(1, 9))


def test_person_lists_identity_numbers_and_contact_dumps_are_blocked():
    assert any(f.kind == "PERSON_LIST" for f in scan_personal_data(STUDENT_LIST))
    assert any(f.kind == "IDENTITY_NUMBER" for f in scan_personal_data("Số CCCD của thí sinh: 001204012345"))
    phones = "\n".join(f"Liên hệ 09{i:08d}" for i in range(10))
    assert any(f.kind == "PHONE_LIST" for f in scan_personal_data(phones))
    emails = "\n".join(f"nguoi{i}@gmail.com" for i in range(6))
    assert any(f.kind == "PERSONAL_EMAIL_LIST" for f in scan_personal_data(emails))


def test_ordinary_school_text_is_not_blocked():
    text = ("Thông báo học phí\nPhòng Đào tạo: 024 3869 1234, email daotao@huce.edu.vn\nHọc phần | Tín chỉ | Học kỳ\nGiải tích 1 | 3 | 1\n"
            "Đại học chính quy | 420.000 đồng/tín chỉ\nHạn nộp 15/10/2026")
    assert scan_personal_data(text) == []
    assert scan_personal_data(extract_page(ARTICLE, "https://huce.edu.vn/x").text) == []


def test_url_normalization_keeps_only_allowed_https_school_urls():
    assert normalize_url("https://HUCE.edu.vn//a//b?utm_source=x&id=2&fbclid=1#top") == "https://huce.edu.vn/a/b?id=2"
    assert normalize_url("https://ttcntt.huce.edu.vn/trang") == "https://ttcntt.huce.edu.vn/trang"
    for bad in ("http://huce.edu.vn/a", "https://example.com/a", "https://huce.edu.vn.evil.com/a", "https://user:pw@huce.edu.vn/a",
                "https://huce.edu.vn:8443/a", "ftp://huce.edu.vn/a", "https://evilhuce.edu.vn/a"):
        assert normalize_url(bad) is None, bad


def test_classification_and_include_exclude_rules():
    assert classify("https://huce.edu.vn/files/a.pdf") == "document" and classify("https://huce.edu.vn/f/b.DOCX") == "document"
    assert classify("https://huce.edu.vn/f/old.doc") == "unsupported_document"
    assert classify("https://huce.edu.vn/images/a.png") == "skip" and classify("https://huce.edu.vn/dang-nhap") == "skip"
    assert classify("https://huce.edu.vn/thong-bao/hoc-phi") == "page"
    assert wanted("https://huce.edu.vn/thong-bao/a", [r"^/thong-bao/"], []) and not wanted("https://huce.edu.vn/tin-tuc/a", [r"^/thong-bao/"], [])
    assert not wanted("https://huce.edu.vn/thong-bao/a?page=9", [r"^/thong-bao/"], [r"page=\d+"])


def test_robots_policy_modes():
    rules = RobotsPolicy("User-agent: *\nDisallow: /private/\nCrawl-delay: 7\nSitemap: https://huce.edu.vn/sitemap.xml\n")
    assert rules.can_fetch("https://huce.edu.vn/thong-bao/a") and not rules.can_fetch("https://huce.edu.vn/private/x")
    assert rules.delay(3.0) == 7.0 and RobotsPolicy("User-agent: *\n").delay(3.0) == 3.0
    assert rules.sitemaps() == ["https://huce.edu.vn/sitemap.xml"]
    assert RobotsPolicy.absent().can_fetch("https://huce.edu.vn/anything")
    assert not RobotsPolicy.unreadable().can_fetch("https://huce.edu.vn/anything")
    ours = RobotsPolicy("User-agent: Campus247-KnowledgeBot\nDisallow: /\n")
    assert not ours.can_fetch("https://huce.edu.vn/thong-bao/a")


def test_sitemap_and_index_parsing_and_hostile_input():
    pages, nested = parse_sitemap(b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://huce.edu.vn/a</loc></url>'
                                  b'<url><loc> https://huce.edu.vn/b </loc></url></urlset>')
    assert pages == ["https://huce.edu.vn/a", "https://huce.edu.vn/b"] and nested == []
    pages, nested = parse_sitemap(b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://huce.edu.vn/s1.xml</loc></sitemap></sitemapindex>')
    assert pages == [] and nested == ["https://huce.edu.vn/s1.xml"]
    assert parse_sitemap(b"<not xml") == ([], [])
