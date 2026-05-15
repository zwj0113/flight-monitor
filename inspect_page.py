"""Quick utility to inspect Qunar's actual page structure and CSS selectors.

Usage: python inspect_page.py 上海 乌鲁木齐 2026-09-25
Saves the page HTML to data/snapshot.html for selector analysis.
"""

import sys
from playwright.sync_api import sync_playwright


def inspect_page(departure: str, arrival: str, date: str):
    url = (
        "https://flight.qunar.com/site/oneway_list.htm?"
        f"searchDepartureAirport={departure}"
        f"&searchArrivalAirport={arrival}"
        f"&searchDepartureTime={date}"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(5000)

        html = page.content()
        with open('data/snapshot.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"Saved {len(html)} bytes to data/snapshot.html")

        page.screenshot(path='data/snapshot.png', full_page=True)
        print("Saved screenshot to data/snapshot.png")
        browser.close()


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print("Usage: python inspect_page.py <departure_city> <arrival_city> <date>")
        print("Example: python inspect_page.py 上海 乌鲁木齐 2026-09-25")
        sys.exit(1)
    inspect_page(sys.argv[1], sys.argv[2], sys.argv[3])
