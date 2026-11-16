"""Exclusive evidence and exact-path preimages for stream B. No retained DB writer."""
from pathlib import Path
import hashlib
import json
import os
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'infra/local/unified-ai-parallel-20261015-01/stream-b'


def checked(path):
    path = Path(path).absolute()
    resolved = path.resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT) or path != resolved:
        raise ValueError('exact canonical descendant required')
    for parent in [path, *path.parents]:
        if parent == ROOT:
            break
        if parent.exists() and (parent.is_symlink() or os.path.isjunction(parent)):
            raise ValueError('reparse target denied')
    return resolved


def retain(path, value):
    path = checked(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def db_digest(path):
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as connection:
        connection.execute('BEGIN')
        tables = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        result = {}
        for name, schema in tables:
            rows = connection.execute('SELECT * FROM "' + name.replace('"', '""') + '"').fetchall()
            encoded = sorted(repr(row) for row in rows)
            result[name] = {'rows': len(rows), 'sha256': hashlib.sha256(repr((schema, encoded)).encode()).hexdigest()}
        return result


def main():
    checked(STATE).mkdir(exist_ok=False)
    status = subprocess.run(['git', 'status', '--short', '--untracked-files=all'], cwd=ROOT, capture_output=True, text=True)
    targets = ['apps/web/src/features/assistance/AssistantSettingsCenter.tsx', 'apps/web/src/app/privacy/page.tsx']
    images = []
    for relative in targets:
        source = checked(ROOT / relative)
        destination = checked(STATE / 'preimages' / relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as handle:
            handle.write(source.read_bytes())
        images.append({'path': relative, 'sha256': sha(source), 'preimage': str(destination)})
    databases = ['infra/local/unified-ai-20261014-01/business-candidate01.sqlite3', 'infra/local/unified-ai-20261014-05/actor-state.sqlite3', 'infra/local/public-rag-20261013/conversations.sqlite3', 'infra/local/multi-agent-integrated-20261013-01/agent-runs.sqlite3']
    retain(STATE / 'preflight.json', {'workspace': str(ROOT), 'git_status': status.stdout, 'git_stderr': status.stderr, 'preimages': images,
        'retained_databases': {name: db_digest(checked(ROOT / name)) for name in databases}})
    print(str(STATE))


if __name__ == '__main__':
    main()
