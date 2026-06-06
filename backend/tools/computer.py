"""
Computer Control Tools (Mouse & Keyboard)
==========================================
Provides mouse clicks, keyboard typing, hotkeys, application launching,
and scrolling via PyAutoGUI. All functions are synchronous and Windows-focused.

Dependencies:
    - pyautogui (pip install pyautogui)

Safety:
    - FAILSAFE is enabled: move mouse to any screen corner to abort.
    - A small pause (0.1s) is inserted between PyAutoGUI calls to prevent
      input flooding.
"""

import logging
import os
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import pyautogui

    # Safety: moving the mouse to any corner of the screen raises
    # pyautogui.FailSafeException, allowing the user to abort.
    pyautogui.FAILSAFE = True

    # Small delay between every PyAutoGUI action to prevent input flooding
    pyautogui.PAUSE = 0.1

    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False
    logger.warning("pyautogui not installed. Computer control tools will be unavailable.")


def _ensure_pyautogui() -> Optional[str]:
    """Return an error message if pyautogui is not available, else None."""
    if not _PYAUTOGUI_AVAILABLE:
        return "Error: pyautogui is not installed. Run: pip install pyautogui"
    return None


# ---------------------------------------------------------------------------
# Mouse
# ---------------------------------------------------------------------------

def click_at(x: int, y: int) -> str:
    """
    Move the mouse to screen coordinates (x, y) and perform a left click.

    Args:
        x: Horizontal pixel coordinate (0 = left edge of primary monitor).
        y: Vertical pixel coordinate (0 = top edge of primary monitor).

    Returns:
        Confirmation string or error message.
    """
    err = _ensure_pyautogui()
    if err:
        return err

    try:
        # Validate coordinates against screen dimensions
        screen_w, screen_h = pyautogui.size()
        if not (0 <= x < screen_w and 0 <= y < screen_h):
            return (
                f"Error: Coordinates ({x}, {y}) are outside screen bounds "
                f"({screen_w}x{screen_h})."
            )

        pyautogui.click(x, y)
        logger.info("Clicked at (%d, %d)", x, y)
        return f"Clicked at position ({x}, {y})."

    except pyautogui.FailSafeException:
        return "Error: Fail-safe triggered — mouse was moved to a screen corner."
    except Exception as e:
        error_msg = f"Click failed: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


def scroll(direction: str, amount: int = 3) -> str:
    """
    Scroll the mouse wheel up or down.

    Args:
        direction: "up" or "down".
        amount: Number of scroll "clicks" (default 3).

    Returns:
        Confirmation string or error message.
    """
    err = _ensure_pyautogui()
    if err:
        return err

    try:
        direction = direction.strip().lower()
        if direction not in ("up", "down"):
            return f"Error: Invalid scroll direction '{direction}'. Use 'up' or 'down'."

        # PyAutoGUI: positive = scroll up, negative = scroll down
        scroll_amount = amount if direction == "up" else -amount
        pyautogui.scroll(scroll_amount)

        logger.info("Scrolled %s by %d", direction, amount)
        return f"Scrolled {direction} by {amount} units."

    except pyautogui.FailSafeException:
        return "Error: Fail-safe triggered — mouse was moved to a screen corner."
    except Exception as e:
        error_msg = f"Scroll failed: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


# ---------------------------------------------------------------------------
# Keyboard
# ---------------------------------------------------------------------------

def type_text(text: str) -> str:
    """
    Type a string of text character-by-character using the keyboard.

    Uses a small interval (0.02s) between keystrokes to avoid dropped
    characters in fast applications.

    Args:
        text: The text to type. Supports printable ASCII characters.
              For special keys or Unicode, use press_keys() instead.

    Returns:
        Confirmation string or error message.
    """
    err = _ensure_pyautogui()
    if err:
        return err

    try:
        if not text:
            return "Error: No text provided to type."

        pyautogui.write(text, interval=0.02)

        # Truncate logged text for readability
        preview = text[:80] + ("..." if len(text) > 80 else "")
        logger.info("Typed text: %r", preview)
        return f"Typed {len(text)} character(s): \"{preview}\""

    except pyautogui.FailSafeException:
        return "Error: Fail-safe triggered — mouse was moved to a screen corner."
    except Exception as e:
        error_msg = f"Type text failed: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


