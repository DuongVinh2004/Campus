"""Non-thinking option remains bound to exact destination/model and existing egress controls."""
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services/api/src"))
from campus247.infrastructure.llm.openai_adapter import OpenAICompatibleAdapter
from campus247.infrastructure.llm.egress_policy import EgressPolicy, EgressViolationError
from campus247.ports.llm import LlmRequest

def request():
    return LlmRequest(request_id="fixture", route_id="grounded_faq", model_profile="answer_balanced",
        system_instructions="Synthetic fixture", input_items=({"role":"user","content":"Reply OK."},),
        max_output_tokens=16, deadline_ms=5000)

def test_opt_in_is_exact_and_egress_preserves_only_disabled():
    adapter = OpenAICompatibleAdapter("deepseek", "https://api.deepseek.com", "fixture-key", "deepseek-flash", disable_thinking=True)
    payload = adapter._build_payload(request())
    assert payload["thinking"] == {"type":"disabled"}
    assert payload["max_tokens"] == 16
    assert EgressPolicy().validate_and_minimize({"purpose":"FAQ_ANSWERING", **payload}) == payload
    legacy = OpenAICompatibleAdapter("deepseek", "https://api.deepseek.com", "fixture-key", "deepseek-flash")
    assert "thinking" not in legacy._build_payload(request())

@pytest.mark.parametrize("provider,url,model", [
    ("fixture","https://api.deepseek.com","deepseek-flash"),
    ("deepseek","https://provider.invalid","deepseek-flash"),
    ("deepseek","https://api.deepseek.com","deepseek-chat"),
    ("deepseek","https://api.deepseek.com","deepseek-v4-pro"),
])
def test_option_rejects_other_destination_model_provider(provider,url,model):
    with pytest.raises(ValueError):
        OpenAICompatibleAdapter(provider,url,"fixture-key",model,disable_thinking=True)

@pytest.mark.parametrize("option", [{"type":"enabled"}, {"type":"disabled","extra":"value"}, {}, True, None])
def test_egress_rejects_any_other_thinking_value(option):
    with pytest.raises(EgressViolationError):
        EgressPolicy().validate_and_minimize({"purpose":"FAQ_ANSWERING", "model":"deepseek-flash",
            "messages":[{"role":"user","content":"Reply OK."}], "thinking":option})

def test_egress_rejects_other_model_and_still_blocks_secrets():
    policy = EgressPolicy()
    payload = {"purpose":"FAQ_ANSWERING", "model":"deepseek-chat", "messages":[{"role":"user","content":"Reply OK."}], "thinking":{"type":"disabled"}}
    with pytest.raises(EgressViolationError): policy.validate_and_minimize(payload)
    payload["model"] = "deepseek-flash"
    payload["messages"] = [{"role":"user","content":"sk-fixture-01234567890123456789"}]
    with pytest.raises(EgressViolationError): policy.validate_and_minimize(payload)

def test_other_purpose_does_not_forward_option_or_internal_fields():
    result = EgressPolicy().validate_and_minimize({"purpose":"EMBEDDING", "model":"fixture",
        "input":"Synthetic library hours", "thinking":{"type":"disabled"}, "request_id":"fixture"})
    assert result == {"model":"fixture", "input":"Synthetic library hours"}


def test_json_output_opt_in_is_constant_and_retains_egress_and_operation_bounds():
    adapter = OpenAICompatibleAdapter("deepseek", "https://api.deepseek.com", "fixture-key", "deepseek-flash",
                                      disable_thinking=True, json_mode=True)
    payload = adapter._build_payload(request())
    assert payload["response_format"] == {"type": "json_object"}
    assert EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", **payload}) == payload
    assert payload["max_tokens"] == 16 and payload["thinking"] == {"type": "disabled"}
    payload["messages"] = [{"role": "user", "content": "sk-fixture-01234567890123456789"}]
    with pytest.raises(EgressViolationError):
        EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", **payload})
    with pytest.raises(ValueError):
        OpenAICompatibleAdapter("deepseek", "https://unapproved.invalid", "fixture", "deepseek-flash", json_mode=True)


@pytest.mark.parametrize("value", [{"type": "text"}, {"type": "json_object", "extra": "value"},
    {"type": "json_schema", "json_schema": {}}, {}, True, None])
def test_json_output_other_values_are_rejected(value):
    with pytest.raises(EgressViolationError):
        EgressPolicy().validate_and_minimize({"purpose": "FAQ_ANSWERING", "model": "deepseek-flash",
            "messages": [{"role": "user", "content": "Return JSON."}], "response_format": value})
