"""
Web Browsing Tools
==================
Opens URLs and performs web searches in the user's default browser.
Uses only the Python standard library (webbrowser, urllib).
"""

import logging
import urllib.parse
import webbrowser

logger = logging.getLogger(__name__)


def open_url(url: str) -> str:
    """
    Open a URL in the user's default web browser.

    Automatically prepends "https://" if no scheme is provided, so both
    "google.com" and "https://google.com" work.

    Args:
        url: The URL to open. Examples: "https://github.com", "google.com".

    Returns:
        Confirmation string or error message.
    """
    try:
        if not url or not url.strip():
            return "Error: No URL provided."

        url = url.strip()

        # Add scheme if missing (bare domains like "google.com")
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url

        # Basic URL validation
        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc and not parsed.path:
            return f"Error: Invalid URL: {url}"

        success = webbrowser.open(url)

        if success:
            logger.info("Opened URL: %s", url)
            return f"Opened URL in default browser: {url}"
        else:
            return f"Error: Browser reported failure opening: {url}"

    except webbrowser.Error as e:
        return f"Error: Could not open browser: {e}"
    except Exception as e:
        error_msg = f"Failed to open URL '{url}': {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"


def search_web(query: str) -> str:
    """
    Perform a Google search by opening the search results page in the
    default browser.

    The query is URL-encoded to handle special characters safely.

    Args:
        query: The search query string, e.g. "Python asyncio tutorial".

    Returns:
        Confirmation string or error message.
    """
    try:
        if not query or not query.strip():
            return "Error: No search query provided."

        query = query.strip()

        # URL-encode the query to handle special characters
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://www.google.com/search?q={encoded_query}"

        success = webbrowser.open(search_url)

        if success:
            logger.info("Web search: %s", query)
            return f"Opened Google search for: \"{query}\""
        else:
            return f"Error: Browser reported failure opening search for: \"{query}\""

    except webbrowser.Error as e:
        return f"Error: Could not open browser for search: {e}"
    except Exception as e:
        error_msg = f"Web search failed for '{query}': {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"
