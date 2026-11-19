"""Balanced view preserves originals, page contents and inherited attributes."""
import hashlib
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject
import pytest

from campus247.infrastructure.learning.pdf_layout import balanced_view

ROOT = Path(__file__).resolve().parents[3]


def fixture(tmp_path, *, pages=33, signed=False):
    if not tmp_path.resolve().is_relative_to(ROOT):
        raise RuntimeError('Use a new --basetemp within the workspace')
    path = tmp_path / 'source.pdf'
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if signed:
        field = writer._add_object(DictionaryObject({NameObject('/FT'): NameObject('/Sig'), NameObject('/T'): TextStringObject('Signature')}))
        writer._root_object[NameObject('/AcroForm')] = DictionaryObject({NameObject('/Fields'): ArrayObject([field])})
    with path.open('xb') as output:
        writer.write(output)
    return path


def test_balances_metadata_and_preserves_source_bytes(tmp_path):
    source = fixture(tmp_path)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    target = tmp_path / 'view.pdf'
    result = balanced_view(source, target, ROOT)
    assert result['optimized'] and result['verified_page_drawing_operators'] == 33
    reader = PdfReader(target)
    children = reader.trailer['/Root']['/Pages']['/Kids']
    assert len(children) == 3 and all(child.get_object()['/Type'] == '/Pages' for child in children)
    assert len(reader.pages) == 33
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_signature_fields_keep_original_view(tmp_path):
    source = fixture(tmp_path, signed=True)
    target = tmp_path / 'view.pdf'
    result = balanced_view(source, target, ROOT)
    assert result == {'optimized': False, 'reason': 'SIGNED_PDF'}
    assert not target.exists()


def test_never_overwrites_an_existing_destination(tmp_path):
    source = fixture(tmp_path)
    target = tmp_path / 'retained.pdf'
    target.write_bytes(b'retained work')
    with pytest.raises(FileExistsError):
        balanced_view(source, target, ROOT)
    assert target.read_bytes() == b'retained work'


def test_small_documents_need_no_derivative(tmp_path):
    source = fixture(tmp_path, pages=3)
    assert balanced_view(source, tmp_path / 'view.pdf', ROOT)['reason'] == 'SMALL_PAGE_TREE'
