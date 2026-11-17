"""Make the reviewed handbook/rule difference explicit in Vietnamese, retaining release30."""
import copy
import huce_document_pipeline as p
from huce_common_source_slices import normalize,validate_release
from huce_public_document_pipeline import chunks


def main():
    p.event('preflight',p.preflight())
    prior=p.read(p.PUB/'reviewed-corrections-20261021-v30.json');old=validate_release(prior,prior['pipeline_coverage'][0])
    d=copy.deepcopy(old['review_dossier'])
    text=('Đối chiếu sổ tay trang31 với Quy chế1486 Điều13.3, PDF18–19: '
          'Sổ tay ghi “Môn học khối kiến thức giáo dục đại cương ≥ 5% số tín chỉ bị điểm F” (ngưỡng ≥5%). '
          'Quy chế ghi khối lượng các học phần phải học lại “vượt quá 5% so với tổng số tín chỉ quy định cho toàn chương trình” '
          '(ngưỡng vượt quá5%), áp dụng việc giảm một mức hạng tốt nghiệp của sinh viên có điểm trung bình tích lũy loại xuất sắc và giỏi; '
          'trường hợp còn lại là sinh viên đã bị kỷ luật từ mức cảnh cáo trở lên trong thời gian học. '
          'Hai nguồn khác cả phạm vi khối học phần, cách tính và dấu ngưỡng; không tự đổi ≥ thành > hoặc áp quy tắc cho mọi hạng tốt nghiệp. '
          'Mốc45 ngày làm việc trong Điều13.2 là thời hạn ra quyết định công nhận và cấp bằng, tính từ khi đáp ứng đầy đủ điều kiện tốt nghiệp '
          'và hoàn thành nghĩa vụ với Trường; không tự coi đó là thời gian được kéo dài học hay quy tắc hạ hạng. '
          'Chưa có bản đính chính khác biệt này trong bộ nguồn đã đọc.')
    d.update(reviewed_comparison_vi=text,reviewed_comparison_vi_sha256=p.sha(text.encode()),comparison_reviewed_against_images=True,
             replaces_excerpt_text_sha256=prior['chunks'][0]['text_sha256'])
    record=normalize(d);file=p.checked(p.BASE/'document-reviews'/f'{p.stamp()}-common-handbook-comparison-vi.json');p.save(file,record)
    at=p.now();coverage=dict(prior['pipeline_coverage'][0],review_file=p.rel(file))
    release={'public_only':True,'acquired_at':at,'version_label':'reviewed-corrections-20261021-v31',
             'verification':'source_verified_excerpts','chunks':chunks(record,at),'pipeline_coverage':[coverage]}
    validate_release(release,coverage)
    target=p.PUB/'reviewed-corrections-20261021-v31.json';p.save(target,release)
    p.event('common-comparison-vi-published',{'release':p.rel(target),'replaced_excerpt':prior['chunks'][0]['text_sha256'],
             'original_source_unchanged':True,'earlier_comparison_retained_in_history':True,'generation_calls':0})
    print(p.rel(target))


if __name__=='__main__':main()
