"""Read-only scope/digests and exclusive B handoffs; preserves every prior attempt."""
import difflib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from unified_parallel_b_preflight import ROOT, STATE, checked, retain, sha, db_digest

EXACT = [
    'services/api/src/campus247/domain/assistant_memory.py', 'services/api/src/campus247/domain/assistant_tracking.py',
    'services/api/src/campus247/infrastructure/repositories/sqlite_assistant_memory.py',
    'services/api/src/campus247/infrastructure/repositories/sqlite_assistant_tracking.py',
    'services/api/src/campus247/presentation/assistant_memory.py', 'services/api/src/campus247/presentation/assistant_tracking.py',
    'services/api/src/campus247/bootstrap/assistant_personal_features.py',
    'apps/web/src/lib/assistant-memory.ts', 'apps/web/src/lib/assistant-tracking.ts',
    'apps/web/src/app/memory/page.tsx', 'apps/web/src/app/notifications/page.tsx',
    'apps/web/src/features/assistance/AssistantSettingsCenter.tsx', 'apps/web/src/app/privacy/page.tsx',
    'docs/UNIFIED_AI_PARALLEL_B_20261015_01.md',
]
FOLDERS = ['services/api/src/campus247/application/assistant_memory', 'services/api/src/campus247/application/assistant_tracking',
    'services/worker/src/campus247_worker/assistant_tracking', 'apps/web/src/features/memory', 'apps/web/src/features/notifications',
    'contracts/json-schema/assistance/memory-v1-01', 'contracts/json-schema/assistance/tracking-v1-01', 'tests/unified_personal13b']


def files():
    paths = [checked(ROOT/name) for name in EXACT]
    for folder in FOLDERS:
        paths.extend(checked(path) for path in (ROOT/folder).rglob('*') if path.is_file() and path.suffix in {'.py', '.tsx', '.ts', '.json'})
    paths.extend(checked(path) for path in (ROOT/'scripts').glob('unified_parallel_b_*.py'))
    return sorted(set(paths))


def scope(attempt):
    before = json.loads((STATE/'preflight.json').read_text(encoding='utf-8'))
    status = subprocess.run(['git', 'status', '--short', '--untracked-files=all'], cwd=ROOT, capture_output=True, text=True)
    original = {line[3:] for line in before['git_status'].splitlines()}
    current = {line[3:] for line in status.stdout.splitlines()}
    missing = sorted(original-current)
    digests = {name: db_digest(checked(ROOT/name)) for name in before['retained_databases']}
    assert digests == before['retained_databases'], 'retained DB drift'
    assert not missing, 'preexisting Git entry missing'
    paths = files()
    hashes = {path.relative_to(ROOT).as_posix(): sha(path) for path in paths}
    patches = []
    preimages = {row['path']: row for row in before['preimages']}
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        prior = checked(preimages[relative]['preimage']) if relative in preimages else None
        if prior:
            assert sha(prior) == preimages[relative]['sha256']
        old = prior.read_text(encoding='utf-8').splitlines(keepends=True) if prior else []
        new = path.read_text(encoding='utf-8').splitlines(keepends=True)
        patches.extend(difflib.unified_diff(old, new, fromfile=relative+' (B preimage)' if prior else '/dev/null', tofile=relative))
    with checked(STATE/('source-diff-'+attempt+'.patch')).open('x', encoding='utf-8') as handle:
        handle.write(''.join(patches))
    latest = {}
    for xml in sorted(STATE.glob('pytest-*/results.xml')):
        for case in ET.parse(xml).getroot().iter('testcase'):
            latest[(case.get('classname'), case.get('name'))] = not any(case.find(tag) is not None for tag in ('failure', 'error', 'skipped'))
    acks = []
    for path in sorted((STATE.parent/'stream-a/integration-acks').glob('personal-*.json')):
        ack = json.loads(path.read_text(encoding='utf-8'))
        acks.append({'file': str(path.relative_to(ROOT)), 'matches': {name: sha(ROOT/name) == checksum for name, checksum in ack['files'].items()}})
    baseline = json.loads((STATE.parent/'coordination-manifest.json').read_text(encoding='utf-8'))
    baseline_hashes = {row['path']: row['sha256'] for row in baseline['files']}
    protected = ['AGENTS.md', 'apps/web/AGENTS.md', 'apps/web/package.json', 'pnpm-lock.yaml', 'pyproject.toml', 'uv.lock']
    protected_matches = {name: sha(ROOT/name) == baseline_hashes[name] for name in protected if name in baseline_hashes}
    assert all(protected_matches.values()), 'protected dispatch source drift'
    guards = {path.relative_to(STATE).as_posix(): sha(path) for path in STATE.glob('frontend-*/acceptance-20261012-58-frontend-repair1-local-repair2/preserve-build.mjs')}
    assert set(guards.values()) == {'8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6'}
    result = {'files': hashes, 'preimages_verified': True, 'retained_databases': digests, 'retained_databases_unchanged': True,
        'preexisting_git_entries_missing': missing, 'git_status': status.stdout, 'git_warnings': status.stderr,
        'protected_dispatch_hashes_match': protected_matches, 'guards': guards, 'integration_acks': acks,
        'latest_unique_cases': len(latest), 'latest_passed': sum(latest.values()), 'latest_failures': [list(key) for key, passed in latest.items() if not passed],
        'global_release_gate': 'not_green_existing_deadline50ms_failure_not_changed_or_rerun',
        'no_deletion_cleanup_commit_push_deploy_runtime_restart': True, 'provider_dispatches': 0, 'ui_tests': False}
    retain(STATE/('scope-'+attempt+'.json'), result)
    print(json.dumps({'files': len(hashes), 'unique_cases': len(latest), 'passed': sum(latest.values()), 'retained_databases_unchanged': True}))
    return result


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in {'01', '02', '03'}:
        raise ValueError('explicit fresh evidence attempt required')
    scope(sys.argv[1])
