"""
Jarvis AI Assistant — Voice I/O
================================
Speech-to-text (Whisper) and text-to-speech (Edge TTS).
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
from typing import Optional

from config import config

logger = logging.getLogger("jarvis.voice")

_whisper_model = None  # cached across calls

MAX_TTS_CHARS = 2000  # truncate very long responses for TTS


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper model (first call)...")
        _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
        logger.info("Whisper model loaded.")
    return _whisper_model


async def speech_to_text(audio_bytes: bytes) -> str:
    if config.stt_provider == "openai":
        return await _stt_openai(audio_bytes)
    elif config.stt_provider == "local":
        return await _stt_local(audio_bytes)
    else:
        raise ValueError(f"Unknown STT provider: {config.stt_provider}")


async def _stt_openai(audio_bytes: bytes) -> str:
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=config.openai_api_key, timeout=config.api_timeout)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.webm"

        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=config.stt_language,
        )
        return transcript.text.strip()
    except Exception as exc:
        logger.error("OpenAI STT failed: %s", exc)
        raise RuntimeError(f"Speech-to-text failed: {exc}") from exc


async def _stt_local(audio_bytes: bytes) -> str:
    tmp_path = None
    try:
        model = _get_whisper_model()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments, _ = model.transcribe(tmp_path, language=config.stt_language)
        return " ".join(s.text for s in segments).strip()
    except ImportError:
        raise RuntimeError("Local STT requires 'faster-whisper': pip install faster-whisper")
    except Exception as exc:
        logger.error("Local STT failed: %s", exc)
        raise RuntimeError(f"Local speech-to-text failed: {exc}") from exc
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


async def text_to_speech(text: str, voice: Optional[str] = None) -> bytes:
    if not text or not text.strip():
        return b""

    # Truncate very long text to avoid huge audio files
    text = text.strip()
    if len(text) > MAX_TTS_CHARS:
        text = text[:MAX_TTS_CHARS] + "..."

    voice = voice or config.tts_voice

    try:
        import edge_tts

        communicate = edge_tts.Communicate(text, voice)
        audio_chunks: list[bytes] = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            logger.warning("Edge TTS returned no audio for: %s", text[:80])
            return b""

        return b"".join(audio_chunks)
    except Exception as exc:
        logger.error("TTS failed: %s", exc)
        raise RuntimeError(f"Text-to-speech failed: {exc}") from exc
