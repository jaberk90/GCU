"""
Patch yfinance to use a browser User-Agent.
Yahoo Finance blocks server IPs — spoofing the UA helps avoid rate limits.
Import this at app startup before any yfinance calls.
"""
import requests
from requests.adapters import HTTPAdapter

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def patch_yfinance():
    """Monkey-patch requests session used by yfinance."""
    try:
        import yfinance.utils as yfu
        original_get_json = yfu.get_json

        def patched_get_json(url, proxy=None, session=None):
            if session is None:
                session = requests.Session()
                session.headers.update(HEADERS)
            return original_get_json(url, proxy=proxy, session=session)

        yfu.get_json = patched_get_json
        import logging
        logging.getLogger(__name__).info("yfinance User-Agent patched successfully")
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("yfinance patch failed: %s", e)
