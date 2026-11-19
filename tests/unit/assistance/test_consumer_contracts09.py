"""Strict display/schema tests; no component, DOM or browser execution."""
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from campus247.application.assistance.consumer_contracts import AssistantDisplayContent
from campus247.presentation.assistant_state import SurfaceBody, MetadataBody
from campus247.presentation.chat import CreateMessagePayload, CreateConversationPayload

@pytest.mark.parametrize("block", [
    {"type":"navigation","label":"Approve","path":"/staff","audience":"student"},
    {"type":"navigation","label":"Pay","path":"javascript:alert(1)","audience":"student"},
    {"type":"proposal","title":"Proposal","changes":[],"action_authority":"execute"},
    {"type":"steps","items":["step"],"onClick":"execute"},
    {"type":"table","columns":["a","b"],"rows":[["one"]]},
    {"type":"status","state":"approved","text":"no"},
])
def test_display_cannot_infer_or_encode_executable_authority(block):
    with pytest.raises(ValidationError): AssistantDisplayContent(content="prose can say approve",blocks=[block])


def test_display_schema_keeps_old_text_and_readonly_proposal():
    assert AssistantDisplayContent(content="Legacy **Markdown**").blocks == []
    value = AssistantDisplayContent(content="Short", blocks=[{"type":"proposal","title":"Candidate","changes":[{"field":"purpose","before":"old","after":"new"}]}])
    assert value.blocks[0].action_authority == "none"


@pytest.mark.parametrize("model", [AssistantDisplayContent,SurfaceBody,MetadataBody,CreateMessagePayload,CreateConversationPayload])
def test_exported_consumer_schema_matches_implementation(model):
    root=Path(__file__).resolve().parents[3]
    path=root/"contracts/json-schema/assistance/unified-consumers-v1"/(model.__name__+".schema.json")
    assert json.loads(path.read_text(encoding="utf-8")) == model.model_json_schema()
