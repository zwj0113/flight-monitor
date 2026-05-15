import os
import re
import time
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from anti_detect import get_random_ua, random_delay

QUNAR_ONEWAY_URL = "https://flight.qunar.com/site/oneway_list.htm"


def build_search_url(departure_city: str, arrival_city: str, date: str) -> str:
    params = {
        "searchDepartureAirport": departure_city,
        "searchArrivalAirport": arrival_city,
        "searchDepartureTime": date,
    }
    return f"{QUNAR_ONEWAY_URL}?{urlencode(params)}"


def build_all_search_params(
    departure_airports: list[dict],
    arrival_airport: dict,
    return_airports: list[dict],
    outbound_date: str,
    return_date: str,
) -> list[dict]:
    tasks = []

    for dep in departure_airports:
        tasks.append({
            'direction': 'outbound',
            'date': outbound_date,
            'departure_code': dep['code'],
            'departure_city': dep['city'],
            'arrival_code': arrival_airport['code'],
            'arrival_city': arrival_airport['city'],
        })

    for arr in return_airports:
        tasks.append({
            'direction': 'return',
            'date': return_date,
            'departure_code': arrival_airport['code'],
            'departure_city': arrival_airport['city'],
            'arrival_code': arr['code'],
            'arrival_city': arr['city'],
        })

    return tasks


def parse_flight_list_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    flights = []

    for item in soup.select('.m-flight-item'):
        flight_no = item.get('data-flight-no', '')

        airline_el = item.select_one('.m-airline-name')
        airline = airline_el.text.strip() if airline_el else ''

        dep_el = item.select_one('.m-dep-time')
        dep_time = dep_el.text.strip() if dep_el else ''

        arr_el = item.select_one('.m-arr-time')
        arr_time = arr_el.text.strip() if arr_el else ''

        stops_el = item.select_one('.m-flight-stops')
        stops_text = stops_el.text.strip() if stops_el else ''
        stops = 0 if '直飞' in stops_text else _parse_stops_count(stops_text)

        price_el = item.select_one('.m-price-num')
        price = 0
        if price_el:
            price_text = re.sub(r'\D', '', price_el.text)
            price = int(price_text) if price_text else 0

        if flight_no and price > 0:
            flights.append({
                'flight_no': flight_no,
                'airline': airline,
                'dep_time': dep_time,
                'arr_time': arr_time,
                'stops': stops,
                'price': price,
                'price_class': '经济舱',
            })

    return flights


def _parse_stops_count(text: str) -> int:
    match = re.search(r'(\d+)', text)
    return int(match.group(1)) if match else 0


def search_flights(
    departure_city: str,
    arrival_city: str,
    date: str,
    headless: bool = True,
    proxy: str | None = None,
) -> list[dict]:
    from playwright.sync_api import sync_playwright

    url = build_search_url(departure_city, arrival_city, date)
    ua = get_random_ua()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            proxy={'server': proxy} if proxy else None,
        )
        context = browser.new_context(
            user_agent=ua,
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        page = context.new_page()

        try:
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(5000)
            page.wait_for_selector('.m-flight-item', timeout=15000)
            content = page.content()
            flights = parse_flight_list_html(content)
        except Exception as e:
            try:
                os.makedirs('data', exist_ok=True)
                timestamp = time.strftime('%Y%m%d_%H%M%S')
                page.screenshot(path=f'data/captcha_{timestamp}.png')
            except Exception:
                pass
            raise RuntimeError(
                f"Failed to parse flight results for {departure_city}→{arrival_city} {date}: {e}"
            ) from e
        finally:
            context.close()
            browser.close()

    return flights


def search_all_routes(
    search_params: list[dict],
    headless: bool = True,
    proxy: str | None = None,
    min_delay: int = 15,
    max_delay: int = 30,
) -> list[dict]:
    all_flights = []
    total = len(search_params)

    for i, params in enumerate(search_params):
        print(f"[{i+1}/{total}] Searching: {params['departure_city']}→{params['arrival_city']} {params['date']}")
        try:
            flights = search_flights(
                params['departure_city'],
                params['arrival_city'],
                params['date'],
                headless=headless,
                proxy=proxy,
            )
            for f in flights:
                f.update({
                    'direction': params['direction'],
                    'departure_airport': params['departure_code'],
                    'arrival_airport': params['arrival_code'],
                    'date': params['date'],
                })
            all_flights.extend(flights)
            print(f"  -> Found {len(flights)} flights")
        except RuntimeError as e:
            print(f"  -> Error: {e}")
        except Exception as e:
            print(f"  -> Fatal error: {e}. Stopping all searches.")
            break

        if i < total - 1:
            delay = random_delay(min_delay, max_delay)
            time.sleep(delay)

    return all_flights
