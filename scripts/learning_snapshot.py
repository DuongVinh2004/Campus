"""Snapshot and recover an explicitly configured synthetic SQLite store into NEW paths only.

The online SQLite backup API captures metadata consistently. Immutable referenced
blobs and the hashed-account identity store are copied with checksum verification.
No live store, old snapshot, credential export or recovery file is ever replaced.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/api/src'))
from campus247.bootstrap.learning import checked_learning_path


def new_directory(path: Path):
    path = Path(path).absolute()
    if '..' in path.parts or path.exists() or path == ROOT or not path.is_relative_to(ROOT):
        raise ValueError('An exact NEW directory inside the workspace is required')
    parent = checked_learning_path(path.parent, ROOT)
    if parent != path.parent:
        raise ValueError('Ambiguous destination parent')
    path.mkdir(exist_ok=False)
    return path


def digest(path):
    path = checked_learning_path(path, ROOT)
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def copy_file(source, destination, expected=None):
    source = checked_learning_path(source, ROOT)
    if destination.parent.resolve(strict=True) != destination.parent or not destination.is_relative_to(ROOT):
        raise ValueError('Destination outside verified recovery directory')
    before = digest(source)
    if expected is not None and before != expected:
        raise ValueError('Source checksum mismatch')
    checksum = hashlib.sha256()
    with source.open('rb') as incoming, destination.open('xb') as outgoing:
        while block := incoming.read(1024 * 1024):
            checksum.update(block)
            outgoing.write(block)
    if checksum.hexdigest() != before or digest(source) != before:
        raise ValueError('Source changed while copying; retained partial evidence')


def database_state(database, tenant):
    database = checked_learning_path(database, ROOT)
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('SQLite integrity check failed')
        rows = db.execute('SELECT tenant_id,payload FROM learning_state').fetchall()
    if len(rows) != 1 or rows[0][0] != tenant:
        raise ValueError('Snapshot tenant mismatch')
    state = json.loads(rows[0][1])
    if any(row.get('state') == 'RECEIVING' for row in state['uploads'].values()):
        raise ValueError('An upload is in flight; retry the snapshot after it settles')
    return state


def blob_records(state):
    result = {}
    for row in state['blobs'].values():
        key = row['storage_key']
        if not re.fullmatch(r'[0-9a-f-]{36}\.(pdf|pptx)', key) or key in result:
            raise ValueError('Ambiguous blob storage key')
        result[key] = row
    for row in state['versions'].values():
        if row.get('blob_id') is None:
            # Preserve early synthetic SQLite records byte-for-byte, without migrating the source.
            key = row['storage_key']
            if not re.fullmatch(r'[0-9a-f-]{36}\.(pdf|pptx)', key):
                raise ValueError('Invalid legacy version storage key')
            if key in result and any(result[key][field] != row[field] for field in ('sha256', 'byte_size')):
                raise ValueError('Ambiguous legacy version bytes')
            result.setdefault(key, row)
        elif row['blob_id'] not in state['blobs']:
            raise ValueError('Missing immutable source blob record')
        if row.get('view_blob_id') and row['view_blob_id'] not in state['blobs']:
            raise ValueError('Missing immutable source or view blob record')
    return result


def snapshot(config_path: Path, destination: Path):
    config_path = checked_learning_path(config_path, ROOT)
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if config.get('storage') != 'sqlite' or config.get('synthetic_only') is not True:
        raise ValueError('This utility is limited to explicitly configured synthetic SQLite stores')
    paths = {}
    for field in ('database_file', 'identity_file', 'blob_directory'):
        relative = Path(config[field])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Explicit local configuration paths required')
        paths[field] = checked_learning_path(config_path.parent / relative, ROOT)
    destination = new_directory(destination)
    database = destination / 'learning.sqlite3'
    with database.open('xb'):
        pass
    with closing(sqlite3.connect(paths['database_file'].as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(database)) as target:
        source.backup(target)
    state = database_state(database, config['tenant_id'])
    records = blob_records(state)
    (destination / 'blobs').mkdir(exist_ok=False)
    for key, row in records.items():
        source = checked_learning_path(paths['blob_directory'] / key, ROOT)
        if source.stat().st_size != row['byte_size']:
            raise ValueError('Blob size mismatch')
        copy_file(source, destination / 'blobs' / key, row['sha256'])
    copy_file(paths['identity_file'], destination / 'identity.json')
    restored_config = config | {'database_file': 'learning.sqlite3', 'identity_file': 'identity.json', 'blob_directory': 'blobs'}
    with (destination / 'config.json').open('x', encoding='utf-8') as stream:
        json.dump(restored_config, stream, indent=2)
    files = ['learning.sqlite3', 'identity.json', 'config.json'] + ['blobs/' + key for key in sorted(records)]
    manifest = {'schema': 'learning-snapshot-v1', 'synthetic_only': True, 'tenant_id': config['tenant_id'],
        'blob_count': len(records), 'files': {name: digest(destination / name) for name in files},
        'credentials_exported': False, 'unreferenced_artifacts_copied': False,
        'identity_contains_signing_key': True}
    with (destination / 'manifest.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
    return verify(destination)


def verify(directory: Path):
    directory = checked_learning_path(directory, ROOT)
    manifest = json.loads(checked_learning_path(directory / 'manifest.json', ROOT).read_text(encoding='utf-8'))
    if manifest.get('schema') != 'learning-snapshot-v1' or manifest.get('synthetic_only') is not True:
        raise ValueError('Unsupported snapshot')
    for name, expected in manifest['files'].items():
        if name not in {'learning.sqlite3', 'identity.json', 'config.json'} and not re.fullmatch(r'blobs/[0-9a-f-]{36}\.(pdf|pptx)', name):
            raise ValueError('Invalid snapshot file name')
        if digest(directory / name) != expected:
            raise ValueError('Snapshot checksum mismatch')
    config = json.loads((directory / 'config.json').read_text(encoding='utf-8'))
    if config['tenant_id'] != manifest['tenant_id'] or config['storage'] != 'sqlite':
        raise ValueError('Snapshot configuration mismatch')
    records = blob_records(database_state(directory / 'learning.sqlite3', manifest['tenant_id']))
    expected_files = {'learning.sqlite3', 'identity.json', 'config.json'} | {'blobs/' + key for key in records}
    if expected_files != set(manifest['files']):
        raise ValueError('Snapshot file coverage mismatch')
    for key, row in records.items():
        path = checked_learning_path(directory / 'blobs' / key, ROOT)
        if digest(path) != row['sha256'] or path.stat().st_size != row['byte_size']:
            raise ValueError('Snapshot blob mismatch')
    return {'status': 'verified', 'directory': str(directory), 'blob_count': len(records),
        'file_count': len(manifest['files']), 'credentials_exported': False}


def restore(source: Path, destination: Path):
    verify(source)
    source = checked_learning_path(source, ROOT)
    manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    destination = new_directory(destination)
    (destination / 'blobs').mkdir(exist_ok=False)
    for name, expected in manifest['files'].items():
        copy_file(source / name, destination / name, expected)
    copy_file(source / 'manifest.json', destination / 'manifest.json')
    return verify(destination)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['snapshot', 'verify', 'restore'])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    if args.action != 'verify' and args.destination is None:
        parser.error('--destination must name a new directory')
    result = verify(args.source) if args.action == 'verify' else (snapshot if args.action == 'snapshot' else restore)(args.source, args.destination)
    print(json.dumps(result))
