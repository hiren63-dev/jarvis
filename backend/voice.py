"""
Jarvis AI Assistant — Voice I/O
================================
Speech-to-text (via OpenAI Whisper) and text-to-speech (via Edge TTS).
"""

from __future__ import annotations

import io
import logging
from typing import Optional

from config import config

logger = logging.getLogger("jarvis.voice")


# ── Speech-to-Text ────────────────────────────────────────────────────────────


async def speech_to_text(audio_bytes: bytes) -> str:
    """
    Transcribe raw audio bytes to text.

    Uses OpenAI Whisper API by default; falls back to a stub for the
    'local' provider (integrate faster-whisper here if desired).

    Args:
        audio_bytes: Raw audio data (WAV/WebM/MP3).

    Returns:
        Transcribed text string.
    """
    if config.stt_provider == "openai":
        return await _stt_openai(audio_bytes)
    elif config.stt_provider == "local":
        return await _stt_local(audio_bytes)
    else:
        raise ValueError(f"Unknown STT provider: {config.stt_provider}")


async def _stt_openai(audio_bytes: bytes) -> str:
    """Transcribe audio using the OpenAI Whisper API."""
    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=config.openai_api_key)

        # Wrap bytes in a file-like object with a name so the API can
        # infer the format. Default to webm which browsers typically send.
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "recording.webm"

        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en",
        )
        return transcript.text.strip()
    except Exception as exc:
        logger.error("OpenAI STT failed: %s", exc)
        raise RuntimeError(f"Speech-to-text failed: {exc}") from exc


async def _stt_local(audio_bytes: bytes) -> str:
    """
    Transcribe audio using a local Whisper model (faster-whisper).

    Requires `faster-whisper` to be installed:
        pip install faster-whisper
    """
    try:
        import tempfile
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]

        model = WhisperModel("base", device="cpu", compute_type="int8")

        # faster-whisper needs a file path; write to a temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments, _info = model.transcribe(tmp_path, language="en")
        text = " ".join(segment.text for segment in segments).strip()

        # Clean up temp file
        import os
        os.unlink(tmp_path)

        return text
    except ImportError:
        raise RuntimeError(
            "Local STT requires 'faster-whisper'. Install with: pip install faster-whisper"
        )
    except Exception as exc:
        logger.error("Local STT failed: %s", exc)
        raise RuntimeError(f"Local speech-to-text failed: {exc}") from exc


# ── Text-to-Speech ────────────────────────────────────────────────────────────


async def text_to_speech(text: str, voice: Optional[str] = None) -> bytes:
    """
    Convert text to speech audio bytes (MP3) using Microsoft Edge TTS.

    Args:
        text: The text to synthesize.
        voice: Override voice name (e.g. "en-US-GuyNeural").

    Returns:
        MP3 audio bytes.
    """
    if not text or not text.strip():
        return b""

    voice = voice or config.tts_voice

    try:
        import edge_tts  # type: ignore[import-untyped]

        communicate = edge_tts.Communicate(text, voice)
        audio_chunks: list[bytes] = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            logger.warning("Edge TTS returned no audio chunks for: %s", text[:80])
            return b""

        return b"".join(audio_chunks)
    except Exception as exc:
        logger.error("Text-to-speech failed: %s", exc)
        raise RuntimeError(f"Text-to-speech failed: {exc}") from exc
