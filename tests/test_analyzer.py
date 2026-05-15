# tests/test_analyzer.py
from analyzer import compute_combinations, detect_price_changes, compute_trend


OUTBOUND_FLIGHTS = [
    {'direction': 'outbound', 'departure_airport': 'PVG', 'arrival_airport': 'URC',
     'date': '2026-09-25', 'flight_no': 'MU1234', 'airline': '东方航空',
     'dep_time': '08:00', 'arr_time': '14:30', 'stops': 0, 'price': 1280},
    {'direction': 'outbound', 'departure_airport': 'PVG', 'arrival_airport': 'URC',
     'date': '2026-09-25', 'flight_no': 'CA5678', 'airline': '中国国航',
     'dep_time': '11:00', 'arr_time': '22:00', 'stops': 1, 'price': 980},
    {'direction': 'outbound', 'departure_airport': 'HGH', 'arrival_airport': 'URC',
     'date': '2026-09-25', 'flight_no': 'MF9999', 'airline': '厦门航空',
     'dep_time': '07:00', 'arr_time': '13:00', 'stops': 0, 'price': 1500},
]

RETURN_FLIGHTS = [
    {'direction': 'return', 'departure_airport': 'URC', 'arrival_airport': 'PVG',
     'date': '2026-10-07', 'flight_no': 'MU4321', 'airline': '东方航空',
     'dep_time': '16:00', 'arr_time': '22:00', 'stops': 0, 'price': 1150},
    {'direction': 'return', 'departure_airport': 'URC', 'arrival_airport': 'SHA',
     'date': '2026-10-07', 'flight_no': 'CZ8888', 'airline': '南方航空',
     'dep_time': '10:00', 'arr_time': '19:00', 'stops': 1, 'price': 880},
]


class TestComputeCombinations:
    def test_returns_sorted_by_total_price(self):
        results = compute_combinations(OUTBOUND_FLIGHTS, RETURN_FLIGHTS)
        assert len(results) > 0
        for i in range(len(results) - 1):
            assert results[i]['total_price'] <= results[i+1]['total_price']

    def test_top_n_limits_results(self):
        results = compute_combinations(OUTBOUND_FLIGHTS, RETURN_FLIGHTS, top_n=3)
        assert len(results) <= 3

    def test_each_combination_has_required_fields(self):
        results = compute_combinations(OUTBOUND_FLIGHTS, RETURN_FLIGHTS)
        for r in results:
            assert 'total_price' in r
            assert 'outbound' in r
            assert 'return' in r
            assert r['outbound']['direction'] == 'outbound'
            assert r['return']['direction'] == 'return'

    def test_handles_empty_input(self):
        results = compute_combinations([], RETURN_FLIGHTS)
        assert results == []


PREV_PRICES = [
    {'flight_no': 'MU1234', 'price': 1400, 'departure_airport': 'PVG', 'arrival_airport': 'URC'},
    {'flight_no': 'CA5678', 'price': 980, 'departure_airport': 'PVG', 'arrival_airport': 'URC'},
]

CURR_PRICES = [
    {'flight_no': 'MU1234', 'price': 1280, 'departure_airport': 'PVG', 'arrival_airport': 'URC'},
    {'flight_no': 'CA5678', 'price': 1050, 'departure_airport': 'PVG', 'arrival_airport': 'URC'},
]


class TestDetectPriceChanges:
    def test_detects_price_drop(self):
        changes = detect_price_changes(CURR_PRICES, PREV_PRICES)
        mu = [c for c in changes if c['flight_no'] == 'MU1234'][0]
        assert mu['change'] < 0
        assert mu['prev_price'] == 1400
        assert mu['curr_price'] == 1280

    def test_detects_price_increase(self):
        changes = detect_price_changes(CURR_PRICES, PREV_PRICES)
        ca = [c for c in changes if c['flight_no'] == 'CA5678'][0]
        assert ca['change'] > 0
        assert ca['prev_price'] == 980
        assert ca['curr_price'] == 1050

    def test_handles_new_flight(self):
        no_prev = [{'flight_no': 'NEW001', 'price': 888}]
        changes = detect_price_changes(no_prev, PREV_PRICES)
        assert len(changes) == 0

    def test_skips_unchanged_price(self):
        curr = [{'flight_no': 'MU1234', 'price': 1400}]
        prev = [{'flight_no': 'MU1234', 'price': 1400}]
        changes = detect_price_changes(curr, prev)
        assert len(changes) == 0

    def test_sorted_by_change_ascending(self):
        curr = [
            {'flight_no': 'A', 'price': 1000},
            {'flight_no': 'B', 'price': 500},
        ]
        prev = [
            {'flight_no': 'A', 'price': 800},
            {'flight_no': 'B', 'price': 1000},
        ]
        changes = detect_price_changes(curr, prev)
        assert len(changes) == 2
        assert changes[0]['change'] < changes[1]['change']

    def test_handles_empty_previous_prices(self):
        changes = detect_price_changes(CURR_PRICES, [])
        assert changes == []


class TestComputeTrend:
    def test_detects_downward_trend(self):
        curr = [{'total_price': 2000}]
        prev = [{'total_price': 2500}]
        trend = compute_trend(curr, prev)
        assert trend['direction'] == 'down'
        assert trend['percent'] == -20.0

    def test_detects_upward_trend(self):
        curr = [{'total_price': 3000}]
        prev = [{'total_price': 2500}]
        trend = compute_trend(curr, prev)
        assert trend['direction'] == 'up'
        assert trend['percent'] == 20.0

    def test_unchanged_when_no_history(self):
        trend = compute_trend([], [])
        assert trend['direction'] == 'unchanged'
        assert trend['percent'] == 0.0

    def test_unchanged_when_prev_best_zero(self):
        curr = [{'total_price': 1000}]
        prev = [{'total_price': 0}]
        trend = compute_trend(curr, prev)
        assert trend['direction'] == 'unchanged'
        assert trend['percent'] == 0.0

    def test_unchanged_when_no_current_data(self):
        trend = compute_trend([], [{'total_price': 1000}])
        assert trend['direction'] == 'unchanged'
        assert trend['percent'] == 0.0
