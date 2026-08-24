"""HTTP and JavaScript fetching with graceful escalation.

Escalation ladder used by the scraper:
  1. plain GET on a shared session with automatic retries
  2. on 403 (bot protection), retry via curl (MockResponse shim)
  3. when the page is a JS skeleton (Nuxt) or the team is flagged requires_js,
     render it with shot-scraper
"""
import shutil
import logging
import subprocess

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:106.0) Gecko/20100101 Firefox/106.0'
}
ROSTER_TIMEOUT = 30
BIO_TIMEOUT = 10
JS_TIMEOUT = 45


def build_session() -> requests.Session:
    """A session with retries on transient/rate-limit statuses."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods={'GET', 'HEAD'},
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update(HEADERS)
    return session


# Module-level shared session (connection pooling + retries).
SESSION = build_session()


class MockResponse:
    """Minimal response shim so curl-fetched content flows through code that
    expects a requests.Response."""

    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.text = content.decode('utf-8', errors='replace')
        self.status_code = status_code

    def json(self):
        import json
        return json.loads(self.text)


def fetch_url(url, session=None, timeout=ROSTER_TIMEOUT):
    """GET a URL through the shared session; on 403 fall back to curl (some
    sites block Python's TLS fingerprint but allow curl). Returns a response or
    MockResponse; never raises for HTTP status."""
    session = session or SESSION
    response = session.get(url, timeout=timeout)
    if response.status_code == 403:
        curl = _curl_fetch(url, timeout)
        if curl is not None:
            logger.info(f"Recovered {url} via curl fallback after 403")
            return curl
    return response


def _curl_fetch(url, timeout=ROSTER_TIMEOUT):
    if not shutil.which('curl'):
        return None
    try:
        result = subprocess.run(
            ['curl', '-sL', '--compressed', '--max-time', str(timeout),
             '-A', HEADERS['User-Agent'],
             '-H', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
             url],
            capture_output=True, timeout=timeout + 5,
        )
        if result.returncode == 0 and result.stdout:
            return MockResponse(result.stdout)
    except subprocess.TimeoutExpired:
        logger.warning(f"curl timeout after {timeout}s for {url}")
    except Exception as e:
        logger.warning(f"curl fallback error for {url}: {e}")
    return None


def fetch_html_with_javascript(url, timeout=JS_TIMEOUT):
    """Render a page with shot-scraper (headless Chromium). Returns a
    BeautifulSoup or None."""
    try:
        result = subprocess.run(
            ['uv', 'run', 'shot-scraper', 'html', url, '--wait', '3000'],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            return BeautifulSoup(result.stdout, 'html.parser')
        logger.warning(f"shot-scraper returned code {result.returncode}: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.warning(f"shot-scraper timeout after {timeout}s for {url}")
    except FileNotFoundError:
        logger.error("shot-scraper or uv not found. Install with: uv sync && uv run shot-scraper install")
    except Exception as e:
        logger.error(f"Error running shot-scraper: {e}")
    return None


def is_nuxt_page(html) -> bool:
    """Detect a Nuxt/WMT JS skeleton whose roster is rendered client-side."""
    raw = str(html)
    return '__NUXT_DATA__' in raw or 'window.__NUXT__' in raw
