"""Export the implemented learning routes and strict request schemas to a new contract file."""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services/api/src'))


def exit_ticket_response_contract():
    uuid = {'type': 'string', 'format': 'uuid'}
    timestamp = {'type': 'string', 'format': 'date-time'}
    text = {'type': 'string'}
    positive = {'type': 'integer', 'minimum': 1}
    def obj(**properties):
        return {'type': 'object', 'additionalProperties': False, 'required': list(properties), 'properties': properties}
    def ref(name):
        return {'$ref': '#/components/schemas/LearningExit' + name}
    def nullable(schema):
        return {'anyOf': [schema, {'type': 'null'}]}
    def array(schema):
        return {'type': 'array', 'items': schema}
    def paginated(schema):
        return obj(items=array(schema), page=obj(next_cursor=nullable(text), has_more={'type': 'boolean'}, limit=positive))
    identity = {'id': uuid, 'session_id': uuid, 'revision': positive}
    instant = obj(local=text, offset_minutes={'type': 'integer'}, utc=timestamp)
    receipt = {'ticket_id': uuid, 'answer': text, 'revision': positive, 'receipt_id': uuid, 'submitted_at': timestamp}
    shared_review = obj(explanation=text, published_at=timestamp)
    schemas = {
        'LearningExitTicket': {'oneOf': [
            obj(**identity, state={'const': 'SOURCE_UNAVAILABLE'}),
            obj(**identity, state={'enum': ['DRAFT', 'SCHEDULED', 'OPEN', 'CLOSED', 'CANCELLED']},
                version_id=uuid, page_no=positive, question=text, zone_id=text, opens=instant, closes=instant,
                instruction=nullable(obj(id=uuid, revision=positive, purpose=text, page_ranges=array(obj(start=positive, end=positive))))),
        ]},
        'LearningExitReceipt': obj(**receipt),
        'LearningExitReceiptHistory': obj(**receipt, history=array(ref('Receipt'))),
        'LearningExitStaffSubmission': obj(**receipt, id=uuid, student_id=uuid),
        'LearningExitStaffReview': obj(revision=positive, topics=text, next_plan=text, explanation=text, published=nullable(shared_review)),
        'LearningExitSharedReview': obj(published=shared_review),
    }
    responses = {
        'exit_tickets': paginated(ref('Ticket')),
        'exit_ticket': ref('Ticket'),
        'exit_submission': obj(submission=nullable(ref('ReceiptHistory'))),
        'exit_submissions': paginated(ref('StaffSubmission')),
        'exit_review': obj(review={'oneOf': [ref('StaffReview'), ref('SharedReview'), {'type': 'null'}]}),
        'exit-ticket-create': ref('Ticket'),
        'exit-ticket-update': ref('Ticket'),
        'exit-submission-save': ref('Receipt'),
        'exit-review-save': ref('StaffReview'),
    }
    return schemas, responses


