def compute_combinations(
    outbound_flights: list[dict],
    return_flights: list[dict],
    top_n: int = 5,
) -> list[dict]:
    if not outbound_flights or not return_flights:
        return []

    combinations = []
    for ob in outbound_flights:
        for rt in return_flights:
            combinations.append({
                'total_price': ob['price'] + rt['price'],
                'outbound': ob,
                'return': rt,
            })

    combinations.sort(key=lambda x: x['total_price'])
    return combinations[:top_n]


def detect_price_changes(
    current_prices: list[dict],
    previous_prices: list[dict],
) -> list[dict]:
    prev_map = {f['flight_no']: f for f in previous_prices}
    changes = []

    for curr in current_prices:
        flight_no = curr['flight_no']
        if flight_no not in prev_map:
            continue
        prev = prev_map[flight_no]
        diff = curr['price'] - prev['price']
        if diff != 0:
            changes.append({
                'flight_no': flight_no,
                'airline': curr.get('airline', ''),
                'departure_airport': curr.get('departure_airport', ''),
                'arrival_airport': curr.get('arrival_airport', ''),
                'curr_price': curr['price'],
                'prev_price': prev['price'],
                'change': diff,
            })

    return sorted(changes, key=lambda x: x['change'])


def compute_trend(combinations: list[dict], prev_combinations: list[dict]) -> dict:
    if not prev_combinations or not combinations:
        return {'direction': 'unchanged', 'percent': 0.0}

    curr_best = combinations[0]['total_price']
    prev_best = prev_combinations[0]['total_price']

    if prev_best == 0:
        return {'direction': 'unchanged', 'percent': 0.0}

    percent = (curr_best - prev_best) / prev_best * 100
    direction = 'down' if percent < 0 else 'up' if percent > 0 else 'unchanged'
    return {'direction': direction, 'percent': round(percent, 1)}
