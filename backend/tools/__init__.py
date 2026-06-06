"""
Jarvis AI Backend Tools Registry
================================
Central registry that imports and exposes all tool functions.
Each tool is a regular (synchronous) function that returns a string result.
Tools are called from the async brain via asyncio.to_thread().
"""

from .screen import capture_screen, describe_screen
from .computer import click_at, type_text, press_keys, open_application, scroll
from .filesystem import list_directory, read_file, write_file, search_files
from .web import open_url, search_web
from .system import get_current_time, run_shell_command, get_system_info

# Registry mapping tool names to their callable functions.
# The brain uses this dict to dynamically dispatch tool calls by name.
TOOL_REGISTRY = {
    "capture_screen": capture_screen,
    "describe_screen": describe_screen,
    "click_at": click_at,
    "type_text": type_text,
    "press_keys": press_keys,
    "open_application": open_application,
    "scroll": scroll,
    "list_directory": list_directory,
    "read_file": read_file,
    "write_file": write_file,
    "search_files": search_files,
    "open_url": open_url,
    "search_web": search_web,
    "get_current_time": get_current_time,
    "run_shell_command": run_shell_command,
    "get_system_info": get_system_info,
}

__all__ = [
    "TOOL_REGISTRY",
    "capture_screen",
    "describe_screen",
    "click_at",
    "type_text",
    "press_keys",
    "open_application",
    "scroll",
    "list_directory",
    "read_file",
    "write_file",
    "search_files",
    "open_url",
    "search_web",
    "get_current_time",
    "run_shell_command",
    "get_system_info",
]
