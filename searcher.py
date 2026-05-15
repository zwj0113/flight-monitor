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