def export(destination: Path):
    from campus247.application.learning.accessible_text import OCR_WRITES
    from campus247.application.learning.exit_tickets import EXIT_TICKET_WRITES
    from campus247.application.learning.idea_cards import IDEA_WRITES
    from campus247.ports.learning_rendition import PDF_MEDIA_TYPE, PPTX_MEDIA_TYPE
    from campus247.presentation.learning import SCHEMAS, create_learning_router
    from fastapi import FastAPI
    destination = destination.absolute()
    if destination.exists() or '..' in destination.parts or not destination.parent.resolve(strict=True).is_relative_to(ROOT):
        raise ValueError('An exact new contract file inside the workspace is required')
    app = FastAPI(title='Campus 24/7 Learning API', version='1.0.0')
    router = create_learning_router(None)
    app.include_router(router)
    # Separate operation IDs for GET and HEAD even when one handler implements both.
    document = app.openapi()
    document['openapi'] = '3.1.2'
    document['servers'] = [{'url': '/'}]
    document['security'] = [{'cookieSession': []}, {'bearerAuth': []}]
    components = document.setdefault('components', {})
    components['securitySchemes'] = {'cookieSession': {'type': 'apiKey', 'in': 'cookie', 'name': 'auth_token'}, 'bearerAuth': {'type': 'http', 'scheme': 'bearer'}}
    schemas = components.setdefault('schemas', {})
    for model in SCHEMAS.values():
        schema = model.model_json_schema(ref_template='#/components/schemas/{model}')
        schemas.update(schema.pop('$defs', {}))
        schemas[model.__name__] = schema
    exit_schemas, exit_responses = exit_ticket_response_contract()
    schemas.update(exit_schemas)
    schemas['LearningUploadInput']['properties']['content_type']['enum'] = [PDF_MEDIA_TYPE, PPTX_MEDIA_TYPE]
    pdf_content = {PDF_MEDIA_TYPE: {'schema': {'type': 'string', 'format': 'binary'}}}
    source_content = pdf_content | {PPTX_MEDIA_TYPE: {'schema': {'type': 'string', 'format': 'binary'}}}
    operation_count = 0
    for route in router.routes:
        for method in route.methods:
            method = method.lower()
            if method not in document['paths'][route.path]:
                continue
            operation = document['paths'][route.path][method]
            operation['security'] = copy.deepcopy(document['security'])
            operation['operationId'] = 'learning_' + method + '_' + route.path.removeprefix('/v1/learning/').replace('/', '_').replace('{', '').replace('}', '').replace('-', '_')
            operation_count += 1
            # FastAPI's dynamic dict transport validates through these Pydantic models.
            action = route.name.removeprefix('learning_')
            if action in SCHEMAS and method in {'post', 'put', 'patch'}:
                operation['requestBody'] = {'required': True, 'content': {'application/json': {'schema': {'$ref': '#/components/schemas/' + SCHEMAS[action].__name__}}}}
            if action in exit_responses:
                operation['responses']['200']['content']['application/json']['schema'] = exit_responses[action]
            if action in {'exit_tickets', 'exit_submissions'}:
                operation.setdefault('parameters', []).extend([
                    {'name': 'limit', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 100}},
                    {'name': 'cursor', 'in': 'query', 'schema': {'type': 'string'}},
                ])
            if action == 'question-update':
                operation['description'] = 'Scope changes require an author-only action preview bound to the question revision, session and exact change. Submit only visibility, revision and confirmation fields when changing scope.'
            if action == 'annotation-share':
                operation['description'] = 'Create a private discussion copy for current instructors after the note owner confirms its exact revision with a signed action preview. The original note remains private.'
            if route.path.endswith('/action-previews'):
                operation['description'] = 'For question-update, provide target_id, visibility and revision in payload. For annotation-share, provide the note target_id and revision in payload. The author receives a private sharing summary and signed confirmation fields.'
            if route.path.endswith('/publication-preview'):
                operation['description'] = 'For retract, replacement_version_id is optional. The response lists eligible published versions of the same material. Confirm with the exact replacement bound to the preview, or omit it to leave no current version.'
            if route.path.endswith('/upload-intents/{upload_id}/content') and method == 'put':
                operation['requestBody'] = {'required': True, 'content': source_content}
            for param in operation.get('parameters', []):
                if param.get('in') == 'path' and param['name'] != 'page_no':
                    param['schema'] = {'type': 'string', 'format': 'uuid'}
            existing_path_names = {p['name'] for p in operation.get('parameters', []) if p.get('in') == 'path'}
            for name in re.findall(r'\{([^}]+)\}', route.path):
                if name not in existing_path_names:
                    operation.setdefault('parameters', []).append({'name': name, 'in': 'path', 'required': True, 'schema': {'type': 'string', 'format': 'uuid'}})
            if method in {'post', 'patch', 'put'}:
                operation.setdefault('parameters', []).extend([
                    {'name': 'Idempotency-Key', 'in': 'header', 'required': action in EXIT_TICKET_WRITES | IDEA_WRITES | OCR_WRITES | {'page-feedback-save', 'page-feedback-withdraw', 'feedback-window-open', 'page-explanation-update', 'version-change-save'} or (method == 'post' and not route.path.endswith(('/action-previews', '/publication-preview', '/abort', '/explain'))), 'schema': {'type': 'string', 'minLength': 16, 'maxLength': 128}},
                    {'name': 'X-Campus-Request', 'in': 'header', 'description': 'Required for cookie-authenticated writes', 'schema': {'type': 'string', 'const': 'learning'}},
                ])
            if route.path.endswith('/me/reader-state/{version_id}'):
                operation.setdefault('parameters', []).append({
                    'name': 'X-Campus-Reader-Actor', 'in': 'header', 'required': False,
                    'description': 'Expected authenticated reader. A mismatch rejects the request before accessing reading position.',
                    'schema': {'type': 'string', 'format': 'uuid'},
                })
            operation.setdefault('responses', {})['default'] = {'description': 'Learning request rejected or dependency unavailable', 'content': {'application/problem+json': {'schema': {'type': 'object', 'required': ['status', 'code'], 'properties': {'status': {'type': 'integer'}, 'code': {'type': 'string'}, 'detail': {'type': 'string'}, 'request_id': {'type': 'string'}}}}}}
            if route.path.endswith(('/content', '/download')) and method in {'get', 'head'}:
                content = source_content if route.path.endswith('/download') else pdf_content
                operation['responses'].update({
                    '200': {'description': 'Authorized file bytes or HEAD metadata', 'content': content},
                    '206': {'description': 'Authorized byte range', 'content': content},
                    '416': {'description': 'Range not satisfiable; Content-Range includes full size'},
                })
                if method == 'head':
                    operation['responses']['200'].pop('content', None)
                    operation['responses'].pop('206', None)
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2)
    return {'path': str(destination), 'operations': operation_count, 'schemas': len(schemas)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.output)))
