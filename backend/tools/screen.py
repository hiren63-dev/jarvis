"""
Screen Capture & Description Tools
===================================
Provides fast screenshot capture using the `mss` library and a helper
that prepares the image for LLM vision analysis in jarvis_brain.py.

Dependencies:
    - mss (pip install mss)
    - Pillow (pip install Pillow)
"""

import base64
import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def capture_screen(monitor_index: int = 1) -> str:
    """
    Capture a screenshot of the primary monitor and return it as a
    base64-encoded JPEG string.

    Uses the `mss` library for high-performance screen capture (much faster
    than PIL.ImageGrab on Windows). The image is compressed to JPEG at
    quality=60 to keep the payload small for network/LLM transmission.

    Args:
        monitor_index: Which monitor to capture. 1 = primary (default).
                       0 = all monitors stitched together.

    Returns:
        Base64-encoded JPEG string of the screenshot, or an error message.
    """
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            # Grab the specified monitor (1-indexed; 0 = all monitors combined)
            monitors = sct.monitors
            if monitor_index >= len(monitors):
                monitor_index = 1  # Fall back to primary monitor
            
            monitor = monitors[monitor_index]
            screenshot = sct.grab(monitor)

            # Convert the raw mss screenshot to a PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            # Encode to JPEG with moderate compression for a good size/quality trade-off
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=60, optimize=True)
            buffer.seek(0)

            # Base64 encode for easy embedding in JSON / LLM messages
            b64_string = base64.b64encode(buffer.getvalue()).decode("utf-8")

            logger.info(
                "Screenshot captured: %dx%d, base64 length=%d",
                img.width,
                img.height,
                len(b64_string),
            )
            return b64_string

    except ImportError as e:
        error_msg = (
            f"Missing dependency for screen capture: {e}. "
            "Install with: pip install mss Pillow"
        )
        logger.error(error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Failed to capture screen: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


def describe_screen() -> str:
    """
    Capture the current screen and return a message indicating the screenshot
    is ready for LLM vision analysis.

    This function does NOT perform the actual image description — that happens
    in jarvis_brain.py, which passes the base64 image to the vision model
    alongside this tool's output.

    Returns:
        A status message with the base64 screenshot embedded, or an error message.
    """
    try:
        screenshot_b64 = capture_screen()

        # If capture_screen returned an error, propagate it
        if screenshot_b64.startswith("Error:"):
            return screenshot_b64

        # Return the screenshot data with a marker so the brain knows to
        # include it as a vision input to the LLM
        return (
            f"[SCREENSHOT_CAPTURED]\n"
            f"Screenshot has been captured and is ready for visual analysis.\n"
            f"Base64 image data length: {len(screenshot_b64)} characters.\n"
            f"[IMAGE_DATA]{screenshot_b64}[/IMAGE_DATA]"
        )

    except Exception as e:
        error_msg = f"Failed to describe screen: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"
