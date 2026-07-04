import sys
import types

import pytest

import generator
from generator import _extract_json, _generate_via_hf_api, _get_hf_model_id, _get_hf_token, _parse_script


def test_extract_json_accepts_direct_json():
    assert _extract_json('{"title": "T", "dialogue": []}') == {"title": "T", "dialogue": []}


def test_extract_json_accepts_fenced_json():
    raw = """```json
{"title": "T", "dialogue": []}
```"""
    assert _extract_json(raw)["title"] == "T"


def test_extract_json_accepts_wrapped_object():
    raw = 'Here is the result:\n{"title": "Wrapped", "dialogue": []}\nThanks'
    assert _extract_json(raw)["title"] == "Wrapped"


def test_extract_json_rejects_invalid_output():
    with pytest.raises(ValueError):
        _extract_json("no json here")


def test_parse_script_trims_text_and_defaults_title():
    script = _parse_script({
        "dialogue": [
            {"speaker": "Host", "text": "  Hello  "},
            {"speaker": "Guest", "text": "   "},
        ]
    })

    assert script.title == "Untitled Episode"
    assert len(script.dialogue) == 1
    assert script.dialogue[0].speaker == "Host"
    assert script.dialogue[0].text == "Hello"


def test_parse_script_rejects_empty_dialogue():
    with pytest.raises(ValueError, match="no dialogue"):
        _parse_script({"title": "Empty", "dialogue": [{"speaker": "Host", "text": " "}]})


def test_get_hf_token_prefers_environment(monkeypatch):
    monkeypatch.setenv("HF_TOKEN", "env-token")

    assert _get_hf_token() == "env-token"


def test_get_hf_token_uses_cli_login_cache(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(generator, "_hf_get_token", lambda: "cached-token")

    assert _get_hf_token() == "cached-token"


def test_get_hf_model_id_defaults_to_supported_provider_model(monkeypatch):
    monkeypatch.delenv("HF_MODEL_ID", raising=False)

    assert _get_hf_model_id() == "openai/gpt-oss-120b:fastest"


def test_get_hf_model_id_uses_environment(monkeypatch):
    monkeypatch.setenv("HF_MODEL_ID", "provider/model:fastest")

    assert _get_hf_model_id() == "provider/model:fastest"


def test_generate_via_hf_api_uses_chat_completion_when_available(monkeypatch):
    class Message:
        content = '{"title": "Chat", "dialogue": []}'

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    class FakeInferenceClient:
        def __init__(self, model, token):
            self.model = model
            self.token = token

        def chat_completion(self, messages, max_tokens, temperature):
            assert messages[0]["role"] == "user"
            assert max_tokens == 2048
            assert temperature == 0.7
            return Response()

    fake_hf = types.SimpleNamespace(InferenceClient=FakeInferenceClient)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)
    monkeypatch.setattr(generator, "_get_hf_token", lambda: "token")

    assert _generate_via_hf_api("article") == '{"title": "Chat", "dialogue": []}'


def test_generate_via_hf_api_falls_back_to_text_generation(monkeypatch):
    class FakeInferenceClient:
        def __init__(self, model, token):
            self.model = model
            self.token = token

        def text_generation(self, prompt, max_new_tokens, temperature, return_full_text):
            assert "ARTICLE:\narticle" in prompt
            assert max_new_tokens == 2048
            assert temperature == 0.7
            assert return_full_text is False
            return '{"title": "Text", "dialogue": []}'

    fake_hf = types.SimpleNamespace(InferenceClient=FakeInferenceClient)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hf)
    monkeypatch.setattr(generator, "_get_hf_token", lambda: "token")

    assert _generate_via_hf_api("article") == '{"title": "Text", "dialogue": []}'
