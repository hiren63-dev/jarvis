"""
Jarvis AI Assistant — Configuration Management
================================================
Centralized configuration using dataclasses with environment variable fallback.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass
class JarvisConfig:
    # ── LLM Settings ──────────────────────────────────────────────────────
    llm_provider: str = "openai"
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    model: str = "gpt-4o"

    # ── API Behavior ──────────────────────────────────────────────────────
    max_tokens: int = 4096
    api_timeout: int = 45        # seconds for LLM API calls (OpenRouter friendly)
    tool_timeout: int = 30       # seconds per tool execution
    max_retries: int = 3         # retry failed API calls (exponential backoff)
    retry_delay: float = 2.0     # base backoff seconds

    # ── Voice Settings ────────────────────────────────────────────────────
    tts_voice: str = "en-US-GuyNeural"
    stt_provider: str = "openai"
    stt_language: str = "en"     # language code for STT
    wake_word_enabled: bool = False

    # ── Server Settings ───────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: list = field(default_factory=lambda: ["*"])

    # ── Safety ────────────────────────────────────────────────────────────
    confirm_dangerous_actions: bool = True
    max_message_length: int = 10_000

    # ── Conversation ──────────────────────────────────────────────────────
    max_history_messages: int = 30  # reduced for faster responses

    # ── Cost Tracking ─────────────────────────────────────────────────────
    track_costs: bool = True
    monthly_budget_usd: float = 10.0

    # ── Screenshot Settings ───────────────────────────────────────────────
    screenshot_max_width: int = 1024  # reduced for faster transmission
    screenshot_quality: int = 85      # JPEG quality 1-95 (balanced)

    # ── Supabase Database ─────────────────────────────────────────────────
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    def __post_init__(self) -> None:
        self.llm_provider = os.environ.get("LLM_PROVIDER", self.llm_provider)
        self.model = os.environ.get("MODEL", self.model)
        self.max_tokens = int(os.environ.get("MAX_TOKENS", self.max_tokens))
        self.api_timeout = int(os.environ.get("API_TIMEOUT", self.api_timeout))
        self.tool_timeout = int(os.environ.get("TOOL_TIMEOUT", self.tool_timeout))

        self.openai_api_key = self.openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.gemini_api_key = (
            self.gemini_api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        self.anthropic_api_key = self.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.openrouter_api_key = self.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY")
        self.supabase_url = self.supabase_url or os.environ.get("SUPABASE_URL")
        self.supabase_key = self.supabase_key or os.environ.get("SUPABASE_KEY")
        self.stt_language = os.environ.get("STT_LANGUAGE", self.stt_language)
        self.monthly_budget_usd = float(os.environ.get("MONTHLY_BUDGET_USD", self.monthly_budget_usd))

        if "LLM_PROVIDER" not in os.environ:
            if self.openrouter_api_key:
                self.llm_provider = "openrouter"
                self.model = os.environ.get("MODEL", "google/gemini-2.0-flash")
            elif self.openai_api_key:
                self.llm_provider = "openai"
                self.model = os.environ.get("MODEL", "gpt-4o")
            elif self.gemini_api_key:
                self.llm_provider = "gemini"
                self.model = os.environ.get("MODEL", "gemini-2.0-flash")
            elif self.anthropic_api_key:
                self.llm_provider = "anthropic"
                self.model = os.environ.get("MODEL", "claude-opus-4-5-20251001")

    @property
    def active_api_key(self) -> Optional[str]:
        return {
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "anthropic": self.anthropic_api_key,
            "openrouter": self.openrouter_api_key,
            "ollama": None,
        }.get(self.llm_provider)

    def validate(self) -> list[str]:
        issues: list[str] = []
        if self.llm_provider != "ollama" and not self.active_api_key:
            issues.append(
                f"No API key found for provider '{self.llm_provider}'. "
                f"Set the appropriate environment variable."
            )
        if self.monthly_budget_usd <= 0:
            issues.append("MONTHLY_BUDGET_USD should be > 0")
        return issues


config = JarvisConfig()
