"""
Jarvis AI Assistant — Core Brain
==================================
Multi-provider LLM brain with tool/function calling, conversation memory,
and streaming event generation. Supports OpenAI, Gemini, Anthropic, and Ollama.
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import glob
import io
import json
import logging
import os
import platform
import subprocess
import webbrowser
from typing import Any, AsyncGenerator, Optional

import psutil

from config import JarvisConfig, config

logger = logging.getLogger("jarvis.brain")

# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    "You are Jarvis, an advanced AI assistant. You are helpful, witty, and "
    "efficient. You can see the user's screen, control their computer, manage "
    "files, browse the web, and execute commands. Be conversational but concise. "
    "When the user asks you to do something on their computer, use the available "
    "tools. Always explain what you're doing."
)

# ─────────────────────────────────────────────────────────────────────────────
# Tool definitions (OpenAI function-calling schema)
# ─────────────────────────────────────────────────────────────────────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "capture_screen",
            "description": "Capture a screenshot of the current screen. Returns a base64-encoded PNG image.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_screen",
            "description": "Capture the screen and return a text description of what is currently displayed.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click_at",
            "description": "Click the mouse at the specified screen coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"},
                },
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": "Type the given text using the keyboard.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_keys",
            "description": "Press a keyboard shortcut (e.g. 'ctrl+c', 'alt+tab', 'enter').",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": "Key combination, e.g. 'ctrl+c', 'alt+f4', 'enter'",
                    },
                },
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_application",
            "description": "Open an application by name (e.g. 'notepad', 'chrome', 'calculator').",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Application name to open",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll the mouse wheel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right"],
                        "description": "Scroll direction",
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Number of scroll clicks (default 3)",
                    },
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a text file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Creates the file if it doesn't exist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files matching a glob pattern in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g. '*.py', '**/*.txt')",
                    },
                },
                "required": ["directory", "pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a URL in the default web browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to open"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web using Google.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current date and time.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell_command",
            "description": "Run a shell command and return the output. Use with caution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_info",
            "description": "Get system information (CPU, memory, disk, OS).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Tool implementations
# ─────────────────────────────────────────────────────────────────────────────


async def _tool_capture_screen() -> dict[str, Any]:
    """Capture the primary monitor and return base64 PNG."""
    try:
        import mss  # type: ignore[import-untyped]
        from PIL import Image

        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary monitor
            shot = sct.grab(monitor)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return {"success": True, "image": b64, "width": img.width, "height": img.height}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_describe_screen() -> dict[str, Any]:
    """Capture screen and build a text description from window titles."""
    try:
        import mss  # type: ignore[import-untyped]

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            resolution = f"{monitor['width']}x{monitor['height']}"

        # Gather active window info via OS-specific methods
        if platform.system() == "Windows":
            cmd = 'powershell -Command "Get-Process | Where-Object {$_.MainWindowTitle} | Select-Object -Property MainWindowTitle | Format-Table -HideTableHeaders"'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
            windows = [w.strip() for w in result.stdout.strip().splitlines() if w.strip()]
        else:
            windows = ["(window enumeration not implemented on this OS)"]

        description = f"Screen resolution: {resolution}\nVisible windows:\n"
        for w in windows[:15]:
            description += f"  • {w}\n"

        return {"success": True, "description": description}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_click_at(x: int, y: int) -> dict[str, Any]:
    """Click at (x, y) screen coordinates."""
    try:
        import pyautogui  # type: ignore[import-untyped]

        pyautogui.click(x, y)
        return {"success": True, "clicked": {"x": x, "y": y}}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_type_text(text: str) -> dict[str, Any]:
    """Type text via the keyboard."""
    try:
        import pyautogui  # type: ignore[import-untyped]

        pyautogui.typewrite(text, interval=0.02) if text.isascii() else _type_unicode(text)
        return {"success": True, "typed": text[:100]}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _type_unicode(text: str) -> None:
    """Fallback for non-ASCII text: use clipboard."""
    import pyperclip  # type: ignore[import-untyped]
    import pyautogui  # type: ignore[import-untyped]

    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")


async def _tool_press_keys(keys: str) -> dict[str, Any]:
    """Press a keyboard shortcut."""
    try:
        import pyautogui  # type: ignore[import-untyped]

        key_list = [k.strip() for k in keys.split("+")]
        pyautogui.hotkey(*key_list)
        return {"success": True, "pressed": keys}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_open_application(name: str) -> dict[str, Any]:
    """Open an application by name."""
    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(name)  # type: ignore[attr-defined]
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", name])
        else:
            subprocess.Popen([name])
        return {"success": True, "opened": name}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_scroll(direction: str, amount: int = 3) -> dict[str, Any]:
    """Scroll the mouse wheel."""
    try:
        import pyautogui  # type: ignore[import-untyped]

        scroll_map = {"up": amount, "down": -amount, "left": -amount, "right": amount}
        clicks = scroll_map.get(direction, 0)
        if direction in ("left", "right"):
            pyautogui.hscroll(clicks)
        else:
            pyautogui.scroll(clicks)
        return {"success": True, "scrolled": direction, "amount": amount}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_list_directory(path: str) -> dict[str, Any]:
    """List contents of a directory."""
    try:
        path = os.path.expanduser(path)
        entries = []
        for entry in os.scandir(path):
            info: dict[str, Any] = {
                "name": entry.name,
                "is_dir": entry.is_dir(),
            }
            try:
                stat = entry.stat()
                info["size"] = stat.st_size
            except OSError:
                info["size"] = None
            entries.append(info)
        entries.sort(key=lambda e: (not e["is_dir"], e["name"].lower()))
        return {"success": True, "path": path, "entries": entries[:200]}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_read_file(path: str) -> dict[str, Any]:
    """Read a text file."""
    try:
        path = os.path.expanduser(path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(500_000)  # cap at ~500 KB
        return {"success": True, "path": path, "content": content, "length": len(content)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_write_file(path: str, content: str) -> dict[str, Any]:
    """Write content to a file."""
    try:
        path = os.path.expanduser(path)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": path, "bytes_written": len(content)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_search_files(directory: str, pattern: str) -> dict[str, Any]:
    """Glob-search for files."""
    try:
        directory = os.path.expanduser(directory)
        full_pattern = os.path.join(directory, pattern)
        matches = glob.glob(full_pattern, recursive=True)
        return {"success": True, "matches": matches[:200], "count": len(matches)}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_open_url(url: str) -> dict[str, Any]:
    """Open a URL in the default browser."""
    try:
        webbrowser.open(url)
        return {"success": True, "url": url}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_search_web(query: str) -> dict[str, Any]:
    """Open a Google search for the query."""
    try:
        import urllib.parse

        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        webbrowser.open(url)
        return {"success": True, "query": query, "url": url}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_get_current_time() -> dict[str, Any]:
    """Get current date/time."""
    now = datetime.datetime.now()
    return {
        "success": True,
        "datetime": now.isoformat(),
        "formatted": now.strftime("%A, %B %d, %Y at %I:%M %p"),
    }


async def _tool_run_shell_command(command: str) -> dict[str, Any]:
    """Run a shell command."""
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                command, capture_output=True, text=True, shell=True, timeout=30
            )
        else:
            result = subprocess.run(
                command, capture_output=True, text=True, shell=True, timeout=30
            )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:10_000],
            "stderr": result.stderr[:5_000],
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out after 30 seconds"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


async def _tool_get_system_info() -> dict[str, Any]:
    """Gather system information."""
    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return {
            "success": True,
            "os": f"{platform.system()} {platform.release()}",
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": psutil.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": disk.percent,
            "python_version": platform.python_version(),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# Dispatch table
TOOL_DISPATCH: dict[str, Any] = {
    "capture_screen": _tool_capture_screen,
    "describe_screen": _tool_describe_screen,
    "click_at": _tool_click_at,
    "type_text": _tool_type_text,
    "press_keys": _tool_press_keys,
    "open_application": _tool_open_application,
    "scroll": _tool_scroll,
    "list_directory": _tool_list_directory,
    "read_file": _tool_read_file,
    "write_file": _tool_write_file,
    "search_files": _tool_search_files,
    "open_url": _tool_open_url,
    "search_web": _tool_search_web,
    "get_current_time": _tool_get_current_time,
    "run_shell_command": _tool_run_shell_command,
    "get_system_info": _tool_get_system_info,
}


# ─────────────────────────────────────────────────────────────────────────────
# Execute a tool call
# ─────────────────────────────────────────────────────────────────────────────


async def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Look up and execute a tool by name, returning its result dict."""
    handler = TOOL_DISPATCH.get(name)
    if handler is None:
        return {"success": False, "error": f"Unknown tool: {name}"}
    try:
        return await handler(**arguments)
    except TypeError as exc:
        return {"success": False, "error": f"Invalid arguments for {name}: {exc}"}


