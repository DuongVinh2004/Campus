"""Fresh B frontend snapshot, inherited preservation guard byte-identical."""
import sys
import subprocess
saved_arguments = sys.argv
sys.argv = sys.argv[:1]
import prepare_unified_ai_frontend08 as previous
sys.argv = saved_arguments
from unified_parallel_b_preflight import ROOT, STATE, checked, retain, sha

ATTEMPT = sys.argv[2]
if ATTEMPT not in {'01', '02', '03', '04'}:
    raise ValueError('exact fresh attempt required')
FRONTEND = checked(STATE / ('frontend-' + ATTEMPT) / 'acceptance-20261012-58-frontend-repair1-local-repair2')
previous.STATE, previous.FRONTEND, previous.ATTEMPT = STATE, FRONTEND, ATTEMPT
previous.build_tools.STATE, previous.build_tools.FRONTEND, previous.build_tools.ATTEMPT = STATE, FRONTEND, ATTEMPT
previous.build_tools.retain = retain


def prepare():
    previous.build_tools.prepare()
    assert sha(FRONTEND/'preserve-build.mjs') == '8f0886295da2214205cf257dd9e1d9476993ed1a7fb0ac67434909fa4af2eae6'
    retain(STATE/('frontend-source-'+ATTEMPT+'.json'), {str(path.relative_to(FRONTEND)): sha(path) for path in (FRONTEND/'src').rglob('*') if path.is_file()})


def typecheck():
    output = checked(STATE / ('frontend-typescript-' + ATTEMPT + '.json'))
    if output.exists():
        raise FileExistsError('preserve prior typescript attempt')
    command = [str(previous.build_tools.NODE), str(ROOT/'apps/web/node_modules/typescript/bin/tsc'), '--project', str(FRONTEND/'tsconfig.json'), '--noEmit', '--incremental', 'false']
    result = subprocess.run(command, cwd=FRONTEND, env=previous.build_tools.runtime_environment(), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180, creationflags=0x08000000)
    retain(output, {'command': command, 'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
    print(result.stdout, result.stderr)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'prepare': prepare, 'build': previous.build_tools.build, 'typecheck': typecheck}[sys.argv[1]]()
