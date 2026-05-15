from urllib.parse import urlencode

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


import re
from bs4 import BeautifulSoup


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