# ─────────────────────────────────────────────────────────────────────────────
# JarvisBrain — Multi-provider LLM brain
# ─────────────────────────────────────────────────────────────────────────────


class JarvisBrain:
    """
    The central AI brain. Maintains conversation history, calls the configured
    LLM provider with tool definitions, executes tool calls, and streams
    response events back to the caller.
    """

    def __init__(self, cfg: Optional[JarvisConfig] = None, session_id: str = "default") -> None:
        self.config = cfg or config
        self.session_id = session_id

        # Initialize database and load history
        import database
        database.init_db()
        history = database.load_messages(session_id=self.session_id, limit=self.config.max_history_messages)

        self.conversation_history: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]

        # Populate conversation history with stored messages
        for msg in history:
            self.conversation_history.append(msg)

        self.max_tool_iterations = 10  # safety limit for tool-call loops

    def clear_history(self) -> None:
        """Reset conversation to just the system prompt and clear database."""
        self.conversation_history = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        import database
        database.init_db()
        client = database.get_supabase_client()
        if client:
            try:
                client.table("jarvis_memory").delete().eq("session_id", self.session_id).execute()
            except Exception as exc:
                logger.error("Failed to clear Supabase history: %s", exc)
        else:
            try:
                import sqlite3
                conn = sqlite3.connect(database.SQLITE_DB_PATH)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM jarvis_memory WHERE session_id = ?", (self.session_id,))
                conn.commit()
                conn.close()
            except Exception as exc:
                logger.error("Failed to clear SQLite history: %s", exc)

    def _trim_history(self) -> None:
        """Keep conversation within the configured window."""
        max_msgs = self.config.max_history_messages
        # Always keep the system prompt (index 0)
        if len(self.conversation_history) > max_msgs + 1:
            self.conversation_history = [
                self.conversation_history[0]
            ] + self.conversation_history[-(max_msgs):]

    # ── Main entry point ──────────────────────────────────────────────────

    async def process_message(
        self, user_message: str, screenshot: Optional[str] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process a user message and yield event dicts:
            {type: 'thinking'}
            {type: 'action', description: str}
            {type: 'screenshot', image: str}
            {type: 'response', content: str}
            {type: 'done'}
        """
        # Build user message content (optionally with screenshot)
        if screenshot:
            user_content: Any = [
                {"type": "text", "text": user_message},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{screenshot}"},
                },
            ]
        else:
            user_content = user_message

        self.conversation_history.append({"role": "user", "content": user_content})
        self._trim_history()

        # Save user message to database
        import database
        database.save_message("user", user_message, session_id=self.session_id)

        yield {"type": "thinking"}

        # Provider dispatch
        provider = self.config.llm_provider
        response_text = ""

        if provider == "openai":
            async for event in self._process_openai():
                if event.get("type") == "response":
                    response_text += event.get("content", "")
                yield event
        elif provider == "gemini":
            async for event in self._process_gemini():
                if event.get("type") == "response":
                    response_text += event.get("content", "")
                yield event
        elif provider == "anthropic":
            async for event in self._process_anthropic():
                if event.get("type") == "response":
                    response_text += event.get("content", "")
                yield event
        elif provider == "ollama":
            async for event in self._process_ollama():
                if event.get("type") == "response":
                    response_text += event.get("content", "")
                yield event
        else:
            yield {"type": "response", "content": f"Unknown LLM provider: {provider}"}

        # Save assistant response to database
        if response_text:
            import database
            database.save_message("assistant", response_text, session_id=self.session_id)

        yield {"type": "done"}

    # ── OpenAI ────────────────────────────────────────────────────────────

    async def _process_openai(self) -> AsyncGenerator[dict[str, Any], None]:
        """Process with OpenAI's chat completions + function calling."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.config.openai_api_key)

        for _ in range(self.max_tool_iterations):
            response = await client.chat.completions.create(
                model=self.config.model,
                messages=self.conversation_history,  # type: ignore[arg-type]
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
            )
            msg = response.choices[0].message

            # If the model wants to call tools
            if msg.tool_calls:
                # Record assistant message with tool_calls
                self.conversation_history.append(msg.model_dump())

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        fn_args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    yield {"type": "action", "description": f"Calling {fn_name}({fn_args})"}

                    result = await execute_tool(fn_name, fn_args)

                    # If it was a screenshot, emit the image event
                    if fn_name == "capture_screen" and result.get("success") and result.get("image"):
                        yield {"type": "screenshot", "image": result["image"]}

                    # Record tool result
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result),
                    })
            else:
                # Final text response
                text = msg.content or ""
                self.conversation_history.append({"role": "assistant", "content": text})
                yield {"type": "response", "content": text}
                return

        # Safety: if we hit max iterations
        yield {"type": "response", "content": "I've completed several actions. Let me know if you need anything else."}

    # ── Gemini ────────────────────────────────────────────────────────────

    async def _process_gemini(self) -> AsyncGenerator[dict[str, Any], None]:
        """Process with Google Gemini (google-genai SDK)."""
        try:
            from google import genai  # type: ignore[import-untyped]
            from google.genai import types  # type: ignore[import-untyped]
        except ImportError:
            yield {"type": "response", "content": "google-genai library not installed. Run: pip install google-genai"}
            return

        client = genai.Client(api_key=self.config.gemini_api_key)

        # Convert tool definitions to Gemini format
        gemini_functions = []
        for tool_def in TOOL_DEFINITIONS:
            fn = tool_def["function"]
            gemini_functions.append(types.FunctionDeclaration(
                name=fn["name"],
                description=fn["description"],
                parameters=fn["parameters"] if fn["parameters"].get("properties") else None,
            ))

        gemini_tools = [types.Tool(function_declarations=gemini_functions)]

        # Convert conversation history to Gemini format
        gemini_contents = []
        for msg in self.conversation_history:
            if msg["role"] == "system":
                continue  # Handled via system_instruction
            elif msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, list):
                    parts = []
                    for part in content:
                        if part.get("type") == "text":
                            parts.append(types.Part.from_text(text=part["text"]))
                        # Skip image parts for simplicity in Gemini format
                    gemini_contents.append(types.Content(role="user", parts=parts))
                else:
                    gemini_contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=content)],
                    ))
            elif msg["role"] == "assistant":
                content = msg.get("content", "")
                if content:
                    gemini_contents.append(types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=content)],
                    ))

        for _ in range(self.max_tool_iterations):
            response = client.models.generate_content(
                model=self.config.model,
                contents=gemini_contents,
                config=types.GenerateContentConfig(
                    tools=gemini_tools,
                    system_instruction=SYSTEM_PROMPT,
                ),
            )

            # Check for function calls
            has_function_call = False
            function_call_parts = []
            function_response_parts = []

            for part in response.candidates[0].content.parts:
                if part.function_call:
                    has_function_call = True
                    fn_name = part.function_call.name
                    fn_args = dict(part.function_call.args) if part.function_call.args else {}

                    yield {"type": "action", "description": f"Calling {fn_name}({fn_args})"}

                    result = await execute_tool(fn_name, fn_args)

                    if fn_name == "capture_screen" and result.get("success") and result.get("image"):
                        yield {"type": "screenshot", "image": result["image"]}

                    function_call_parts.append(part)
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=fn_name,
                            response=result,
                        )
                    )

            if has_function_call:
                # Add model's function call message
                gemini_contents.append(types.Content(
                    role="model",
                    parts=function_call_parts,
                ))
                # Add function responses
                gemini_contents.append(types.Content(
                    role="user",
                    parts=function_response_parts,
                ))
            else:
                # Final text response
                text = response.text or ""
                self.conversation_history.append({"role": "assistant", "content": text})
                yield {"type": "response", "content": text}
                return

        yield {"type": "response", "content": "I've completed several actions. Let me know if you need anything else."}

    # ── Anthropic ─────────────────────────────────────────────────────────

    async def _process_anthropic(self) -> AsyncGenerator[dict[str, Any], None]:
        """Process with Anthropic Claude (tool_use)."""
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            yield {"type": "response", "content": "anthropic library not installed. Run: pip install anthropic"}
            return

        client = AsyncAnthropic(api_key=self.config.anthropic_api_key)

        # Convert tools to Anthropic format
        anthropic_tools = []
        for tool_def in TOOL_DEFINITIONS:
            fn = tool_def["function"]
            anthropic_tools.append({
                "name": fn["name"],
                "description": fn["description"],
                "input_schema": fn["parameters"],
            })

        # Build messages (exclude system — passed separately)
        messages = []
        for msg in self.conversation_history:
            if msg["role"] == "system":
                continue
            elif msg["role"] == "user":
                content = msg["content"]
                if isinstance(content, list):
                    # Convert image format
                    parts = []
                    for part in content:
                        if part.get("type") == "text":
                            parts.append({"type": "text", "text": part["text"]})
                        elif part.get("type") == "image_url":
                            url = part["image_url"]["url"]
                            if url.startswith("data:image/png;base64,"):
                                b64_data = url.split(",", 1)[1]
                                parts.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": b64_data,
                                    },
                                })
                    messages.append({"role": "user", "content": parts})
                else:
                    messages.append({"role": "user", "content": content})
            elif msg["role"] == "assistant":
                messages.append({"role": "assistant", "content": msg.get("content", "")})

        for _ in range(self.max_tool_iterations):
            response = await client.messages.create(
                model=self.config.model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=anthropic_tools,
            )

            # Process response content blocks
            has_tool_use = False
            assistant_content = []
            tool_results = []

            for block in response.content:
                if block.type == "text":
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    has_tool_use = True
                    assistant_content.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

                    yield {"type": "action", "description": f"Calling {block.name}({block.input})"}

                    result = await execute_tool(block.name, block.input)

                    if block.name == "capture_screen" and result.get("success") and result.get("image"):
                        yield {"type": "screenshot", "image": result["image"]}

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            messages.append({"role": "assistant", "content": assistant_content})

            if has_tool_use:
                messages.append({"role": "user", "content": tool_results})
            else:
                # Extract final text
                text_parts = [b["text"] for b in assistant_content if b.get("type") == "text"]
                text = "\n".join(text_parts)
                self.conversation_history.append({"role": "assistant", "content": text})
                yield {"type": "response", "content": text}
                return

        yield {"type": "response", "content": "I've completed several actions. Let me know if you need anything else."}

    # ── Ollama ────────────────────────────────────────────────────────────

    async def _process_ollama(self) -> AsyncGenerator[dict[str, Any], None]:
        """Process with Ollama (OpenAI-compatible endpoint)."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            yield {"type": "response", "content": "openai library not installed. Run: pip install openai"}
            return

        client = AsyncOpenAI(
            base_url=f"{self.config.ollama_base_url}/v1",
            api_key="ollama",  # Ollama doesn't require a real key
        )

        # Ollama may not support all tools — try with tools first, fall back
        try:
            for _ in range(self.max_tool_iterations):
                response = await client.chat.completions.create(
                    model=self.config.model,
                    messages=self.conversation_history,  # type: ignore[arg-type]
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto",
                )
                msg = response.choices[0].message

                if msg.tool_calls:
                    self.conversation_history.append(msg.model_dump())

                    for tc in msg.tool_calls:
                        fn_name = tc.function.name
                        try:
                            fn_args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            fn_args = {}

                        yield {"type": "action", "description": f"Calling {fn_name}({fn_args})"}

                        result = await execute_tool(fn_name, fn_args)

                        if fn_name == "capture_screen" and result.get("success") and result.get("image"):
                            yield {"type": "screenshot", "image": result["image"]}

                        self.conversation_history.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result),
                        })
                else:
                    text = msg.content or ""
                    self.conversation_history.append({"role": "assistant", "content": text})
                    yield {"type": "response", "content": text}
                    return
        except Exception:
            # Fallback: no tool calling — plain chat
            logger.warning("Ollama tool calling failed, falling back to plain chat")
            response = await client.chat.completions.create(
                model=self.config.model,
                messages=self.conversation_history,  # type: ignore[arg-type]
            )
            text = response.choices[0].message.content or ""
            self.conversation_history.append({"role": "assistant", "content": text})
            yield {"type": "response", "content": text}
