import pytest

from generator import _extract_json, _parse_script


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
