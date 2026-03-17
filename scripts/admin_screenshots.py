"""Take screenshots of the Admin Panel for documentation.

Starts admin_demo.py, captures Tools/Logs/Namespaces tabs via Playwright,
and saves PNGs to docs_en/docs/assets/ and docs_zh/docs/assets/.

Usage:
    conda run -n toolregistry python scripts/admin_screenshots.py
"""

import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

PORT = 8081
BASE_URL = f"http://127.0.0.1:{PORT}"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_EN = PROJECT_ROOT / "docs_en" / "docs" / "assets"
ASSETS_ZH = PROJECT_ROOT / "docs_zh" / "docs" / "assets"

TABS = [
    ("tools", "admin-panel-tools.png"),
    ("logs", "admin-panel-logs.png"),
    ("namespaces", "admin-panel-namespaces.png"),
]


def wait_for_server(url: str, timeout: int = 15) -> None:
    """Poll until the server responds or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urlopen(url, timeout=2)
            return
        except Exception:
            time.sleep(0.3)
    raise TimeoutError(f"Server at {url} did not start within {timeout}s")


def main() -> None:
    # Ensure asset dirs exist
    ASSETS_EN.mkdir(parents=True, exist_ok=True)
    ASSETS_ZH.mkdir(parents=True, exist_ok=True)

    # Start admin_demo.py
    demo_script = PROJECT_ROOT / "examples" / "admin_demo.py"
    print(f"[1/4] Starting {demo_script.name} ...")
    proc = subprocess.Popen(
        [sys.executable, str(demo_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        print(f"[2/4] Waiting for server at {BASE_URL} ...")
        wait_for_server(BASE_URL)
        print("       Server is ready.")

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(BASE_URL)
            # Wait for the UI to fully render
            page.wait_for_selector(".tab.active", timeout=10_000)
            # Small pause so data loads
            page.wait_for_timeout(1000)

            print("[3/4] Taking screenshots ...")
            for tab_name, filename in TABS:
                # Click the tab button
                page.click(f'button.tab[data-tab="{tab_name}"]')
                page.wait_for_timeout(600)

                dest = ASSETS_EN / filename
                page.screenshot(path=str(dest), full_page=False)
                print(f"       Saved {dest.relative_to(PROJECT_ROOT)}")

            browser.close()

        # Copy to ZH assets
        print("[4/4] Copying screenshots to docs_zh/docs/assets/ ...")
        for _, filename in TABS:
            src = ASSETS_EN / filename
            dst = ASSETS_ZH / filename
            shutil.copy2(src, dst)
            print(f"       Copied {dst.relative_to(PROJECT_ROOT)}")

        print("\nDone!")

    finally:
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    main()
