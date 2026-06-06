"""
Jarvis AI Assistant — FastAPI Server
======================================
WebSocket-based server that bridges the frontend UI with the Jarvis brain.
Handles text/audio messages, streams response events, and serves static files.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import traceback
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import config
from jarvis_brain import JarvisBrain
from voice import speech_to_text, text_to_speech

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-18s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis.server")

# ── Constants ─────────────────────────────────────────────────────────────────

BANNER = r"""
     _   _    ____  __     __ ___  ____
    | | / \  |  _ \ \ \   / /|_ _|/ ___|
 _  | |/ _ \ | |_) | \ \ / /  | | \___ \
| |_| / ___ \|  _ <   \ V /   | |  ___) |
 \___/_/   \_\_| \_\   \_/   |___||____/
"""

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Startup / shutdown lifecycle hook."""
    # ── Startup ───────────────────────────────────────────────────────────
    print(BANNER)
    print(f"  Provider : {config.llm_provider}")
    print(f"  Model    : {config.model}")
    print(f"  Voice    : {config.tts_voice}")
    print(f"  Server   : http://{config.host}:{config.port}")
    print()

    warnings = config.validate()
    for w in warnings:
        logger.warning("⚠  %s", w)

    if FRONTEND_DIR.is_dir():
        logger.info("Serving frontend from %s", FRONTEND_DIR)
    else:
        logger.warning("Frontend directory not found at %s — API-only mode", FRONTEND_DIR)

    logger.info("Jarvis is online. Awaiting connections…")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("Jarvis shutting down. Goodbye!")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Jarvis AI Assistant",
    description="Advanced AI assistant with computer control capabilities.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow any origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check() -> JSONResponse:
    """Health-check endpoint."""
    return JSONResponse({
        "status": "ok",
        "provider": config.llm_provider,
        "model": config.model,
    })


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    """
    Main WebSocket endpoint for real-time communication.

    Expected client messages (JSON):
        {type: "text",  content: "<user message>"}
        {type: "audio", audio: "<base64 audio data>"}
        {type: "clear"} — reset conversation history

    Server sends events (JSON):
        {type: "transcription", content: str}
        {type: "thinking"}
        {type: "response",    content: str}
        {type: "audio",       audio: str}       (base64 MP3)
        {type: "action",      description: str}
        {type: "screenshot",  image: str}       (base64 PNG)
        {type: "done"}
        {type: "error",       message: str}
    """
    await ws.accept()
    brain = JarvisBrain()
    logger.info("Client connected via WebSocket")

    try:
        while True:
            raw = await ws.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, {"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type", "")

            # ── Clear history ─────────────────────────────────────────────
            if msg_type == "clear":
                brain.clear_history()
                await _send(ws, {"type": "response", "content": "Conversation history cleared."})
                await _send(ws, {"type": "done"})
                continue

            # ── Audio message ─────────────────────────────────────────────
            if msg_type == "audio":
                audio_b64 = data.get("audio", "")
                if not audio_b64:
                    await _send(ws, {"type": "error", "message": "No audio data provided"})
                    continue

                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    user_text = await speech_to_text(audio_bytes)
                    await _send(ws, {"type": "transcription", "content": user_text})
                except Exception as exc:
                    logger.error("STT error: %s", exc)
                    await _send(ws, {"type": "error", "message": f"Transcription failed: {exc}"})
                    continue
            elif msg_type == "text":
                user_text = data.get("content", "").strip()
                if not user_text:
                    await _send(ws, {"type": "error", "message": "Empty message"})
                    continue
            else:
                await _send(ws, {"type": "error", "message": f"Unknown message type: {msg_type}"})
                continue

            # ── Process through brain ─────────────────────────────────────
            logger.info("User: %s", user_text[:120])
            full_response = ""

            try:
                async for event in brain.process_message(user_text):
                    await _send(ws, event)

                    # Collect text for TTS
                    if event.get("type") == "response":
                        full_response += event.get("content", "")

                # ── Generate TTS audio ────────────────────────────────────
                if full_response.strip():
                    try:
                        audio_bytes = await text_to_speech(full_response)
                        if audio_bytes:
                            audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
                            await _send(ws, {"type": "audio", "audio": audio_b64})
                    except Exception as tts_exc:
                        logger.warning("TTS failed (non-fatal): %s", tts_exc)

            except Exception as exc:
                logger.error("Brain processing error: %s\n%s", exc, traceback.format_exc())
                await _send(ws, {"type": "error", "message": f"Processing error: {exc}"})
                await _send(ws, {"type": "done"})

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)


async def _send(ws: WebSocket, data: dict) -> None:  # type: ignore[type-arg]
    """Send a JSON message over the WebSocket."""
    try:
        await ws.send_text(json.dumps(data))
    except Exception as exc:
        logger.warning("Failed to send WebSocket message: %s", exc)


# ── Static files (frontend) ──────────────────────────────────────────────────

if FRONTEND_DIR.is_dir():
    # Serve index.html at root
    @app.get("/")
    async def serve_index() -> FileResponse:
        """Serve the frontend index.html."""
        index = FRONTEND_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return FileResponse(FRONTEND_DIR)

    # Serve all other static assets
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    """Start the Jarvis server."""
    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
