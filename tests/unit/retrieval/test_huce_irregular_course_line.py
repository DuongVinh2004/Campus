"""A missing separator may be repaired without inventing a code or credits."""
import copy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
import huce_document_pipeline as pipeline


def actual():
    did='1I1BwlDMeWLqyosnMojP2pOn832XHXQDc'
    return next(i for i in pipeline.items() if i['drive_id']==did),copy.deepcopy(pipeline.latest_reviews()[did][1]['review_dossier'])


def test_actual_missing_separator_remains_bound_to_original_numbers():
    item,dossier=actual()
    record=pipeline.normalize(item,dossier)
    course=next(c for c in record['courses'] if c['code']=='361464')
    assert course['credits']==2 and course['code_credit_source_line']=='361464 2'
    assert course['name_verbatim']=='Kinh tế xây dựng và\nnghiệp vụ đấu thầu'
    english=next(c for c in record['courses'] if c['code']=='446604')
    assert english['name_verbatim']=='Anh ngữ 4'
    assert any('361464 2' in r['text'] for r in record['full_semester_regions'])


@pytest.mark.parametrize('field,value',[('code','999999'),('credits',9),('source_line','361464 9')])
def test_separator_repair_cannot_change_a_printed_value(field,value):
    item,dossier=actual()
    dossier['reviewed_code_line_variants'][0][field]=value
    with pytest.raises(AssertionError):
        pipeline.normalize(item,dossier)
