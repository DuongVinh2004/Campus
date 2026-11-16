"""Register only newly allocated tmp_path fixtures; never touch retained DBs."""
import pytest
from unified_completion_scope import register


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    outcome = yield
    if fixturedef.argname == 'tmp_path':
        register(outcome.get_result())
