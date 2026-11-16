"""Exact canonical per-test scopes for this run; retained/outside paths denied."""
import json
import re
try:
    from unified_parallel_c_preserve import checked, ROOT
except ModuleNotFoundError:
    from scripts.unified_parallel_c_preserve import checked, ROOT

STATE = checked(ROOT / 'infra/local/unified-ai-completion-20261015-01')


def completion_fixture(path):
    path = checked(path)
    try:
        parts = path.relative_to(STATE).parts
    except ValueError:
        return False
    if (len(parts) != 4 or parts[0] != 'checks' or re.fullmatch(r'backend-[0-9]{2}', parts[1]) is None
            or parts[2] != 'basetemp' or not parts[3].startswith('test_')):
        return False
    marker = checked(path / '.completion-scope.json')
    if not marker.is_file():
        return False
    value = json.loads(marker.read_text(encoding='utf-8'))
    return value == {'fixture': str(path), 'purpose': 'new_synthetic_process_fixture', 'version': 1}


def register(path):
    path = checked(path)
    marker = checked(path / '.completion-scope.json')
    # Verify lexical shape before exclusive creation as well as after readback.
    parts = path.relative_to(STATE).parts
    if (len(parts) != 4 or parts[0] != 'checks' or re.fullmatch(r'backend-[0-9]{2}', parts[1]) is None
            or parts[2] != 'basetemp' or not parts[3].startswith('test_')):
        raise ValueError('exact new pytest fixture required')
    with marker.open('x', encoding='utf-8') as output:
        json.dump({'fixture': str(path), 'purpose': 'new_synthetic_process_fixture', 'version': 1}, output)
    if not completion_fixture(path):
        raise ValueError('fixture readback mismatch')
