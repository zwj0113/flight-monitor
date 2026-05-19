import pytest

from searcher import build_all_search_params, _parse_batch_search_response


class TestBuildAllSearchParams:
    def test_generates_all_combinations(self):
        departure_airports = [
            {"code": "PVG", "city": "上海"},
            {"code": "HGH", "city": "杭州"},
            {"code": "NKG", "city": "南京"},
            {"code": "WUX", "city": "无锡"},
            {"code": "CZX", "city": "常州"},
            {"code": "NTG", "city": "南通"},
            {"code": "SHA", "city": "上海"},
        ]
        arrival = {"code": "URC", "city": "乌鲁木齐"}
        return_airports = [
            {"code": "PVG", "city": "上海"},
            {"code": "HGH", "city": "杭州"},
            {"code": "NKG", "city": "南京"},
            {"code": "WUX", "city": "无锡"},
            {"code": "CZX", "city": "常州"},
            {"code": "NTG", "city": "南通"},
            {"code": "SHA", "city": "上海"},
        ]

        results = build_all_search_params(
            departure_airports, arrival, return_airports,
            "2026-09-25", "2026-10-07"
        )

        outbounds = [r for r in results if r['direction'] == 'outbound']
        returns = [r for r in results if r['direction'] == 'return']
        assert len(outbounds) == 7
        assert len(returns) == 7
        assert len(results) == 14

        for r in outbounds:
            assert r['date'] == "2026-09-25"
            assert r['arrival_city'] == "乌鲁木齐"

        for r in returns:
            assert r['date'] == "2026-10-07"
            assert r['departure_city'] == "乌鲁木齐"


def _make_itinerary(flight_no, airline, dep_time, arr_time, adult_price, transfer=0, stop=0,
                    aircraft_code='', aircraft_name='', dep_airport_name='', arr_airport_name='',
                    dep_terminal='', arr_terminal='', duration=0, operate_airline='',
                    operate_flight_no='',
                    baggage_tag='', free_baggage=True):
    """Helper to build a flight itinerary matching real batchSearch structure."""
    baggage = {}
    if baggage_tag or free_baggage:
        baggage = {
            "baggageTag": baggage_tag,
            "dataList": [{
                "adultBaggage": {
                    "checkedBaggage": {
                        "hasFreeBaggage": free_baggage,
                    }
                }
            }],
        }
    return {
        "itineraryId": f"iti_{flight_no}",
        "flightSegments": [{
            "segmentNo": 1,
            "airlineCode": flight_no[:2],
            "airlineName": airline,
            "transferCount": transfer,
            "stopCount": stop,
            "flightList": [{
                "flightNo": flight_no,
                "departureDateTime": dep_time,
                "arrivalDateTime": arr_time,
                "aircraftCode": aircraft_code,
                "aircraftName": aircraft_name,
                "departureAirportName": dep_airport_name,
                "arrivalAirportName": arr_airport_name,
                "departureTerminal": dep_terminal,
                "arrivalTerminal": arr_terminal,
                "duration": duration,
                "operateAirlineName": operate_airline,
                "operateFlightNo": operate_flight_no,
            }],
        }],
        "priceList": [{
            "adultPrice": adult_price,
            "cabin": "Y",
            "baggage": baggage,
        }],
    }


# Sample batchSearch API response for SHA->URC on 2026-09-25
SAMPLE_BATCH_SEARCH_RESPONSE = {
    "status": 0,
    "msg": "success",
    "data": {
        "flightItineraryList": [
            _make_itinerary("CA4671", "中国国航", "2026-09-25 08:00:00", "2026-09-25 12:30:00", 3330),
            _make_itinerary("MU5678", "东方航空", "2026-09-25 14:00:00", "2026-09-25 18:30:00", 2120, transfer=1),
            _make_itinerary("CZ9012", "南方航空", "2026-09-25 16:00:00", "2026-09-25 20:30:00", 2800, stop=1),
            _make_itinerary("HU3456", "海南航空", "2026-09-25 10:00:00", "2026-09-25 14:30:00", 3500),
            _make_itinerary("3U1234", "四川航空", "2026-09-25 07:00:00", "2026-09-25 11:30:00", 0),
        ],
    },
}


