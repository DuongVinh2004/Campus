"""Build/run a fresh local frontend; inherited preservation guard unchanged."""
import json
import subprocess
import sys

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
from unified_completion import STATE, checked, ROOT, retain, manifest, git_status

stage, number = sys.argv[1:3]
if stage not in {'prepare', 'build', 'typecheck', 'serve'} or number not in {'01', '02', '03', '04'}:
    raise ValueError('exact frontend action/attempt required')
sys.argv = [sys.argv[0], stage, '01']
import prepare_unified_ai_frontend08 as wrapper
build = wrapper.build_tools
build.STATE = checked(STATE / 'checks' / ('frontend-' + number))
build.ATTEMPT = number
build.FRONTEND = checked(build.STATE / 'frontend' / 'acceptance-20261012-58-frontend-repair1-local-repair2')
build.retain = retain
original_environment = build.runtime_environment
def environment():
    return {**original_environment(), 'NEXT_PUBLIC_API_URL': 'http://localhost:' + str(8015 + int(number))}
build.runtime_environment = environment
before = manifest()
git_status()
if stage == 'prepare':
    build.STATE.mkdir(exist_ok=False)
    build.prepare()
    retain(build.STATE / 'prepared.json', {'source_hashes': before, 'guard_copy_identical':
        (build.FRONTEND / 'preserve-build.mjs').read_bytes() == (ROOT / 'infra/local/rag-fixture/m1_source_guard_20261012_58-repair1.mjs').read_bytes(),
        'api_url': environment()['NEXT_PUBLIC_API_URL'], 'frontend_port': 3015 + int(number)})
elif stage == 'build':
    build.build()
elif stage == 'typecheck':
    command = [str(build.NODE), str(ROOT / 'apps/web/node_modules/typescript/bin/tsc'),
        '--project', str(build.FRONTEND / 'tsconfig.json'), '--noEmit', '--incremental', 'false']
    result = subprocess.run(command, cwd=build.FRONTEND, env=environment(), capture_output=True, text=True, encoding='utf-8', timeout=180, creationflags=0x08000000)
    retain(build.STATE / 'typescript.json', {'command': command, 'exit_code': result.returncode,
        'stdout': result.stdout, 'stderr': result.stderr, 'source_stable': before == manifest()})
    print(result.stdout, result.stderr)
    raise SystemExit(result.returncode)
else:
    command = [str(build.NODE), '--import', (build.FRONTEND / 'preserve-build.mjs').as_uri(),
        str(ROOT / 'apps/web/node_modules/next/dist/bin/next'), 'start', str(build.FRONTEND), '-p', str(3015 + int(number)), '-H', '127.0.0.1']
    retain(build.STATE / 'serve-command.json', {'command': command, 'build_id': (build.FRONTEND / '.next/BUILD_ID').read_text(),
        'api_url': environment()['NEXT_PUBLIC_API_URL'], 'source_hashes': before, 'guard_unchanged': True})
    raise SystemExit(subprocess.call(command, cwd=build.FRONTEND, env=environment(), creationflags=0x08000000))
