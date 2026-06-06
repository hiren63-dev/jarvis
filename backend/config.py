"""
Jarvis AI Assistant — Configuration Management
================================================
Centralized configuration using dataclasses with environment variable fallback.
Supports multiple LLM providers (OpenAI, Gemini, Anthropic, Ollama) with
automatic provider detection based on available API keys.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load .env file if present (project root or backend dir)
load_dotenv()


@dataclass
class JarvisConfig:
    """Master configuration for the Jarvis AI assistant."""

    # ── LLM Settings ──────────────────────────────────────────────────────
    llm_provider: str = "openai"  # openai | gemini | anthropic | ollama | openrouter
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    model: str = "gpt-4o"  # default model per provider

    # ── Voice Settings ────────────────────────────────────────────────────
    tts_voice: str = "en-US-GuyNeural"  # Microsoft Edge TTS voice
    stt_provider: str = "openai"  # openai | local
    wake_word_enabled: bool = False

    # ── Server Settings ───────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Safety ────────────────────────────────────────────────────────────
    confirm_dangerous_actions: bool = True

    # ── Conversation ──────────────────────────────────────────────────────
    max_history_messages: int = 50  # rolling window for context

    # ── Supabase Database ─────────────────────────────────────────────────
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None

    def __post_init__(self) -> None:
        """Resolve API keys from environment and auto-detect the best provider."""
        # Load LLM settings from env if specified
        self.llm_provider = os.environ.get("LLM_PROVIDER", self.llm_provider)
        self.model = os.environ.get("MODEL", self.model)

        self.openai_api_key = self.openai_api_key or os.environ.get("OPENAI_API_KEY")
        self.gemini_api_key = (
            self.gemini_api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        self.anthropic_api_key = self.anthropic_api_key or os.environ.get(
            "ANTHROPIC_API_KEY"
        )
        self.openrouter_api_key = self.openrouter_api_key or os.environ.get(
            "OPENROUTER_API_KEY"
        )
        self.supabase_url = self.supabase_url or os.environ.get("SUPABASE_URL")
        self.supabase_key = self.supabase_key or os.environ.get("SUPABASE_KEY")

        # Auto-detect provider if default is not overridden in env
        if "LLM_PROVIDER" not in os.environ:
            if self.openrouter_api_key:
                self.llm_provider = "openrouter"
                self.model = "google/gemini-2.0-flash"
            elif self.openai_api_key:
                self.llm_provider = "openai"
                self.model = "gpt-4o"
            elif self.gemini_api_key:
                self.llm_provider = "gemini"
                self.model = "gemini-2.0-flash"
            elif self.anthropic_api_key:
                self.llm_provider = "anthropic"
                self.model = "claude-sonnet-4-20250514"

    @property
    def active_api_key(self) -> Optional[str]:
        """Return the API key for the currently selected provider."""
        return {
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "anthropic": self.anthropic_api_key,
            "openrouter": self.openrouter_api_key,
            "ollama": None,  # Ollama runs locally
        }.get(self.llm_provider)

    def validate(self) -> list[str]:
        """Return a list of configuration warnings/errors."""
        issues: list[str] = []
        if self.llm_provider != "ollama" and not self.active_api_key:
            issues.append(
                f"No API key found for provider '{self.llm_provider}'. "
                f"Set the appropriate environment variable."
            )
        return issues


# Singleton config instance — import this everywhere
config = JarvisConfig()
