"""Retained unique attempts for B tests/build/types/contracts and final audit."""
import os
import subprocess
import sys
from unified_parallel_b_preflight import ROOT, STATE, checked, retain, db_digest, sha


def source_hashes():
    paths = [ROOT/name for name in [
        'services/api/src/campus247/bootstrap/unified_demo.py', 'services/api/src/campus247/bootstrap/assistant_features.py',
        'services/api/src/campus247/application/assistance/personal_consumers.py', 'services/api/src/campus247/application/assistance/scoped_context.py',
        'services/api/src/campus247/presentation/assistant_state.py', 'services/api/src/campus247/infrastructure/repositories/case_workflow.py',
        'services/api/src/campus247/application/assistance/case_workflow.py', 'services/api/src/campus247/domain/assistant_memory.py',
        'services/api/src/campus247/domain/assistant_tracking.py', 'services/api/src/campus247/bootstrap/assistant_personal_features.py',
        'services/api/src/campus247/presentation/assistant_memory.py', 'services/api/src/campus247/presentation/assistant_tracking.py',
        'scripts/unified_parallel_b_fixture_worker.py',
        'services/api/src/campus247/infrastructure/repositories/sqlite_assistant_memory.py', 'services/api/src/campus247/infrastructure/repositories/sqlite_assistant_tracking.py']]
    for relative in ['services/api/src/campus247/application/assistant_memory', 'services/api/src/campus247/application/assistant_tracking',
            'services/worker/src/campus247_worker/assistant_tracking', 'tests/unified_personal13b']:
        paths.extend((ROOT/relative).rglob('*.py'))
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in sorted(set(paths))}


def tests(attempt):
    target = checked(STATE / ('pytest-' + attempt))
    if target.exists():
        raise FileExistsError('preserve prior pytest attempt')
    target.mkdir(exist_ok=False)
    base = checked(target / 'basetemp')
    command = [sys.executable, '-B', '-u', '-m', 'pytest', 'tests/unified_personal13b', '-q', '-o', 'faulthandler_timeout=30', '-p', 'no:cacheprovider',
        '--basetemp', str(base), '--junitxml', str(target/'results.xml')]
    environment = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONIOENCODING': 'utf-8',
        'CAMPUS247_IDEMPOTENCY_DB': str(target/'idempotency.sqlite3'),
        'PYTHONPATH': str(ROOT/'services/worker/src') + os.pathsep + str(ROOT/'services/api/src')}
    before = source_hashes()
    with (target/'pytest.log').open('xb') as log:
        try:
            result = subprocess.run(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=180, creationflags=0x08000000)
        except subprocess.TimeoutExpired:
            retain(target/'command.json', {'command': command, 'exit_code': None, 'failure': 'harness_timeout_180_seconds', 'log': str(target/'pytest.log')})
            raise
    after = source_hashes()
    retain(target/'command.json', {'command': command, 'exit_code': result.returncode, 'log': str(target/'pytest.log'),
        'source_before': before, 'source_after': after, 'source_unchanged_during_run': before == after})
    print((target/'pytest.log').read_text(encoding='utf-8', errors='replace'))
    raise SystemExit(result.returncode)


def audit(attempt):
    import json
    before = json.loads((STATE/'preflight.json').read_text(encoding='utf-8'))
    after = {name: db_digest(checked(ROOT/name)) for name in before['retained_databases']}
    retain(STATE/('audit-'+attempt+'.json'), {'retained_databases': after, 'unchanged': after == before['retained_databases']})
    assert after == before['retained_databases']


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) != 3 or sys.argv[2] not in {'01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20'}:
        raise ValueError('exact new attempt required')
    {'tests': tests, 'audit': audit}[sys.argv[1]](sys.argv[2])
