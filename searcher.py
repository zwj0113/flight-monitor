import math
import os
import time

from anti_detect import get_random_ua, random_delay

# Fee constants (2026-05-16 起执行)
AIRPORT_FEE = 50       # 民航发展基金（机建费）
FUEL_SHORT = 90        # 燃油附加费 ≤800km
FUEL_LONG = 170        # 燃油附加费 >800km

# Airport coordinates (latitude, longitude)
_AIRPORT_COORDS = {
    'SHA': (31.1979, 121.3363),   # 上海虹桥
    'PVG': (31.1434, 121.8052),   # 上海浦东
    'HGH': (30.2295, 120.4344),   # 杭州萧山
    'NKG': (31.7420, 118.8620),   # 南京禄口
    'WUX': (31.4944, 120.4291),   # 无锡硕放
    'CZX': (31.9197, 119.7787),   # 常州奔牛
    'NTG': (32.0708, 120.9765),   # 南通兴东
    'URC': (43.9071, 87.4742),    # 乌鲁木齐地窝堡
}

# Airport short Chinese names for display
_AIRPORT_CN = {
    'SHA': '上海虹桥', 'PVG': '上海浦东', 'HGH': '杭州萧山',
    'NKG': '南京禄口', 'WUX': '无锡硕放', 'CZX': '常州奔牛',
    'NTG': '南通兴东', 'URC': '乌鲁木齐天山',
}

# Price channel key -> Chinese name
_CHANNEL_CN = {
    'JPFWB': '机票服务包', 'GFFX_HO': '吉祥官方旗舰',
    'YC_QJ': '优程旗舰', 'CC_QJ': '差旅旗舰',
    'CZCW': '畅行舱位', 'NLXZ': '南航直销',
    'RSXZ': '日上优选', 'JJCZL': '经济舱直连',
    'JJCZL_CZ': '经济舱直连(南航)', 'JJCZL_MU': '经济舱直连(东航)',
    'JJCZL_FM': '经济舱直连(上航)',
    'SWYX_DS_ZX': '商务优选(电商)', 'SWYX_LM_ZX': '商务优选(联盟)',
    'B2T_ZS': 'B2T直省', 'PTZC_HSHY': '普通政策',
    'CC_ZDJ': '差旅自定价', 'ZLHS_HY': '中联航惠',
    'GFFX': '官方飞行', 'HSZX_CCZDJ': '航司直连',
}

# Price groupType -> Chinese name (fallback when key not in _CHANNEL_CN)
_GROUP_CN = {
    'Airline': '航司直连', 'Priority': '优选',
    'Service_Packages': '服务包', 'Favorable': '特惠',
}


def _channel_cn(key: str, group_type: str) -> str:
    """Return Chinese name for a price channel."""
    if key in _CHANNEL_CN:
        return _CHANNEL_CN[key]
    return _GROUP_CN.get(group_type, group_type)


def _airport_display(code: str, full_name: str) -> str:
    """Return 'CODE(短中文名)' format for airport display."""
    if code in _AIRPORT_CN:
        short = _AIRPORT_CN[code]
    else:
        short = full_name.replace('国际机场', '').replace('机场', '')
    return f"{code}({short})"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _get_airport_distance(dep_code: str, arr_code: str) -> float:
    """Look up coordinates and compute distance between two airports."""
    lat1, lon1 = _AIRPORT_COORDS[dep_code]
    lat2, lon2 = _AIRPORT_COORDS[arr_code]
    return _haversine_km(lat1, lon1, lat2, lon2)


def _get_fuel_surcharge(dep_code: str, arr_code: str) -> int:
    """Return fuel surcharge based on flight distance."""
    distance = _get_airport_distance(dep_code, arr_code)
    return FUEL_SHORT if distance <= 800 else FUEL_LONG

CTRIP_COOKIE_URL = "https://m.ctrip.com/"
CTRIP_SEARCH_URL = "https://flights.ctrip.com/online/list/oneway-{dep}-{arr}?depdate={date}&cabin=y_s&adult=1&child=0&infant=0"


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


