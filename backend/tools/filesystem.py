"""
File System Tools
=================
Provides directory listing, file reading/writing, and file search operations.
All functions are synchronous, return strings, and handle errors gracefully.

No external dependencies — uses only the Python standard library.
"""

import fnmatch
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Safety limits
_MAX_READ_CHARS = 5000       # Truncate file reads beyond this
_MAX_SEARCH_RESULTS = 50     # Cap search results to avoid overwhelming output


def list_directory(path: str = ".") -> str:
    """
    List files and folders in a directory with sizes and types.

    Args:
        path: Directory path to list. Defaults to current working directory.

    Returns:
        Formatted listing of directory contents, or an error message.
    """
    try:
        target = Path(path).resolve()

        if not target.exists():
            return f"Error: Path does not exist: {target}"
        if not target.is_dir():
            return f"Error: Not a directory: {target}"

        entries = sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))

        if not entries:
            return f"Directory is empty: {target}"

        lines = [f"Contents of: {target}", f"{'Type':<8} {'Size':>12}  {'Name'}",  "-" * 50]

        for entry in entries:
            try:
                if entry.is_dir():
                    # Count immediate children for directories
                    try:
                        child_count = sum(1 for _ in entry.iterdir())
                        size_str = f"{child_count} items"
                    except PermissionError:
                        size_str = "N/A"
                    lines.append(f"{'[DIR]':<8} {size_str:>12}  {entry.name}/")
                else:
                    size = entry.stat().st_size
                    size_str = _format_size(size)
                    lines.append(f"{'[FILE]':<8} {size_str:>12}  {entry.name}")
            except PermissionError:
                lines.append(f"{'[???]':<8} {'denied':>12}  {entry.name}")
            except Exception as e:
                lines.append(f"{'[ERR]':<8} {'error':>12}  {entry.name}  ({e})")

        lines.append(f"\nTotal: {len(entries)} item(s)")
        return "\n".join(lines)

    except PermissionError:
        return f"Error: Permission denied accessing: {path}"
    except Exception as e:
        error_msg = f"Failed to list directory '{path}': {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


def read_file(path: str) -> str:
    """
    Read and return the contents of a text file.

    Binary files are detected and rejected gracefully. Large files are
    truncated to the first 5000 characters with a warning note appended.

    Args:
        path: Path to the file to read.

    Returns:
        File contents as a string, or an error message.
    """
    try:
        target = Path(path).resolve()

        if not target.exists():
            return f"Error: File does not exist: {target}"
        if not target.is_file():
            return f"Error: Not a file: {target}"

        file_size = target.stat().st_size

        # Quick binary check: read a small chunk and look for null bytes
        try:
            with open(target, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    return (
                        f"Error: '{target.name}' appears to be a binary file "
                        f"({_format_size(file_size)}). Cannot display binary content."
                    )
        except PermissionError:
            return f"Error: Permission denied reading: {target}"

        # Read as text
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(_MAX_READ_CHARS + 1)

        truncated = len(content) > _MAX_READ_CHARS
        if truncated:
            content = content[:_MAX_READ_CHARS]

        result = f"--- {target.name} ({_format_size(file_size)}) ---\n{content}"
        if truncated:
            result += (
                f"\n\n[TRUNCATED: File is {_format_size(file_size)}. "
                f"Only the first {_MAX_READ_CHARS:,} characters are shown.]"
            )

        return result

    except UnicodeDecodeError:
        return f"Error: Could not decode '{path}' as text. It may be a binary file."
    except PermissionError:
        return f"Error: Permission denied reading: {path}"
    except Exception as e:
        error_msg = f"Failed to read file '{path}': {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


def write_file(path: str, content: str) -> str:
    """
    Write content to a file, creating parent directories if needed.

    Args:
        path: Destination file path.
        content: Text content to write.

    Returns:
        Confirmation string or error message.
    """
    try:
        target = Path(path).resolve()

        # Create parent directories if they don't exist
        target.parent.mkdir(parents=True, exist_ok=True)

        with open(target, "w", encoding="utf-8") as f:
            f.write(content)

        written_size = target.stat().st_size
        logger.info("Wrote %s to %s", _format_size(written_size), target)
        return (
            f"Successfully wrote {len(content):,} characters "
            f"({_format_size(written_size)}) to: {target}"
        )

    except PermissionError:
        return f"Error: Permission denied writing to: {path}"
    except OSError as e:
        return f"Error: OS error writing to '{path}': {e}"
    except Exception as e:
        error_msg = f"Failed to write file '{path}': {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


def search_files(directory: str, pattern: str) -> str:
    """
    Recursively search a directory tree for files matching a glob pattern.

    Args:
        directory: Root directory to search in.
        pattern: Glob pattern to match filenames against (e.g. "*.py",
                 "config*.json", "README*").

    Returns:
        Newline-separated list of matching file paths, or an error message.
        Results are capped at 50 matches.
    """
    try:
        root = Path(directory).resolve()

        if not root.exists():
            return f"Error: Directory does not exist: {root}"
        if not root.is_dir():
            return f"Error: Not a directory: {root}"

        matches: list[str] = []
        scanned = 0

        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden directories and common noise
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and d not in ("node_modules", "__pycache__", ".git")
            ]

            for filename in filenames:
                scanned += 1
                if fnmatch.fnmatch(filename, pattern):
                    full_path = os.path.join(dirpath, filename)
                    matches.append(full_path)

                    if len(matches) >= _MAX_SEARCH_RESULTS:
                        result = "\n".join(matches)
                        return (
                            f"Found {len(matches)} matches for '{pattern}' in {root} "
                            f"(results capped at {_MAX_SEARCH_RESULTS}):\n\n{result}"
                        )

        if not matches:
            return (
                f"No files matching '{pattern}' found in {root} "
                f"(scanned {scanned:,} files)."
            )

        result = "\n".join(matches)
        return (
            f"Found {len(matches)} match(es) for '{pattern}' in {root}:\n\n{result}"
        )

    except PermissionError:
        return f"Error: Permission denied accessing: {directory}"
    except Exception as e:
        error_msg = f"Search failed in '{directory}': {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_size(size_bytes: int) -> str:
    """Convert a byte count to a human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
