"""Quick utility to inspect Qunar's actual page structure and CSS selectors.

Usage: python inspect_page.py 上海 乌鲁木齐 2026-09-25
Saves the page HTML to data/snapshot.html for selector analysis.
"""

import os
import sys
from playwright.sync_api import sync_playwright


def inspect_page(departure: str, arrival: str, date: str):
    from searcher import build_search_url

    os.makedirs('data', exist_ok=True)
    url = build_search_url(departure, arrival, date)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            page = browser.new_page(viewport={'width': 1920, 'height': 1080})
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(5000)

            html = page.content()
            with open('data/snapshot.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"Saved {len(html)} bytes to data/snapshot.html")

            screenshot_path = 'data/snapshot.png'
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"Saved {os.path.getsize(screenshot_path)} bytes to {screenshot_path}")
        finally:
            browser.close()


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python inspect_page.py <departure_city> <arrival_city> <date>")
        print("Example: python inspect_page.py 上海 乌鲁木齐 2026-09-25")
        sys.exit(1)
    inspect_page(sys.argv[1], sys.argv[2], sys.argv[3])