def _parse_batch_search_response(
    data: dict,
    direction: str,
    dep_code: str,
    arr_code: str,
    date: str,
    free_baggage_only: bool = True,
) -> list[dict]:
    """Parse batchSearch API response and return direct flights only.

    Real API structure:
      response.data.flightItineraryList[]
        .flightSegments[]          — transferCount, stopCount, airlineName
          .flightList[]            — flightNo, departureDateTime, arrivalDateTime,
                                     aircraftCode, aircraftName, departureAirportName,
                                     arrivalAirportName, departureTerminal, arrivalTerminal,
                                     duration, operateAirlineName, operateFlightNo
        .priceList[]               — adultPrice (裸票价，不含税费), cabin, baggage

    Filters for flights where all segments have transferCount==0 and stopCount==0.
    Adds fuel surcharge (¥90/¥170 based on distance) and airport fee (¥50).
    When free_baggage_only is True, filters out flights without free checked baggage.
    """
    inner = data.get('data', data)
    itinerary_list = inner.get('flightItineraryList', [])
    flights = []

    for item in itinerary_list:
        segments = item.get('flightSegments', [])

        # Check if all segments are direct non-stop
        if not segments:
            continue
        if any(
            seg.get('transferCount', 0) != 0 or seg.get('stopCount', 0) != 0
            for seg in segments
        ):
            continue

        # Take the first segment's first flight for flight info
        first_seg = segments[0]
        flight_list = first_seg.get('flightList', [])
        if not flight_list:
            continue
        first_flight = flight_list[0]

        flight_no = first_flight.get('flightNo', '')
        airline = first_seg.get('airlineName', '')
        dep_time = first_flight.get('departureDateTime', '')
        arr_time = first_flight.get('arrivalDateTime', '')

        # New fields from flightList
        aircraft_code = first_flight.get('aircraftCode', '')
        aircraft_name = first_flight.get('aircraftName', '')
        dep_airport_name = first_flight.get('departureAirportName', '')
        arr_airport_name = first_flight.get('arrivalAirportName', '')
        dep_terminal = first_flight.get('departureTerminal', '')
        arr_terminal = first_flight.get('arrivalTerminal', '')
        duration_minutes = first_flight.get('duration', 0)
        operate_airline = first_flight.get('operateAirlineName', '')
        operate_flight_no = first_flight.get('operateFlightNo', '')

        # Get the cheapest adult price from priceList
        price_list = item.get('priceList', [])
        adult_price = min(
            (p.get('adultPrice', float('inf')) for p in price_list),
            default=0,
        )
        if not adult_price or adult_price <= 0 or adult_price == float('inf'):
            continue

        # Channel info from the first price entry
        price_key = ''
        group_type = ''
        if price_list:
            price_key = price_list[0].get('key', '') or ''
            group_type = price_list[0].get('groupType', '') or ''
        price_channel_cn = _channel_cn(price_key, group_type)

        # Baggage info from the first price entry
        baggage_tag = ''
        free_baggage = False
        if price_list:
            try:
                baggage = price_list[0].get('baggage', {})
                if baggage:
                    baggage_tag = baggage.get('baggageTag', '')
                    data_list = baggage.get('dataList', [])
                    if data_list:
                        adult_baggage = data_list[0].get('adultBaggage', {})
                        checked = adult_baggage.get('checkedBaggage', {})
                        free_baggage = checked.get('hasFreeBaggage', False)
            except (KeyError, IndexError, TypeError):
                pass

        # Filter by free baggage
        if free_baggage_only and not free_baggage:
            continue

        # Calculate total price: adultPrice + fuel surcharge + airport fee
        fuel = _get_fuel_surcharge(dep_code, arr_code)
        total_price = adult_price + fuel + AIRPORT_FEE

        # Map cabin code to Chinese name
        price_class = _cabin_name(price_list[0].get('cabin', ''))

        flights.append({
            'flight_no': flight_no,
            'airline': airline,
            'dep_time': dep_time,
            'arr_time': arr_time,
            'stops': 0,
            'price': int(total_price),
            'adult_price': int(adult_price),
            'fuel_surcharge': fuel,
            'price_key': price_key,
            'price_channel_cn': price_channel_cn,
            'price_class': price_class,
            'direction': direction,
            'departure_airport': dep_code,
            'arrival_airport': arr_code,
            'date': date,
            'aircraft_code': aircraft_code,
            'aircraft_name': aircraft_name,
            'dep_airport_name': dep_airport_name,
            'arr_airport_name': arr_airport_name,
            'dep_terminal': dep_terminal,
            'arr_terminal': arr_terminal,
            'duration_minutes': duration_minutes if isinstance(duration_minutes, int) else 0,
            'baggage_tag': baggage_tag,
            'free_baggage': free_baggage,
            'operate_airline': operate_airline,
            'operate_flight_no': operate_flight_no,
        })

    return flights


