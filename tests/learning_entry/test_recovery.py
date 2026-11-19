"""Recovery always targets a new path and preserves original stores and snapshots."""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from campus247.bootstrap.learning import load_local_learning
from campus247.domain.shared.values import generate_uuid7
from learning_local_setup import setup
from learning_snapshot import restore, snapshot, verify


def test_snapshot_restore_hashes_state_identity_and_rejects_existing_destinations(tmp_path):
    if not tmp_path.resolve().is_relative_to(ROOT):
        raise ValueError('Explicit workspace basetemp required')
    runtime = tmp_path / 'runtime'
    setup(runtime, 'recovery-test')
    identity_hash = hashlib.sha256((runtime / 'identity.json').read_bytes()).digest()
    credentials = json.loads((runtime / 'credentials.json').read_text(encoding='utf-8'))['accounts'][0]
    blob_id, key = generate_uuid7(), generate_uuid7() + '.pdf'
    data = b'%PDF-1.4\nsynthetic recovery bytes'
    (runtime / 'blobs' / key).write_bytes(data)
    with sqlite3.connect(runtime / 'learning.sqlite3') as db:
        state = json.loads(db.execute('SELECT payload FROM learning_state').fetchone()[0])
        state['blobs'][blob_id] = {'id': blob_id, 'storage_key': key, 'sha256': hashlib.sha256(data).hexdigest(), 'byte_size': len(data)}
        state['versions']['legacy-synthetic-version'] = {'storage_key': key, 'sha256': hashlib.sha256(data).hexdigest(), 'byte_size': len(data)}
        state['reader_states']['synthetic-reader'] = {'page_no': 3, 'revision': 2}
        state['bookmarks']['synthetic-bookmark'] = {'page_no': 2, 'label': 'Preserve bookmark'}
        db.execute('UPDATE learning_state SET payload=? WHERE tenant_id=?', (json.dumps(state), 'recovery-test'))
    original_hash = hashlib.sha256((runtime / 'learning.sqlite3').read_bytes()).hexdigest()
    backup = tmp_path / 'snapshot'
    assert snapshot(runtime / 'config.json', backup)['blob_count'] == 1
    recovered = tmp_path / 'recovered'
    assert restore(backup, recovered)['status'] == 'verified'
    _service, adapter = load_local_learning(recovered / 'config.json', workspace=ROOT, tenant_id='recovery-test')
    token = adapter.authenticate(credentials['username'], credentials['password'])
    assert adapter.resolve_token(token).subject_id == credentials['subject_id']
    assert hashlib.sha256((recovered / 'identity.json').read_bytes()).digest() == identity_hash
    with sqlite3.connect(recovered / 'learning.sqlite3') as db:
        assert json.loads(db.execute('SELECT payload FROM learning_state').fetchone()[0]) == state
    assert hashlib.sha256((runtime / 'learning.sqlite3').read_bytes()).hexdigest() == original_hash
    assert (recovered / 'blobs' / key).read_bytes() == data
    assert not (backup / 'credentials.json').exists()
    with pytest.raises(ValueError, match='NEW'):
        restore(backup, runtime)
    with pytest.raises(ValueError, match='NEW'):
        snapshot(runtime / 'config.json', backup)
    # Only corrupt newly created test evidence, never a user store.
    with (recovered / 'blobs' / key).open('r+b') as stream:
        stream.write(b'!')
    with pytest.raises(ValueError, match='checksum'):
        verify(recovered)
