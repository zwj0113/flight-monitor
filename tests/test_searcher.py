from searcher import build_search_url, build_all_search_params


class TestBuildSearchURL:
    def test_oneway_url_format(self):
        url = build_search_url("上海", "乌鲁木齐", "2026-09-25")
        assert "flight.qunar.com" in url
        assert "searchDepartureAirport" in url
        assert "searchArrivalAirport" in url
        assert "searchDepartureTime" in url
        assert "2026-09-25" in url

    def test_url_encoding_preserves_chinese(self):
        url = build_search_url("上海", "乌鲁木齐", "2026-09-25")
        assert "%E4%B8%8A%E6%B5%B7" in url or "上海" in url
        assert "%E4%B9%8C%E9%B2%81%E6%9C%A8%E9%BD%90" in url or "乌鲁木齐" in url


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
