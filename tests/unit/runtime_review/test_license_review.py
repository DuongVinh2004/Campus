"""Reject malformed public archive input without filesystem extraction or execution."""
import gzip
import importlib.util
import io
import lzma
from pathlib import Path
import sys
import tarfile

import pytest

HERE = Path(__file__).resolve().parents[3] / "infra/local/rag-fixture"
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("runtime_license_review", HERE / "runtime_license_review_20261004.py")
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:") as output:
        for name, data, kind in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(data) if kind == tarfile.REGTYPE else 0
            info.linkname = "outside" if kind == tarfile.SYMTYPE else ""
            output.addfile(info, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
    return lzma.compress(stream.getvalue())


def deb(members):
    raw = b"!<arch>\n"
    for name, data in members:
        header = (name + "/").ljust(16) + "0".ljust(12) + "0".ljust(6) + "0".ljust(6) + "100644".ljust(8) + str(len(data)).ljust(10) + "`\n"
        raw += header.encode() + data + (b"\n" if len(data) % 2 else b"")
    return raw


def test_index_accepts_filename_first_and_blank_separator():
    raw = gzip.compress(b"Package: a\nVersion: 1\n\n\nFilename: pool/b.deb\nPackage: b\nVersion: 2\n\n")
    assert [p["Package"] for p in review.package_index(raw)] == ["a", "b"]


def test_only_regular_license_documents_are_returned():
    raw = archive([("./opt/mkl/licensing/license.txt", b"license", tarfile.REGTYPE),
                   ("./opt/mkl/bin/vars.sh", b"do not execute", tarfile.REGTYPE)])
    inventory, documents = review.document_members(raw)
    assert len(inventory) == 2 and documents == {"opt/mkl/licensing/license.txt": b"license"}


@pytest.mark.parametrize("name,kind", [("../licensing/file.txt", tarfile.REGTYPE),
                                        ("/opt/licensing/file.txt", tarfile.REGTYPE),
                                        ("opt/licensing/file.txt", tarfile.SYMTYPE)])
def test_unsafe_document_rejected(name, kind):
    with pytest.raises(AssertionError):
        review.document_members(archive([(name, b"content", kind)]))


def test_duplicate_tar_document_rejected():
    entry = ("licensing/license.txt", b"content", tarfile.REGTYPE)
    with pytest.raises(AssertionError, match="duplicate"):
        review.document_members(archive([entry, entry]))


def test_unreviewed_non_utf8_document_rejected():
    with pytest.raises(UnicodeDecodeError):
        review.document_members(archive([("licensing/new.txt", b"\xa7", tarfile.REGTYPE)]))


def test_expansion_and_concatenated_stream_rejected():
    with pytest.raises(AssertionError, match="bound"):
        review.bounded_xz(lzma.compress(b"x" * 100), bound=99)
    with pytest.raises(AssertionError, match="bound"):
        review.bounded_xz(lzma.compress(b"x") + lzma.compress(b"y"))


def test_signed_deb_layout_and_truncation():
    raw = deb([("debian-binary", b"2.0\n"), ("control.tar.xz", b"control"),
               ("data.tar.xz", b"data"), ("_gpgorigin", b"signature")])
    assert review.ar_members(raw)["_gpgorigin"] == b"signature"
    with pytest.raises(AssertionError):
        review.ar_members(raw[:-1])


def test_duplicate_ar_member_rejected():
    raw = deb([("debian-binary", b"2.0\n"), ("debian-binary", b"2.0\n")])
    with pytest.raises(AssertionError, match="ambiguous"):
        review.ar_members(raw)
