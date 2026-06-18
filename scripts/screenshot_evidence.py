"""
Capture a full-page screenshot of the running Evidence dashboard to /artifacts,
as proof that the BI site builds and renders (Verification Gate 6).

Usage:
    python scripts/screenshot_evidence.py [URL] [OUTPUT_PNG]

Defaults: URL=http://localhost:3001  OUTPUT=artifacts/evidence_dashboard.png
Waits for the page to be reachable and for charts to render before shooting.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3001"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("artifacts/evidence_dashboard.png")


def wait_for_server(url: str, attempts: int = 60, delay: int = 5) -> None:
    for i in range(1, attempts + 1):
        try:
            with urlopen(url, timeout=5) as r:
                if r.status == 200:
                    print(f"server up at {url} (attempt {i})")
                    return
        except Exception as exc:  # noqa: BLE001
            print(f"  waiting for {url} ({i}/{attempts}): {exc.__class__.__name__}")
            time.sleep(delay)
    raise SystemExit(f"Evidence server not reachable at {url}")


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wait_for_server(URL)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(URL, wait_until="networkidle", timeout=120_000)
        # Give Evidence's client-side charts time to query + render.
        page.wait_for_timeout(8000)
        page.screenshot(path=str(OUT), full_page=True)
        browser.close()
    size = OUT.stat().st_size
    print(f"Wrote {OUT} ({size:,} bytes)")
    if size < 10_000:
        raise SystemExit("Screenshot suspiciously small; render may have failed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
