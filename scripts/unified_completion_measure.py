"""Bounded synthetic evaluation/load; never claims human benefit or real cost."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sys
import time

sys.dont_write_bytecode = True
from unified_completion import STATE, ROOT, checked, retain, manifest, git_status
sys.path[:0] = [str(ROOT / p) for p in ['.', 'services/api/src', 'packages/synthetic/src', 'services/worker/src']]


def matched():
    import unified_parallel_c_compare as compare
    compare.STATE, compare.retain = STATE, retain
    asyncio.run(compare.run('01'))


def load():
    from fastapi.testclient import TestClient
    from campus247.bootstrap.unified_demo import create_unified_demo_app
    from campus247.domain.shared.values import generate_uuid7
    from tests.api.test_service_stage6 import sent, login, read
    from tests.unified_workflow13a.test_case_workflow import draft_body, prepare, preview, confirmation, post
    from unified_parallel_c_evaluate import CASES, distribution
    target = checked(STATE / 'fixtures/concurrent-load-01')
    target.mkdir(exist_ok=False)
    app = create_unified_demo_app(checked(target / 'business.sqlite3'), state_database=checked(target / 'actor.sqlite3'))
    before = manifest()
    observations = []
    with TestClient(app) as client:
        student, record, _ = sent(client)
        staff = login(client, 'OF002')
        from tests.api.test_service_stage6 import act
        record = act(client, staff, record, 'claim').json()['document_request']
        body = draft_body(client, staff, record)
        prepare(client, staff, body)
        prepared = preview(client, staff, body)
        result = post(client, staff, ':confirm', confirmation(prepared))
        assert result.status_code == 200
        receipt_body = {'client_id': prepared['client_id']}
        def one(index):
            case = CASES[index % 2]
            times, codes = {}, {}
            for name, call in [
                ('restore', lambda: client.get('/v1/assistant/preferences', headers=student)),
                ('prepare', lambda: client.post('/v1/assistant/student:prepare', headers=student, json={
                    'goal': case['goal'], 'workflow': case['workflow'], 'statements': case['statements'], 'operation_id': generate_uuid7()})),
                ('receipt_readback', lambda: client.post('/v1/assistant/cases/receipt:read', headers=staff, json=receipt_body)),
            ]:
                started = time.monotonic()
                response = call()
                times[name], codes[name] = (time.monotonic() - started) * 1000, response.status_code
            return {'index': index, 'condition': 'first_touch' if index < 4 else 'warm', 'latency_ms': times, 'status': codes}
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=4) as pool:
            observations = list(pool.map(one, range(24)))
        elapsed = time.monotonic() - start
        # Same current authorization checks apply to the concurrent workload.
        denied = client.post('/v1/assistant/cases/receipt:read', headers=student, json=receipt_body)
        current = read(client, student, record['id'])
    report = {'scope': 'in-process synthetic shared application and SQLite; no production load',
        'concurrency': 4, 'n': len(observations), 'observations': observations, 'duration_seconds': elapsed,
        'triplets_per_second': len(observations) / elapsed,
        'latencies': {key: distribution([row['latency_ms'][key] for row in observations]) for key in ['restore', 'prepare', 'receipt_readback']},
        'all_success': all(code == 200 for row in observations for code in row['status'].values()),
        'recipient_denial_status': denied.status_code, 'business_version_unchanged_by_read_prepare': current['version'] == record['version'] + 1,
        'dataset_sha256': hashlib.sha256(json.dumps(CASES[:2], sort_keys=True).encode()).hexdigest(),
        'source_hashes': before, 'source_stable': before == manifest(),
        'model_cost_usd': None, 'provider_calls': 0, 'active_ms': None, 'student_wait_ms': None, 'unit_wait_ms': None,
        'cold_process': 'initial application construction excluded; first_touch is not cold disk/cache',
        'queue_cache_worker_load': 'not measured; correctness/restart/budgets covered by backend suite',
        'production_slo': False}
    retain(target / 'report.json', report)
    print(json.dumps({k: v for k, v in report.items() if k not in {'observations', 'source_hashes'}}))
    if not report['all_success'] or not report['business_version_unchanged_by_read_prepare'] or denied.status_code not in {403, 404}:
        raise SystemExit(1)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    git_status()
    {'matched': matched, 'load': load}[sys.argv[1]]()
