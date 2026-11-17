"""AUD-003: every ENVIRONMENT value Settings accepts must either start the app or refuse for a stated reason.

`testing` is a valid Settings value, but the synthetic identity adapter used to reject it, so create_app failed
before opening any store. Production and staging must keep refusing the synthetic identity adapter.
"""
import pytest
from campus247.bootstrap import app as bootstrap
from campus247.bootstrap.settings import Settings
from campus247.infrastructure.identity.mock import ALLOWED_ENVIRONMENTS, SyntheticIdentityAdapter
from campus247.infrastructure.identity.production_guard import ProductionSecurityError

SECURE = {"IDENTITY_SECRET_KEY": "x" * 48, "CONFIRMATION_SIGNING_KEY": "y" * 48}


@pytest.mark.parametrize("environment", ["development", "testing"])
def test_local_environments_start_the_app(monkeypatch, environment):
    monkeypatch.setenv("ENVIRONMENT", environment)
    assert bootstrap.create_app() is not None


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_environments_never_start_with_the_synthetic_identity(monkeypatch, environment):
    monkeypatch.setenv("ENVIRONMENT", environment)
    for name, value in SECURE.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DEMO_MODE", "true")
    with pytest.raises((ValueError, ProductionSecurityError)):
        bootstrap.create_app()


def test_every_settings_environment_is_either_allowed_or_deployed():
    declared = set(Settings.model_fields["ENVIRONMENT"].annotation.__args__)
    assert declared - ALLOWED_ENVIRONMENTS == {"staging", "production"}


@pytest.mark.parametrize("environment", ["staging", "production", "PRODUCTION"])
def test_adapter_refuses_deployed_environments(environment):
    with pytest.raises(ValueError):
        SyntheticIdentityAdapter(secret_key="k" * 48, environment=environment)
