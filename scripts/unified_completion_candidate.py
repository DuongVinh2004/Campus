"""Explicit new synthetic candidate on8016; never opens a retained serving DB."""
import json
import sys

sys.dont_write_bytecode = True
from unified_completion import STATE, ROOT, checked, retain, manifest, git_status
sys.path[:0] = [str(ROOT / path) for path in ['.', 'services/api/src', 'services/worker/src', 'packages/synthetic/src']]
from campus247.bootstrap.app import create_app
from campus247.bootstrap.settings import Settings
from campus247.bootstrap.unified_demo import create_unified_demo_app
from campus247.infrastructure.llm.fake import DeterministicFakeProvider
from campus247.infrastructure.repositories.sqlite_actor_state import SQLiteActorStateStore
from campus247.infrastructure.repositories.sqlite_assistant_memory import SQLiteAssistantMemory
from campus247.infrastructure.repositories.sqlite_assistant_tracking import SQLiteAssistantTracking
from campus247.infrastructure.repositories.sqlite_conversations import SQLiteConversationRepository

NUMBER = sys.argv[2] if len(sys.argv) == 3 else '01'
if NUMBER not in {'01', '02', '03', '04'}: raise ValueError('exact candidate attempt required')
API_PORT, FRONTEND_PORT = 8015 + int(NUMBER), 3015 + int(NUMBER)
TARGET = checked(STATE / 'fixtures' / ('candidate' + NUMBER))


def composition():
    if not (TARGET / 'new-fixture.json').is_file():
        raise ValueError('new candidate marker required')
    paths = {name: checked(TARGET / (name + '.sqlite3')) for name in ['business', 'actor', 'memory', 'tracking', 'history']}
    if not all(path.is_file() for path in paths.values()):
        raise ValueError('existing exact candidate files required')
    settings = Settings(_env_file=None, OPENAI_API_KEY=None, GEMINI_API_KEY=None, DEEPSEEK_API_KEY=None,
        ACTOR_STATE_STORAGE_MODE='sqlite', ACTOR_STATE_SQLITE_PATH=paths['actor'],
        CONSENT_STORAGE_MODE='sqlite', CONSENT_SQLITE_PATH=paths['actor'])
    memory, tracking = SQLiteAssistantMemory(paths['memory']), SQLiteAssistantTracking(paths['tracking'])
    native = create_app(runtime_settings=settings, synthetic_tenant_id='huce-local-public',
        conversation_repository=SQLiteConversationRepository(paths['history']), personal_memory_store=memory,
        llm_gateway=DeterministicFakeProvider.default())
    frontend = checked(STATE / 'checks' / ('frontend-' + NUMBER) / 'frontend/acceptance-20261012-58-frontend-repair1-local-repair2')
    build_id = (frontend / '.next/BUILD_ID').read_text().strip()
    app = create_unified_demo_app(paths['business'], state_database=paths['actor'], consent_mode='sqlite',
        personal_memory_store=memory, personal_tracking_store=tracking, chat_application=native,
        frontend_build_id=build_id)
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=[f'http://localhost:{FRONTEND_PORT}', f'http://127.0.0.1:{FRONTEND_PORT}'],
        allow_credentials=True, allow_methods=['GET', 'POST'], allow_headers=['Content-Type', 'Authorization'])
    @app.get('/candidate-manifest')
    def candidate_manifest():
        return {'namespace': 'unified-ai-completion-20261015-01/fixtures/candidate' + NUMBER,
            'api': f'http://localhost:{API_PORT}', 'frontend': f'http://localhost:{FRONTEND_PORT}', 'build_id': build_id,
            'provider': 'deterministic_fake', 'paid_calls': 0, 'serving_transition': False}
    return app


if __name__ == '__main__':
    git_status()
    if sys.argv[1] == 'init':
        TARGET.mkdir(exist_ok=False)
        retain(TARGET / 'new-fixture.json', {'kind': 'new_synthetic_completion_candidate', 'no_retained_data': True})
        SQLiteActorStateStore(checked(TARGET / 'actor.sqlite3'))
        SQLiteAssistantMemory(checked(TARGET / 'memory.sqlite3'), initialize=True)
        SQLiteAssistantTracking(checked(TARGET / 'tracking.sqlite3'), initialize=True)
        SQLiteConversationRepository(checked(TARGET / 'history.sqlite3'), tenant='huce-local-public')
        create_unified_demo_app(checked(TARGET / 'business.sqlite3'), state_database=checked(TARGET / 'actor.sqlite3'))
        retain(TARGET / 'initial-source.json', manifest())
        print(str(TARGET))
    elif sys.argv[1] == 'serve':
        import uvicorn
        app = composition()
        retain(TARGET / 'serve.json', {'source_hashes': manifest(), 'api_port': API_PORT, 'frontend_port': FRONTEND_PORT, 'paid_calls': 0})
        uvicorn.run(app, host='127.0.0.1', port=API_PORT, access_log=False)
    else: raise ValueError('explicit init/serve only')