class TestParseBatchSearchResponse:
    def test_filters_direct_flights_only(self):
        """Should exclude flights with transferCount>0 or stopCount>0."""
        flights = _parse_batch_search_response(
            SAMPLE_BATCH_SEARCH_RESPONSE,
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        flight_nos = {f['flight_no'] for f in flights}
        assert 'CA4671' in flight_nos
        assert 'HU3456' in flight_nos
        assert 'MU5678' not in flight_nos  # has transferCount=1
        assert 'CZ9012' not in flight_nos  # has stopCount=1

    def test_price_includes_fuel_and_airport_fee(self):
        """Price = adultPrice + fuel surcharge + airport fee."""
        flights = _parse_batch_search_response(
            SAMPLE_BATCH_SEARCH_RESPONSE,
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        # SHA->URC >800km: fuel=170 + 50 = 220 extra
        ca_flight = [f for f in flights if f['flight_no'] == 'CA4671'][0]
        assert ca_flight['price'] == 3550  # 3330 + 170 + 50

        hu_flight = [f for f in flights if f['flight_no'] == 'HU3456'][0]
        assert hu_flight['price'] == 3720  # 3500 + 170 + 50

    def test_short_route_fuel_surcharge(self):
        """Short route (≤800km) should use ¥90 fuel surcharge."""
        response = {
            "data": {
                "flightItineraryList": [
                    _make_itinerary("MU1001", "东方航空",
                                    "2026-09-25 08:00:00", "2026-09-25 09:30:00", 500),
                ],
            },
        }
        flights = _parse_batch_search_response(
            response,
            'outbound', 'SHA', 'NKG', '2026-09-25',
        )
        assert len(flights) == 1
        # SHA->NKG ≈270km ≤800km: fuel=90 + 50 = 140 extra
        assert flights[0]['price'] == 640  # 500 + 90 + 50

    def test_filters_zero_price(self):
        """Should exclude flights with adultPrice=0."""
        flights = _parse_batch_search_response(
            SAMPLE_BATCH_SEARCH_RESPONSE,
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        flight_nos = {f['flight_no'] for f in flights}
        assert '3U1234' not in flight_nos  # adultPrice=0

    def test_extracted_fields_have_required_keys(self):
        flights = _parse_batch_search_response(
            SAMPLE_BATCH_SEARCH_RESPONSE,
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        assert len(flights) > 0
        f = flights[0]
        assert 'flight_no' in f
        assert 'airline' in f
        assert 'dep_time' in f
        assert 'arr_time' in f
        assert 'stops' in f
        assert 'price' in f
        assert 'price_class' in f
        assert 'direction' in f
        assert 'departure_airport' in f
        assert 'arrival_airport' in f
        assert 'date' in f

    def test_has_real_airline_and_flight_no(self):
        """batchSearch provides real airline names and flight numbers."""
        flights = _parse_batch_search_response(
            SAMPLE_BATCH_SEARCH_RESPONSE,
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        ca = [f for f in flights if f['flight_no'] == 'CA4671'][0]
        assert ca['airline'] == '中国国航'
        assert ca['flight_no'] == 'CA4671'
        assert ca['dep_time'] == '2026-09-25 08:00:00'
        assert ca['arr_time'] == '2026-09-25 12:30:00'

    def test_stops_is_zero_for_direct(self):
        flights = _parse_batch_search_response(
            SAMPLE_BATCH_SEARCH_RESPONSE,
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        for f in flights:
            assert f['stops'] == 0

    def test_price_is_int(self):
        flights = _parse_batch_search_response(
            SAMPLE_BATCH_SEARCH_RESPONSE,
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        for f in flights:
            assert isinstance(f['price'], int)

    def test_handles_empty_itinerary_list(self):
        flights = _parse_batch_search_response(
            {"flightItineraryList": []},
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        assert flights == []

    def test_handles_missing_itinerary_key(self):
        flights = _parse_batch_search_response(
            {},
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        assert flights == []

    def test_all_direct_transfer_both_zero_means_direct(self):
        """transferCount==0 and stopCount==0 means a direct flight."""
        flights = _parse_batch_search_response(
            {
                "data": {
                    "flightItineraryList": [
                        _make_itinerary("FM9221", "上海航空",
                                        "2026-09-25 09:00:00", "2026-09-25 13:30:00", 2790),
                    ],
                },
            },
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        assert len(flights) == 1
        assert flights[0]['flight_no'] == 'FM9221'

    def test_parses_new_flight_fields(self):
        """Should extract aircraft, airport names, terminals, duration."""
        flights = _parse_batch_search_response(
            {
                "data": {
                    "flightItineraryList": [
                        _make_itinerary(
                            "CA3272", "中国国航",
                            "2026-09-25 10:05:00", "2026-09-25 15:25:00", 2630,
                            aircraft_code='320', aircraft_name='空客320(中)',
                            dep_airport_name='虹桥国际机场', arr_airport_name='地窝堡国际机场',
                            dep_terminal='T2', arr_terminal='T1',
                            duration=320,
                            baggage_tag='托运行李额20KG',
                        ),
                    ],
                },
            },
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        assert len(flights) == 1
        f = flights[0]
        assert f['aircraft_code'] == '320'
        assert f['aircraft_name'] == '空客320(中)'
        assert f['dep_airport_name'] == '虹桥国际机场'
        assert f['arr_airport_name'] == '地窝堡国际机场'
        assert f['dep_terminal'] == 'T2'
        assert f['arr_terminal'] == 'T1'
        assert f['duration_minutes'] == 320
        assert f['baggage_tag'] == '托运行李额20KG'
        assert f['free_baggage'] is True

    def test_parses_operate_airline_for_code_share(self):
        """Should extract operate airline for code-share flights."""
        flights = _parse_batch_search_response(
            {
                "data": {
                    "flightItineraryList": [
                        _make_itinerary(
                            "SC2185", "山东航空",
                            "2026-09-25 19:00:00", "2026-09-25 23:50:00", 2080,
                            operate_airline='中国国航', operate_flight_no='CA3272',
                        ),
                    ],
                },
            },
            'outbound', 'SHA', 'URC', '2026-09-25',
        )
        assert len(flights) == 1
        f = flights[0]
        assert f['operate_airline'] == '中国国航'
        assert f['operate_flight_no'] == 'CA3272'

    def test_free_baggage_filter_excludes_no_baggage(self):
        """When free_baggage_only=True, flights without free baggage are excluded."""
        response = {
            "data": {
                "flightItineraryList": [
                    _make_itinerary("CA1111", "中国国航",
                                    "2026-09-25 08:00:00", "2026-09-25 12:00:00", 3000,
                                    free_baggage=True),
                    _make_itinerary("MU2222", "东方航空",
                                    "2026-09-25 09:00:00", "2026-09-25 13:00:00", 2800,
                                    free_baggage=False),
                    _make_itinerary("CZ3333", "南方航空",
                                    "2026-09-25 10:00:00", "2026-09-25 14:00:00", 2600,
                                    free_baggage=True),
                ],
            },
        }
        flights = _parse_batch_search_response(
            response, 'outbound', 'SHA', 'URC', '2026-09-25',
            free_baggage_only=True,
        )
        flight_nos = {f['flight_no'] for f in flights}
        assert 'CA1111' in flight_nos
        assert 'CZ3333' in flight_nos
        assert 'MU2222' not in flight_nos  # no free baggage

    def test_free_baggage_filter_disabled_includes_all(self):
        """When free_baggage_only=False, all flights are included."""
        response = {
            "data": {
                "flightItineraryList": [
                    _make_itinerary("CA1111", "中国国航",
                                    "2026-09-25 08:00:00", "2026-09-25 12:00:00", 3000,
                                    free_baggage=True),
                    _make_itinerary("MU2222", "东方航空",
                                    "2026-09-25 09:00:00", "2026-09-25 13:00:00", 2800,
                                    free_baggage=False),
                ],
            },
        }
        flights = _parse_batch_search_response(
            response, 'outbound', 'SHA', 'URC', '2026-09-25',
            free_baggage_only=False,
        )
        assert len(flights) == 2

    def test_missing_baggage_defaults_to_no_free_baggage(self):
        """Flights with missing baggage data default to free_baggage=False."""
        response = {
            "data": {
                "flightItineraryList": [
                    _make_itinerary("XX9999", "测试航空",
                                    "2026-09-25 08:00:00", "2026-09-25 12:00:00", 3000,
                                    baggage_tag='', free_baggage=False),
                ],
            },
        }
        flights = _parse_batch_search_response(
            response, 'outbound', 'SHA', 'URC', '2026-09-25',
            free_baggage_only=True,
        )
        assert len(flights) == 0  # filtered out, no free baggage


class TestSearchFlightsImport:
    """Verify functions are properly importable."""

    def test_search_flights_is_callable(self):
        from searcher import search_flights
        assert callable(search_flights)

    def test_search_all_routes_is_callable(self):
        from searcher import search_all_routes
        assert callable(search_all_routes)

    def test_build_all_search_params_is_callable(self):
        from searcher import build_all_search_params
        assert callable(build_all_search_params)

    def test_parse_batch_search_response_is_callable(self):
        from searcher import _parse_batch_search_response
        assert callable(_parse_batch_search_response)
