"""Explicit composition prevents silent database, scanner or provider fallbacks."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from campus247.bootstrap.learning import configure_learning_ai, load_local_learning
from campus247.infrastructure.learning.repository import PostgresLearningRepository

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from learning_local_setup import setup


@pytest.fixture
def configuration(tmp_path):
    if not tmp_path.resolve().is_relative_to(ROOT):
        raise RuntimeError('Use an explicit new --basetemp inside the authorized repository')
    directory = tmp_path / 'local'
    setup(directory, 'configuration-test')
    return directory, json.loads((directory / 'config.json').read_text())


def new_config(directory, name, value):
    path = directory / name
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream)
    return path


def test_postgres_requires_matching_verified_database(configuration):
    directory, value = configuration
    path = new_config(directory, 'postgres.json', value | {'storage': 'postgres', 'database_name': 'explicit-test'})
    for pool, name in [(None, 'explicit-test'), (object(), None), (object(), 'other-database')]:
        with pytest.raises(ValueError, match='explicitly verified matching database'):
            load_local_learning(path, workspace=ROOT, tenant_id='configuration-test', postgres_pool=pool, verified_database_name=name)
    pool = object()
    service, _ = load_local_learning(path, workspace=ROOT, tenant_id='configuration-test', postgres_pool=pool, verified_database_name='explicit-test')
    assert isinstance(service.repository, PostgresLearningRepository)
    assert service.repository.pool is pool


def test_unknown_scanner_mode_never_falls_back(configuration):
    directory, value = configuration
    path = new_config(directory, 'invalid-scanner.json', value | {'scanner_mode': 'unknown'})
    with pytest.raises(ValueError, match='Unknown learning scanner mode'):
        load_local_learning(path, workspace=ROOT, tenant_id='configuration-test')


def test_postgres_optimized_views_require_verified_revision_0024(configuration):
    directory, value = configuration
    path = new_config(directory, 'postgres-views.json', value | {'storage': 'postgres', 'database_name': 'explicit-test', 'pdf_web_view': True})
    for revision in (None, '0023'):
        with pytest.raises(ValueError, match='schema revision 0024'):
            load_local_learning(path, workspace=ROOT, tenant_id='configuration-test', postgres_pool=object(),
                verified_database_name='explicit-test', verified_schema_revision=revision)


def test_learning_ai_is_explicit_and_does_not_call_provider():
    calls = []
    gateway = SimpleNamespace(generate=lambda request: calls.append(request))
    service = SimpleNamespace(ai_gateway=None, ai_verifier=None, ai_source_hashes=frozenset())
    configure_learning_ai(service, gateway, enabled=False)
    assert service.ai_gateway is None
    with pytest.raises(ValueError):
        configure_learning_ai(service, None, enabled=True)
    with pytest.raises(ValueError, match="explicit synthetic source hashes"):
        configure_learning_ai(service, gateway, enabled=True)
    service.ai_source_hashes = frozenset({"a" * 64})
    configure_learning_ai(service, gateway, enabled=True)
    assert service.ai_gateway is gateway and service.ai_verifier is not None
    assert not calls


def test_ai_config_rejects_hashes_outside_the_synthetic_fixture_list(configuration):
    directory, value = configuration
    path = new_config(directory, 'unlisted-ai-source.json', value | {'ai_synthetic_source_sha256': ['a' * 64]})
    with pytest.raises(ValueError, match='explicitly listed synthetic fixture hashes'):
        load_local_learning(path, workspace=ROOT, tenant_id='configuration-test')


def test_ocr_pause_config_defaults_off_and_requires_enabled_offerings(configuration):
    directory, value = configuration
    offering = str(uuid4())
    field = "accessible_text_ocr_paused_offerings"
    enabled = value | {"accessible_text_offerings": [offering]}
    for name, profile, expected in (
        ("default", enabled, frozenset()),
        ("paused", enabled | {field: [offering]}, frozenset({offering})),
    ):
        service, _ = load_local_learning(new_config(directory, f"{name}.json", profile),
                                         workspace=ROOT, tenant_id="configuration-test")
        assert service.accessible_text_ocr_paused_offerings == expected
    for name, profile, message in (
        ("wrong-type", enabled | {field: offering}, "canonical offering IDs"),
        ("other-class", enabled | {field: [str(uuid4())]}, "also be enabled"),
    ):
        with pytest.raises(ValueError, match=message):
            load_local_learning(new_config(directory, f"{name}.json", profile),
                                workspace=ROOT, tenant_id="configuration-test")
