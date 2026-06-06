"""
Jarvis AI Assistant — FastAPI Server
======================================
WebSocket + REST API server bridging frontend with the Jarvis brain.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator

from config import config
from jarvis_brain import JarvisBrain
from voice import speech_to_text, text_to_speech

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-18s │ %(levelname)-7s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("jarvis.server")

BANNER = r"""
     _   _    ____  __     __ ___  ____
    | | / \  |  _ \ \ \   / /|_ _|/ ___|
 _  | |/ _ \ | |_) | \ \ / /  | | \___ \
| |_| / ___ \|  _ <   \ V /   | |  ___) |
 \___/_/   \_\_| \_\   \_/   |___||____/
"""

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(BANNER)
    print(f"  Provider : {config.llm_provider}")
    print(f"  Model    : {config.model}")
    print(f"  Voice    : {config.tts_voice}")
    print(f"  Server   : http://{config.host}:{config.port}")
    print()

    for w in config.validate():
        logger.warning("⚠  %s", w)

    if FRONTEND_DIR.is_dir():
        logger.info("Serving frontend from %s", FRONTEND_DIR)
    else:
        logger.warning("Frontend directory not found — API-only mode")

    import database
    database.init_db()

    logger.info("Jarvis is online. Awaiting connections…")
    yield
    logger.info("Jarvis shutting down.")


app = FastAPI(
    title="Jarvis AI Assistant",
    description="Advanced AI assistant with computer control capabilities.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check() -> JSONResponse:
    from cost_tracker import total_this_month
    return JSONResponse({
        "status": "ok",
        "provider": config.llm_provider,
        "model": config.model,
        "budget_used_usd": round(total_this_month(), 4),
        "budget_limit_usd": config.monthly_budget_usd,
    })


# ── REST API (for n8n / external integrations) ────────────────────────────────

class ProcessRequest(BaseModel):
    message: str
    session_id: str = "default"

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty")
        if len(v) > config.max_message_length:
            raise ValueError(f"message exceeds {config.max_message_length} chars")
        return v


@app.post("/api/process")
async def api_process(req: ProcessRequest) -> JSONResponse:
    """REST endpoint for n8n / external integrations. Returns final response synchronously."""
    brain = JarvisBrain(session_id=req.session_id)
    events: list[dict] = []
    response_text = ""

    try:
        async for event in brain.process_message(req.message):
            events.append(event)
            if event.get("type") == "response":
                response_text += event.get("content", "")
    except Exception as exc:
        logger.error("REST process error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({
        "success": True,
        "response": response_text,
        "session_id": req.session_id,
        "events": [e for e in events if e.get("type") != "screenshot"],  # omit binary
    })


@app.delete("/api/session/{session_id}")
async def api_clear_session(session_id: str) -> JSONResponse:
    """Clear a session's conversation history."""
    brain = JarvisBrain(session_id=session_id)
    brain.clear_history()
    return JSONResponse({"success": True, "session_id": session_id})


@app.get("/api/costs")
async def api_costs() -> JSONResponse:
    from cost_tracker import summary
    return JSONResponse(summary())


@app.get("/api/config")
async def api_config() -> JSONResponse:
    return JSONResponse({
        "provider": config.llm_provider,
        "model": config.model,
        "tts_voice": config.tts_voice,
        "stt_provider": config.stt_provider,
        "max_history_messages": config.max_history_messages,
        "tool_timeout": config.tool_timeout,
    })


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    session_id = ws.query_params.get("session_id", "default")
    brain = JarvisBrain(session_id=session_id)
    logger.info("Client connected (session=%s)", session_id)

    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=300)
            except asyncio.TimeoutError:
                # Send ping to keep alive
                await _send(ws, {"type": "ping"})
                continue

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, {"type": "error", "message": "Invalid JSON"})
                continue

            msg_type = data.get("type", "")

            if msg_type == "clear":
                brain.clear_history()
                await _send(ws, {"type": "response", "content": "Conversation history cleared."})
                await _send(ws, {"type": "done"})
                continue

            if msg_type == "audio":
                audio_b64 = data.get("audio", "")
                if not audio_b64:
                    await _send(ws, {"type": "error", "message": "No audio data"})
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
                if len(user_text) > config.max_message_length:
                    await _send(ws, {"type": "error", "message": "Message too long"})
                    continue
            else:
                await _send(ws, {"type": "error", "message": f"Unknown type: {msg_type}"})
                continue

            logger.info("User [%s]: %s", session_id, user_text[:120])
            full_response = ""

            try:
                async for event in brain.process_message(user_text):
                    await _send(ws, event)
                    if event.get("type") == "response":
                        full_response += event.get("content", "")

                if full_response.strip():
                    try:
                        audio_bytes = await text_to_speech(full_response)
                        if audio_bytes:
                            await _send(ws, {
                                "type": "audio",
                                "audio": base64.b64encode(audio_bytes).decode("utf-8"),
                            })
                    except Exception as tts_exc:
                        logger.warning("TTS failed (non-fatal): %s", tts_exc)

            except Exception as exc:
                logger.error("Brain error: %s\n%s", exc, traceback.format_exc())
                await _send(ws, {"type": "error", "message": f"Processing error: {exc}"})
                await _send(ws, {"type": "done"})

    except WebSocketDisconnect:
        logger.info("Client disconnected (session=%s)", session_id)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)


async def _send(ws: WebSocket, data: dict) -> None:
    try:
        await ws.send_text(json.dumps(data))
    except Exception as exc:
        logger.warning("Failed to send message: %s", exc)


# ── Static files ──────────────────────────────────────────────────────────────

if FRONTEND_DIR.is_dir():
    @app.get("/")
    async def serve_index() -> FileResponse:
        index = FRONTEND_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return FileResponse(FRONTEND_DIR)

    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")


def main() -> None:
    uvicorn.run("main:app", host=config.host, port=config.port, reload=False, log_level="info")


if __name__ == "__main__":
    main()
