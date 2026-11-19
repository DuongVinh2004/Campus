"""The published learning contract covers every implemented operation and local schema."""
import json
import re
from pathlib import Path

import pytest
import yaml
from campus247.presentation.learning import (
    SCHEMAS,
    LearningExplanationInput,
    create_learning_router,
)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / 'contracts/openapi/v1/learning.openapi.pptx.json'


def test_learning_contract_covers_routes_security_and_path_parameters():
    document = json.loads(CONTRACT.read_text(encoding='utf-8'))
    router = create_learning_router(None)
    actual = {(route.path, method.lower()) for route in router.routes for method in route.methods}
    published = {(path, method) for path, item in document['paths'].items() for method in item}
    assert actual == published
    ids = []
    for path, method in published:
        operation = document['paths'][path][method]
        ids.append(operation['operationId'])
        assert operation['security'] == [{'cookieSession': []}, {'bearerAuth': []}]
        assert set(re.findall(r'\{([^}]+)\}', path)) == {p['name'] for p in operation.get('parameters', []) if p['in'] == 'path'}
    assert len(set(ids)) == len(ids)
    root_document = yaml.safe_load((CONTRACT.parent / 'openapi.yaml').read_text(encoding='utf-8'))
    for path in document['paths']:
        assert root_document['paths'][path]['$ref'] == './' + CONTRACT.name + '#/paths/' + path.replace('~', '~0').replace('/', '~1')


def test_learning_schema_refs_and_binary_head_contract():
    document = json.loads(CONTRACT.read_text(encoding='utf-8'))
    def visit(value):
        if isinstance(value, dict):
            if '$ref' in value:
                assert value['$ref'].startswith('#/')
                target = document
                for part in value['$ref'][2:].split('/'):
                    target = target[part.replace('~1', '/').replace('~0', '~')]
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(document)
    path = document['paths']['/v1/learning/versions/{version_id}/content']
    assert 'content' not in path['head']['responses']['200']
    assert '206' not in path['head']['responses']
    assert 'application/pdf' in path['get']['responses']['206']['content']
    upload = document['paths']['/v1/learning/upload-intents/{upload_id}/content']['put']
    assert 'application/pdf' in upload['requestBody']['content']
    pptx = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    assert pptx in upload['requestBody']['content']
    assert pptx not in path['get']['responses']['200']['content']
    download = document['paths']['/v1/learning/versions/{version_id}/download']['get']
    assert pptx in download['responses']['206']['content']
    assert 'rendition_id' in document['components']['schemas']['LearningAnnotationInput']['properties']
    for action in ('question-create', 'question-update', 'reply-create'):
        schema = SCHEMAS[action]
        assert document['components']['schemas'][schema.__name__] == schema.model_json_schema()


@pytest.mark.parametrize('body', [
    {'page_no': True, 'question': 'Explain'},
    {'page_no': 0, 'question': 'Explain'},
    {'page_no': 1, 'question': ''},
    {'page_no': 1, 'question': 'Explain', 'role': 'SYSTEM_ADMIN'},
])
def test_explanation_input_is_strict(body):
    with pytest.raises(ValueError):
        LearningExplanationInput.model_validate(body)
