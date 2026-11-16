"""Build a separate balanced page-tree PDF without changing lecture content or originals."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject


def balanced_view(source: Path, destination: Path, workspace: Path):
    workspace = workspace.resolve(strict=True)
    for path in (source, destination):
        if not path.is_absolute() or '..' in path.parts or not path.resolve().is_relative_to(workspace):
            raise ValueError('PDF view paths must be explicit workspace paths')
        for parent in (path, *path.parents):
            if parent.is_symlink() or getattr(parent, 'is_junction', lambda: False)():
                raise ValueError('PDF view reparse points are not supported')
            if parent == workspace:
                break
    if destination.exists():
        raise FileExistsError('PDF view destination must be new')
    with source.open('rb') as stream:
        before = hashlib.file_digest(stream, 'sha256').hexdigest()
    reader = PdfReader(source, strict=True)
    if reader.is_encrypted:
        raise ValueError('Encrypted PDF is not supported')
    if reader.trailer['/Root'].get('/Perms') or any(field.get('/FT') == '/Sig' for field in (reader.get_fields() or {}).values()):
        return {'optimized': False, 'reason': 'SIGNED_PDF'}
    count = len(reader.pages)
    if not 0 < count <= 500:
        raise ValueError('PDF page count is outside supported limits')
    if count <= 16:
        return {'optimized': False, 'reason': 'SMALL_PAGE_TREE'}
    writer = PdfWriter(clone_from=reader)
    pages = list(writer.pages)
    root_ref = writer._root_object.raw_get('/Pages')
    root = root_ref.get_object()
    # Materialize inherited page attributes before changing parent nodes.
    for page in pages:
        for key in ('/Resources', '/MediaBox', '/CropBox', '/Rotate'):
            if key in page:
                continue
            parent = page
            visited = set()
            while key not in parent and parent.get('/Parent') is not None:
                identity = id(parent)
                if identity in visited or len(visited) >= 128:
                    raise ValueError('Cyclic or excessive page inheritance')
                visited.add(identity)
                parent = parent['/Parent']
            if key in parent:
                page[NameObject(key)] = parent.raw_get(key)
    children = ArrayObject()
    for offset in range(0, count, 16):
        group = pages[offset:offset + 16]
        branch = DictionaryObject({NameObject('/Type'): NameObject('/Pages'),
            NameObject('/Parent'): root_ref, NameObject('/Count'): NumberObject(len(group)),
            NameObject('/Kids'): ArrayObject([page.indirect_reference for page in group])})
        branch_ref = writer._add_object(branch)
        children.append(branch_ref)
        for page in group:
            page[NameObject('/Parent')] = branch_ref
    root[NameObject('/Kids')] = children
    root[NameObject('/Count')] = NumberObject(count)
    with destination.open('xb') as output:
        writer.write(output)
    equivalent = PdfReader(destination, strict=True)
    if len(equivalent.pages) != count:
        raise ValueError('PDF view page count mismatch')
    for original, view in zip(reader.pages, equivalent.pages):
        if list(original.mediabox) != list(view.mediabox) or list(original.cropbox) != list(view.cropbox) or original.rotation != view.rotation:
            raise ValueError('PDF view page geometry mismatch')
        if original.extract_text() != view.extract_text():
            raise ValueError('PDF view text mismatch')
        old_content, new_content = original.get_contents(), view.get_contents()
        if (old_content.get_data() if old_content else b'') != (new_content.get_data() if new_content else b''):
            raise ValueError('PDF view drawing operators mismatch')
    with source.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != before:
            raise ValueError('PDF source changed during view generation')
    with destination.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'optimized': True, 'page_count': count, 'source_sha256': before, 'sha256': digest,
        'byte_size': destination.stat().st_size, 'verified_page_text': count,
        'verified_page_drawing_operators': count, 'page_tree_fanout': 16}


if __name__ == '__main__':
    print(json.dumps(balanced_view(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))))
