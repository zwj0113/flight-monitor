from anti_detect import get_random_ua, random_delay, round_robin_ua


class TestRandomUA:
    def test_returns_non_empty_string(self):
        ua = get_random_ua()
        assert isinstance(ua, str)
        assert len(ua) > 20

    def test_returns_different_uas(self):
        uas = {get_random_ua() for _ in range(20)}
        assert len(uas) > 1


class TestRoundRobinUA:
    def test_cycles_through_pool(self):
        gen = round_robin_ua()
        first = next(gen)
        second = next(gen)
        third = next(gen)
        assert first != second
        assert second != third
        assert first != third  # 10-entry pool: first three are all distinct

        # After consuming 10 total, the 11th wraps back to first
        for _ in range(7):
            next(gen)
        eleventh = next(gen)
        assert first == eleventh

    def test_wraps_around(self):
        gen = round_robin_ua()
        pool_size = 10
        seen = [next(gen) for _ in range(pool_size * 2)]
        for i in range(pool_size):
            assert seen[i] == seen[i + pool_size]


class TestRandomDelay:
    def test_returns_number_in_range(self):
        for _ in range(100):
            delay = random_delay(2, 5)
            assert 2 <= delay <= 5

    def test_uses_default_range(self):
        delay = random_delay()
        assert 15 <= delay <= 30