def press_keys(keys: str) -> str:
    """
    Press a key combination (hotkey).

    Parses a '+'-delimited combo string such as "ctrl+c", "alt+tab",
    "ctrl+shift+s", or a single key like "enter", "escape", "f5".

    Supported modifier names (case-insensitive):
        ctrl, alt, shift, win/windows/cmd/command

    Args:
        keys: Key combo string, e.g. "ctrl+c", "alt+f4", "enter".

    Returns:
        Confirmation string or error message.
    """
    err = _ensure_pyautogui()
    if err:
        return err

    try:
        if not keys or not keys.strip():
            return "Error: No keys provided."

        # Normalize the key combo: split on '+', strip whitespace, lowercase
        key_parts = [k.strip().lower() for k in keys.split("+")]

        # Map common aliases to pyautogui key names
        alias_map = {
            "ctrl": "ctrl",
            "control": "ctrl",
            "alt": "alt",
            "shift": "shift",
            "win": "win",
            "windows": "win",
            "cmd": "win",
            "command": "win",
            "super": "win",
            "esc": "escape",
            "del": "delete",
            "return": "enter",
            "space": "space",
            "spacebar": "space",
            "backspace": "backspace",
            "bs": "backspace",
            "tab": "tab",
            "caps": "capslock",
            "capslock": "capslock",
            "pageup": "pageup",
            "pgup": "pageup",
            "pagedown": "pagedown",
            "pgdn": "pagedown",
            "pgdown": "pagedown",
            "home": "home",
            "end": "end",
            "insert": "insert",
            "ins": "insert",
            "printscreen": "printscreen",
            "prtsc": "printscreen",
            "prtscn": "printscreen",
            "numlock": "numlock",
            "scrolllock": "scrolllock",
        }

        resolved_keys = [alias_map.get(k, k) for k in key_parts]

        # Use hotkey for combos, press for single keys
        if len(resolved_keys) == 1:
            pyautogui.press(resolved_keys[0])
        else:
            pyautogui.hotkey(*resolved_keys)

        combo_str = "+".join(resolved_keys)
        logger.info("Pressed keys: %s", combo_str)
        return f"Pressed key combination: {combo_str}"

    except pyautogui.FailSafeException:
        return "Error: Fail-safe triggered — mouse was moved to a screen corner."
    except Exception as e:
        error_msg = f"Key press failed: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


# ---------------------------------------------------------------------------
# Application Launcher
# ---------------------------------------------------------------------------

# Common Windows application mappings.
# Keys are lowercase aliases; values are the executable or shell command.
_APP_REGISTRY: dict[str, list[str]] = {
    "notepad":      ["notepad.exe"],
    "calculator":   ["calc.exe"],
    "calc":         ["calc.exe"],
    "paint":        ["mspaint.exe"],
    "explorer":     ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "cmd":          ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "powershell":   ["powershell.exe"],
    "terminal":     ["wt.exe"],  # Windows Terminal
    "settings":     ["start", "ms-settings:"],
    "chrome":       [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "google chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox":      [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge":         ["msedge.exe"],
    "microsoft edge": ["msedge.exe"],
    "spotify":      [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
    ],
    "vscode":       ["code"],
    "code":         ["code"],
    "visual studio code": ["code"],
    "task manager": ["taskmgr.exe"],
    "snipping tool": ["snippingtool.exe"],
    "snip":         ["snippingtool.exe"],
    "control panel": ["control.exe"],
    "wordpad":      ["wordpad.exe"],
}


def open_application(name: str) -> str:
    """
    Launch a Windows application by its common name.

    Supports a registry of well-known apps (notepad, chrome, vscode, etc.).
    For unrecognized names, attempts os.startfile() and subprocess.Popen()
    as fallbacks.

    Args:
        name: Application name (case-insensitive), e.g. "chrome", "notepad",
              "vscode", "spotify", "settings".

    Returns:
        Confirmation string or error message.
    """
    try:
        if not name or not name.strip():
            return "Error: No application name provided."

        app_key = name.strip().lower()
        logger.info("Attempting to open application: %s", app_key)

        # --- Try the known-app registry first ---
        if app_key in _APP_REGISTRY:
            candidates = _APP_REGISTRY[app_key]
            last_error = None

            for candidate in candidates:
                try:
                    # Special case: "start" prefix for URI-scheme launches
                    if candidate == "start":
                        # e.g. ["start", "ms-settings:"]
                        uri = candidates[candidates.index(candidate) + 1]
                        os.startfile(uri)
                        logger.info("Opened %s via URI: %s", app_key, uri)
                        return f"Opened {name} (via URI scheme)."

                    # Check if the path exists (for absolute paths)
                    if os.sep in candidate or "/" in candidate:
                        if not os.path.isfile(candidate):
                            continue

                    # Launch with subprocess (detached from Jarvis process)
                    subprocess.Popen(
                        [candidate],
                        shell=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.DETACHED_PROCESS
                        | subprocess.CREATE_NEW_PROCESS_GROUP,
                    )
                    logger.info("Opened %s via: %s", app_key, candidate)
                    return f"Opened {name}."

                except Exception as e:
                    last_error = e
                    continue

            # All candidates failed
            if last_error:
                return f"Error: Could not open {name}. Last error: {last_error}"

        # --- Fallback 1: os.startfile (handles file associations & URIs) ---
        try:
            os.startfile(app_key)
            logger.info("Opened %s via os.startfile()", app_key)
            return f"Opened {name} (via os.startfile)."
        except OSError:
            pass

        # --- Fallback 2: subprocess with shell=True (PATH lookup) ---
        try:
            subprocess.Popen(
                app_key,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            logger.info("Opened %s via shell subprocess", app_key)
            return f"Opened {name} (via shell)."
        except Exception as e:
            pass

        return (
            f"Error: Could not find or open application '{name}'. "
            "Make sure the application is installed and accessible."
        )

    except Exception as e:
        error_msg = f"Failed to open application '{name}': {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"
