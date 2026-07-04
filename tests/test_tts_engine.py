from pydub import AudioSegment
import pytest

import tts_engine


@pytest.mark.asyncio
async def test_generate_podcast_audio_keeps_original_indexes_for_skipped_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(tts_engine, "AUDIO_CACHE_DIR", tmp_path)
    monkeypatch.setattr(tts_engine, "PAUSE_BETWEEN_SPEAKERS_MS", 0)

    async def fake_synthesize_line(text, speaker, output_path):
        AudioSegment.silent(duration=100).export(output_path, format="wav")
        return output_path

    monkeypatch.setattr(tts_engine, "_synthesize_line", fake_synthesize_line)

    output_path, timing = await tts_engine.generate_podcast_audio(
        [
            {"speaker": "Host", "text": ""},
            {"speaker": "Guest", "text": "First audible line"},
            {"speaker": "Host", "text": "Second audible line"},
        ],
        session_id="abcdef123456",
    )

    assert output_path.endswith("podcast.mp3")
    assert [item["index"] for item in timing] == [1, 2]
    assert [item["text"] for item in timing] == ["First audible line", "Second audible line"]


@pytest.mark.asyncio
async def test_generate_podcast_audio_rejects_all_blank_dialogue(tmp_path, monkeypatch):
    monkeypatch.setattr(tts_engine, "AUDIO_CACHE_DIR", tmp_path)

    async def fail_if_called(text, speaker, output_path):
        raise AssertionError("blank dialogue should not be synthesized")

    monkeypatch.setattr(tts_engine, "_synthesize_line", fail_if_called)

    with pytest.raises(ValueError, match="No audio clips"):
        await tts_engine.generate_podcast_audio([{"speaker": "Host", "text": " "}])
