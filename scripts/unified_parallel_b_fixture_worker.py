"""Single worker tick against an explicit synthetic B fixture; never serving runtime."""
from datetime import datetime
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
from unified_parallel_b_preflight import ROOT, STATE, checked
from unified_completion_scope import completion_fixture

sys.path[:0] = [str(ROOT/'services/api/src'), str(ROOT/'services/worker/src'), str(ROOT/'packages/synthetic/src')]
from campus247.application.assistant_tracking.service import AssistantTrackingService
from campus247.domain.action.confirmation import ConfirmationTokenService
from campus247.application.assistance.feature_contracts import ActiveGrant
from campus247.infrastructure.repositories.sqlite_assistant_tracking import SQLiteAssistantTracking
from campus247.ports.identity import IdentityContext, IdentityRole
from campus247_worker.assistant_tracking.worker import AssistantTrackingWorker


def tick(config_path):
    config_path = checked(config_path)
    completion = completion_fixture(config_path.parent)
    if not config_path.is_relative_to(STATE) and not completion:
        raise ValueError('B fixture only')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if config.get('kind') == 'unified':
        from campus247.bootstrap.unified_demo import create_unified_demo_app
        from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
        paths = {name: checked(config[name]) for name in ('business_path', 'actor_path', 'memory_path', 'tracking_path')}
        if not all((path.is_relative_to(STATE) or completion and path.parent == config_path.parent) and path.is_file() for path in paths.values()):
            raise ValueError('existing exact B fixture databases required')
        app = create_unified_demo_app(paths['business_path'], state_database=paths['actor_path'], consent_mode='sqlite',
            personal_memory_store=SQLiteAssistantMemory(paths['memory_path']), personal_tracking_store=SQLiteAssistantTracking(paths['tracking_path']))
        return AssistantTrackingWorker(app.state.assistant_tracking).tick()
    fields = config['actor']
    actor = IdentityContext(**{**fields, 'roles': tuple(IdentityRole(role) for role in fields['roles']),
        'auth_time': datetime.fromisoformat(fields['auth_time']), 'expires_at': datetime.fromisoformat(fields['expires_at']), 'unit_ids': tuple(fields['unit_ids'])})
    source_type = runpy.run_path(str(ROOT/'tests/unified_personal13b/test_memory_tracking.py'))['DurableBusinessSource']
    source = object.__new__(source_type)
    source.path = checked(config['source_path'])
    store_path = checked(config['tracking_path'])
    if not all(path.is_relative_to(STATE) or completion and path.parent == config_path.parent for path in (source.path, store_path)):
        raise ValueError('B fixture databases only')
    grant = ActiveGrant.model_validate(config['grant'])
    permission = SimpleNamespace(version=1, payload=grant.model_dump(mode='json'))
    grants = SimpleNamespace(store=SimpleNamespace(get=lambda scope, namespace, key: permission if key == grant.spec.client_id else None),
        observe=lambda actor, target: SimpleNamespace(evidence=grant.evidence, resource=SimpleNamespace(view=grant.audience)))
    def resolve(tenant, owner, session):
        if (tenant, owner, session) != (actor.tenant_id, actor.subject_id, actor.session_id):
            raise ValueError('fixture recipient mismatch')
        return actor
    service = AssistantTrackingService(SQLiteAssistantTracking(store_path), tenant='fixture-b', authorize=lambda actor: None,
        tokens=ConfirmationTokenService('synthetic-b-test-signing-key'), grants=grants, source=source,
        resolve_recipient=resolve, project_notification=source.project, minimize=lambda text: text)
    return AssistantTrackingWorker(service).tick()


if __name__ == '__main__':
    print(json.dumps(tick(Path(sys.argv[1]))))
