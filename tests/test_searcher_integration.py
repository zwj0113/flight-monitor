import pytest

from searcher import search_all_routes, build_all_search_params


@pytest.fixture
def sample_search_params():
    departure_airports = [
        {"code": "PVG", "city": "上海"},
    ]
    arrival = {"code": "URC", "city": "乌鲁木齐"}
    return_airports = [
        {"code": "PVG", "city": "上海"},
    ]
    return build_all_search_params(
        departure_airports, arrival, return_airports,
        "2026-09-25", "2026-10-07",
    )


class TestSearchAllRoutesStructure:
    """Tests that don't require Playwright browser — verify input/output shapes."""

    def test_accepts_empty_params(self):
        result = search_all_routes([])
        assert result == []
        assert isinstance(result, list)

    def test_missing_optional_keys_default(self, sample_search_params):
        """search_all_routes should handle params gracefully even
        when the search itself fails (no browser available)."""
        # With headless=False and no real browser, this will error quickly
        # but the function should not crash — it catches errors in the loop.
        result = search_all_routes(
            sample_search_params,
            headless=True,
            min_delay=0,
            max_delay=0,
        )
        # No real browser in CI — returns empty list, no crash
        assert isinstance(result, list)

    def test_search_params_structure(self, sample_search_params):
        for p in sample_search_params:
            assert 'direction' in p
            assert p['direction'] in ('outbound', 'return')
            assert 'departure_city' in p
            assert 'arrival_city' in p
            assert 'date' in p
            assert 'departure_code' in p
            assert 'arrival_code' in p


class TestSearchFlightsImport:
    """Verify the function is properly importable."""

    def test_search_flights_is_callable(self):
        from searcher import search_flights
        assert callable(search_flights)

    def test_search_all_routes_is_callable(self):
        from searcher import search_all_routes
        assert callable(search_all_routes)
