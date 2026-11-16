"""Append-only evidence for the sequential completion run; no serving mutations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from unified_parallel_c_preserve import checked, database_digest, DATABASES, manifest, ROOT

STATE = checked(ROOT / 'infra/local/unified-ai-completion-20261015-01')


def git_status():
    result = subprocess.run(['git', '--no-optional-locks', '-c', 'safe.directory=' + str(ROOT), 'status', '--porcelain=v1'],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    return {'entries': result.stdout.splitlines(), 'warnings': result.stderr}


def retain(path, data):
    path = checked(path)
    if not path.is_relative_to(STATE):
        raise ValueError('completion evidence only')
    with path.open('x', encoding='utf-8') as output:
        json.dump(data, output, ensure_ascii=False, indent=2)


def init():
    status = git_status()
    before = manifest()
    databases = {name: database_digest(ROOT / name) for name in DATABASES}
    STATE.mkdir(exist_ok=False)
    for name in ['preimages', 'checks', 'fixtures', 'snapshots']:
        checked(STATE / name).mkdir(exist_ok=False)
    for name, checksum in before.items():
        source = checked(ROOT / name)
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != checksum:
            raise RuntimeError('source drift during capture')
        destination = checked(STATE / 'preimages' / name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as output:
            output.write(data)
    retain(STATE / 'preflight.json', {'git': status, 'source_hashes': before,
        'retained_databases': databases, 'stable': before == manifest(),
        'authority': 'direct sequential local implementation; Git read-only per-message exception',
        'provider_calls': 0, 'serving_transitions': 0})
    print(json.dumps({'namespace': str(STATE), 'preimages': len(before), 'databases_ro': len(databases)}))


def verify(number, selected):
    from unified_parallel_c_verify import selected_files, outcomes
    status = git_status()
    target = checked(STATE / 'checks' / ('backend-' + number))
    target.mkdir(exist_ok=False)
    cases = selected or selected_files('combined') + ['tests/unified_completion']
    command = [sys.executable, '-B', '-u', '-m', 'pytest', *cases, '-q', '--tb=short',
        '-p', 'no:cacheprovider', '-p', 'pytest_asyncio.plugin', '-p', 'unified_completion_pytest', '-o', 'faulthandler_timeout=30',
        '--basetemp=' + str(checked(target / 'basetemp')), '--junitxml=' + str(checked(target / 'backend.xml'))]
    environment = {**os.environ, 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONDONTWRITEBYTECODE': '1',
        'PYTHONIOENCODING': 'utf-8', 'CAMPUS247_IDEMPOTENCY_DB': str(checked(target / 'idempotency.sqlite3')),
        'PYTHONPATH': os.pathsep.join(str(ROOT / p) for p in ['.', 'scripts', 'services/api/src', 'services/worker/src', 'packages/synthetic/src'])}
    before = manifest()
    started = time.monotonic()
    with checked(target / 'backend.log').open('xb') as output:
        result = subprocess.run(command, cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT)
    after = manifest()
    summary = outcomes([target / 'backend.xml']) if (target / 'backend.xml').exists() else {'collection_failed': True}
    retain(target / 'command.json', {'command': command, 'exit_code': result.returncode,
        'duration_seconds': time.monotonic() - started, 'outcomes': summary, 'git_before': status,
        'source_before': before, 'source_after': after, 'stable': before == after, 'provider_calls': 0})
    print(json.dumps({'exit_code': result.returncode, 'stable': before == after, 'outcomes': summary}))
    print((target / 'backend.log').read_text(encoding='utf-8', errors='replace')[-14000:])
    return result.returncode


def audit(number):
    before = json.loads((STATE / 'preflight.json').read_text(encoding='utf-8'))
    after = {name: database_digest(ROOT / name) for name in DATABASES}
    status = git_status()
    protected = ['AGENTS.md', 'apps/web/AGENTS.md', 'apps/web/package.json', 'pnpm-lock.yaml', 'pyproject.toml', 'uv.lock',
        'infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs']
    now = manifest()
    result = {'retained_databases_unchanged': before['retained_databases'] == after,
        'protected_unchanged': {p: before['source_hashes'][p] == now[p] for p in protected},
        'git': status, 'missing_preexisting_entries': sorted(set(before['git']['entries']) - set(status['entries'])),
        'source_hashes': now, 'provider_calls': 0, 'serving_transitions': 0}
    retain(STATE / ('preservation-' + number + '.json'), result)
    print(json.dumps({k: v for k, v in result.items() if k not in {'git', 'source_hashes'}}))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['init', 'verify', 'audit'])
    parser.add_argument('number', nargs='?', default='01')
    parser.add_argument('selected', nargs='*')
    args = parser.parse_args()
    if not args.number.isdigit() or len(args.number) != 2:
        raise ValueError('exact two-digit attempt')
    if args.action == 'init': init()
    elif args.action == 'audit': audit(args.number)
    else: raise SystemExit(verify(args.number, args.selected))
