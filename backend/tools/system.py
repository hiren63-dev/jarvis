"""
System Information & Shell Command Tools
=========================================
Provides current time, shell command execution, and system resource
monitoring (CPU, RAM, disk) via psutil.

Dependencies:
    - psutil (pip install psutil)  — for get_system_info()
"""

import datetime
import logging
import platform
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Safety limits
_COMMAND_TIMEOUT = 30     # seconds
_MAX_OUTPUT_CHARS = 3000  # truncate shell output beyond this


def get_current_time() -> str:
    """
    Return the current date, time, day of week, and timezone in a
    human-readable format.

    Returns:
        Formatted datetime string.
    """
    try:
        now = datetime.datetime.now()
        utc_now = datetime.datetime.now(datetime.timezone.utc)

        # Compute UTC offset
        local_tz = now.astimezone().tzinfo
        tz_name = str(local_tz)

        # Try to get a friendlier timezone name
        try:
            tz_name = now.astimezone().strftime("%Z")
        except Exception:
            pass

        utc_offset = now.astimezone().strftime("%z")
        # Format as "+05:30" style
        if len(utc_offset) >= 5:
            utc_offset = utc_offset[:3] + ":" + utc_offset[3:]

        return (
            f"Current Date & Time:\n"
            f"  Date      : {now.strftime('%A, %B %d, %Y')}\n"
            f"  Time      : {now.strftime('%I:%M:%S %p')}\n"
            f"  Day       : {now.strftime('%A')}\n"
            f"  Timezone  : {tz_name} (UTC{utc_offset})\n"
            f"  ISO 8601  : {now.isoformat()}"
        )

    except Exception as e:
        error_msg = f"Failed to get current time: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


def run_shell_command(command: str) -> str:
    """
    Execute a shell command and return its output.

    Runs the command via subprocess with a 30-second timeout. Both stdout
    and stderr are captured and returned. Output is truncated to 3000
    characters to prevent overwhelming the LLM context.

    **Security Note**: This executes arbitrary commands. The Jarvis brain
    should validate/sanitize commands before calling this tool.

    Args:
        command: The shell command to execute (e.g. "dir", "ipconfig",
                 "python --version").

    Returns:
        Combined stdout and stderr output, or an error message.
    """
    try:
        if not command or not command.strip():
            return "Error: No command provided."

        command = command.strip()
        logger.info("Executing shell command: %s", command)

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_COMMAND_TIMEOUT,
            # Run in a new process group so it doesn't inherit Jarvis's console
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            if platform.system() == "Windows"
            else 0,
        )

        # Combine stdout and stderr
        output_parts: list[str] = []

        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            # Prefix stderr so the LLM can distinguish it
            output_parts.append(f"[STDERR]\n{result.stderr}")

        output = "\n".join(output_parts).strip()

        if not output:
            output = "(Command produced no output)"

        # Append exit code if non-zero
        if result.returncode != 0:
            output += f"\n\n[Exit code: {result.returncode}]"

        # Truncate long output
        if len(output) > _MAX_OUTPUT_CHARS:
            output = output[:_MAX_OUTPUT_CHARS] + (
                f"\n\n[TRUNCATED: Output was {len(output):,} characters. "
                f"Only the first {_MAX_OUTPUT_CHARS:,} are shown.]"
            )

        return output

    except subprocess.TimeoutExpired:
        return (
            f"Error: Command timed out after {_COMMAND_TIMEOUT} seconds: "
            f"'{command}'"
        )
    except FileNotFoundError:
        return f"Error: Command not found: '{command}'"
    except PermissionError:
        return f"Error: Permission denied executing: '{command}'"
    except Exception as e:
        error_msg = f"Command execution failed: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


def get_system_info() -> str:
    """
    Return current system resource usage and platform information.

    Uses psutil to report CPU usage, RAM usage, disk usage, and basic
    platform metadata (OS, architecture, hostname).

    Returns:
        Formatted system info string, or an error message.
    """
    try:
        info_lines: list[str] = ["=== System Information ===", ""]

        # --- Platform info (no dependencies) ---
        info_lines.append("Platform:")
        info_lines.append(f"  OS          : {platform.system()} {platform.release()}")
        info_lines.append(f"  Version     : {platform.version()}")
        info_lines.append(f"  Machine     : {platform.machine()}")
        info_lines.append(f"  Processor   : {platform.processor() or 'N/A'}")
        info_lines.append(f"  Hostname    : {platform.node()}")
        info_lines.append(f"  Python      : {platform.python_version()}")
        info_lines.append("")

        # --- Resource usage (requires psutil) ---
        try:
            import psutil

            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count_logical = psutil.cpu_count(logical=True)
            cpu_count_physical = psutil.cpu_count(logical=False)
            cpu_freq = psutil.cpu_freq()

            info_lines.append("CPU:")
            info_lines.append(f"  Usage       : {cpu_percent}%")
            info_lines.append(
                f"  Cores       : {cpu_count_physical} physical, "
                f"{cpu_count_logical} logical"
            )
            if cpu_freq:
                info_lines.append(f"  Frequency   : {cpu_freq.current:.0f} MHz")
            info_lines.append("")

            # Memory
            mem = psutil.virtual_memory()
            info_lines.append("Memory (RAM):")
            info_lines.append(f"  Total       : {_format_bytes(mem.total)}")
            info_lines.append(f"  Used        : {_format_bytes(mem.used)} ({mem.percent}%)")
            info_lines.append(f"  Available   : {_format_bytes(mem.available)}")
            info_lines.append("")

            # Disk (all partitions)
            info_lines.append("Disk:")
            for partition in psutil.disk_partitions(all=False):
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    info_lines.append(
                        f"  {partition.device} ({partition.mountpoint}):"
                    )
                    info_lines.append(
                        f"    Total     : {_format_bytes(usage.total)}"
                    )
                    info_lines.append(
                        f"    Used      : {_format_bytes(usage.used)} ({usage.percent}%)"
                    )
                    info_lines.append(
                        f"    Free      : {_format_bytes(usage.free)}"
                    )
                except PermissionError:
                    info_lines.append(
                        f"  {partition.device}: Permission denied"
                    )
            info_lines.append("")

            # Network (basic)
            net = psutil.net_io_counters()
            info_lines.append("Network:")
            info_lines.append(f"  Sent        : {_format_bytes(net.bytes_sent)}")
            info_lines.append(f"  Received    : {_format_bytes(net.bytes_recv)}")

            # Battery (if available, e.g. laptops)
            battery = psutil.sensors_battery()
            if battery:
                info_lines.append("")
                info_lines.append("Battery:")
                info_lines.append(f"  Charge      : {battery.percent}%")
                info_lines.append(
                    f"  Plugged In  : {'Yes' if battery.power_plugged else 'No'}"
                )
                if battery.secsleft > 0 and not battery.power_plugged:
                    hours, remainder = divmod(battery.secsleft, 3600)
                    minutes = remainder // 60
                    info_lines.append(
                        f"  Time Left   : {int(hours)}h {int(minutes)}m"
                    )

        except ImportError:
            info_lines.append(
                "Resource Usage: psutil not installed. "
                "Run 'pip install psutil' for CPU/RAM/disk stats."
            )

        return "\n".join(info_lines)

    except Exception as e:
        error_msg = f"Failed to get system info: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_bytes(size_bytes: int) -> str:
    """Convert a byte count to a human-readable size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"