def _cabin_name(cabin_code: str) -> str:
    """Map cabin code to Chinese name."""
    mapping = {
        'Y': '经济舱',
        'C': '公务舱',
        'F': '头等舱',
        'W': '超级经济舱',
    }
    if isinstance(cabin_code, dict):
        return cabin_code.get('cabinName', '经济舱')
    return mapping.get(cabin_code, f'{cabin_code}舱' if cabin_code else '经济舱')


def search_flights(
    departure_code: str,
    arrival_code: str,
    date: str,
    headless: bool = True,
    proxy: str | None = None,
    free_baggage_only: bool = True,
) -> list[dict]:
    """Search Ctrip for direct flights on a specific route and date.

    Opens a Playwright browser, navigates to the Ctrip search results page,
    intercepts the batchSearch API response, and parses direct flights.
    """
    from playwright.sync_api import sync_playwright

    ua = get_random_ua()
    search_url = CTRIP_SEARCH_URL.format(dep=departure_code, arr=arrival_code, date=date)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            proxy={'server': proxy} if proxy else None,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ],
        )
        context = browser.new_context(
            user_agent=ua,
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        page = context.new_page()

        try:
            # Set cookies via homepage
            page.goto(CTRIP_COOKIE_URL, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(3000)

            flights = _navigate_and_intercept(
                page, search_url, 'single', departure_code, arrival_code, date,
                free_baggage_only=free_baggage_only,
            )
        except Exception as e:
            _save_debug_info(page)
            raise RuntimeError(
                f"Failed to search flights for {departure_code}->{arrival_code} {date}: {e}"
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
    free_baggage_only: bool = True,
) -> list[dict]:
    """Search all routes using a single browser session.

    Opens one Playwright browser, sets cookies, then navigates to the
    Ctrip search results page for each route, intercepting the batchSearch
    API response.
    """
    from playwright.sync_api import sync_playwright

    all_flights = []
    total = len(search_params)
    ua = get_random_ua()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            proxy={'server': proxy} if proxy else None,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ],
        )
        context = browser.new_context(
            user_agent=ua,
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN',
        )
        page = context.new_page()

        try:
            page.goto(CTRIP_COOKIE_URL, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(3000)
        except Exception:
            pass

        for i, params in enumerate(search_params):
            label = (
                f"{params['departure_city']}({params['departure_code']}) -> "
                f"{params['arrival_city']}({params['arrival_code']})"
            )
            print(f"[{i+1}/{total}] Searching: {label} {params['date']}")

            search_url = CTRIP_SEARCH_URL.format(
                dep=params['departure_code'],
                arr=params['arrival_code'],
                date=params['date'],
            )

            try:
                flights = _navigate_and_intercept(
                    page, search_url,
                    params['direction'],
                    params['departure_code'],
                    params['arrival_code'],
                    params['date'],
                    free_baggage_only=free_baggage_only,
                )
                all_flights.extend(flights)

                if flights:
                    cheapest = min(f['price'] for f in flights)
                    print(f"  -> Found {len(flights)} direct flights, cheapest=¥{cheapest}")
                else:
                    print(f"  -> No direct flights found for this route")
            except RuntimeError as e:
                print(f"  -> Error: {e}")
            except Exception as e:
                print(f"  -> Fatal error: {e}. Stopping all searches.")
                break

            if i < total - 1:
                delay = random_delay(min_delay, max_delay)
                time.sleep(delay)

        context.close()
        browser.close()

    return all_flights


def _navigate_and_intercept(
    page,
    search_url: str,
    direction: str,
    dep_code: str,
    arr_code: str,
    date: str,
    free_baggage_only: bool = True,
) -> list[dict]:
    """Navigate to search page and intercept batchSearch API response."""
    captured = []

    def on_response(response):
        if 'batchSearch' in response.url and response.status == 200:
            try:
                data = response.json()
                captured.append(data)
            except Exception:
                pass

    page.on('response', on_response)
    try:
        page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(15000)
    finally:
        # Remove the listener to avoid capturing stale responses for next route
        page.remove_listener('response', on_response)

    if not captured:
        _save_debug_info(page)
        raise RuntimeError(
            f"batchSearch response not captured for {dep_code}->{arr_code} {date}"
        )

    return _parse_batch_search_response(captured[0], direction, dep_code, arr_code, date,
                                          free_baggage_only=free_baggage_only)


def _save_debug_info(page) -> None:
    """Save screenshot and HTML for debugging."""
    try:
        os.makedirs('data', exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        page.screenshot(path=f'data/captcha_{timestamp}.png')
        try:
            debug_html = page.content()
        except Exception:
            debug_html = '<failed to get page content>'
        html_path = f'data/debug_{timestamp}.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(debug_html)
    except Exception:
        pass
