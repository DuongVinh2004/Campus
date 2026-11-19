from campus247.application.retrieval.material_support import support_issues

SOURCE = "Sinh viên được đăng ký từ năm thứ hai. Tại thời điểm đăng ký, sinh viên phải đáp ứng 01 trong 02 điều kiện sau và các điều kiện khác của cơ sở đào tạo: a) Học lực khá và đáp ứng ngưỡng bảo đảm chất lượng; b) Học lực trung bình và đáp ứng điều kiện trúng tuyển."


def test_two_listed_options_do_not_eliminate_the_printed_additional_conditions():
    claim = "Tại thời điểm đăng ký, sinh viên phải đáp ứng 01 trong 02 điều kiện: học lực khá và đáp ứng ngưỡng bảo đảm chất lượng."
    assert "MISSING_MATERIAL_CONDITION" in support_issues(claim, SOURCE)
    complete = "Tại thời điểm đăng ký, sinh viên phải đáp ứng 01 trong 02 điều kiện sau và các điều kiện khác của cơ sở đào tạo."
    assert "MISSING_MATERIAL_CONDITION" not in support_issues(complete, SOURCE)
    assert "MISSING_MATERIAL_CONDITION" not in support_issues("Sinh viên được đăng ký từ năm thứ hai.", SOURCE)
