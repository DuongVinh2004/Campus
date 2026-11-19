from uuid import UUID

import pytest

from campus247.infrastructure.knowledge import storage as module
from .conftest import ROOT


def test_restored_storage_reads_originals_and_appends_to_new_namespace(monkeypatch, retained_directory):
    original = module.FileKnowledgeStorage(ROOT, retained_directory / "retained")
    artifact = original.write_json(b'{"retained":"source"}', "fixture")
    restored = module.ReadThroughKnowledgeStorage(ROOT, retained_directory / "new", original.root)
    assert restored.read(artifact.__dict__) == b'{"retained":"source"}'
    fresh = restored.write_json(b'{"new":"observation"}', "fixture")
    assert restored.path(fresh.object_key).parent == restored.root
    assert restored.path(artifact.object_key).parent == original.root
    monkeypatch.setattr(module, "uuid4", lambda: UUID(artifact.id))
    with pytest.raises(FileExistsError):
        restored.write_json(b"must never overwrite a retained artifact", "collision-test")
    assert original.read(artifact.__dict__) == b'{"retained":"source"}'
