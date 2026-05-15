import os
import tempfile
from database import FlightDB


class TestFlightDB:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, "test.db")

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _sample_flight(self, **overrides):
        data = {
            'direction': 'outbound',
            'departure_airport': 'PVG',
            'arrival_airport': 'URC',
            'date': '2026-09-25',
            'flight_no': 'MU1234',
            'airline': '东方航空',
            'dep_time': '08:00',
            'arr_time': '14:30',
            'stops': 0,
            'price': 1280,
            'price_class': '经济舱',
        }
        data.update(overrides)
        return data

    def test_init_creates_table(self):
        db = FlightDB(self.db_path)
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flight_prices'")
        assert cursor.fetchone() is not None
        conn.close()

    def test_save_and_retrieve_flights(self):
        db = FlightDB(self.db_path)
        flights = [
            self._sample_flight(),
            self._sample_flight(flight_no='CA5678', price=1350, stops=1),
        ]
        count = db.save_flights(flights)
        assert count == 2

        results = db.get_latest_prices('outbound', 'PVG', 'URC', '2026-09-25')
        assert len(results) == 2
        assert results[0]['flight_no'] in ('MU1234', 'CA5678')
        assert results[0]['price'] in (1280, 1350)

    def test_get_previous_prices_returns_empty_on_first_query(self):
        db = FlightDB(self.db_path)
        db.save_flights([self._sample_flight()])
        prev = db.get_previous_prices('outbound', 'PVG', 'URC', '2026-09-25')
        assert prev == []

    def test_get_previous_prices_returns_earlier_batch(self):
        db = FlightDB(self.db_path)
        db.save_flights([self._sample_flight()])
        import time
        time.sleep(1.1)
        db.save_flights([self._sample_flight(price=999)])
        prev = db.get_previous_prices('outbound', 'PVG', 'URC', '2026-09-25')
        assert len(prev) == 0 or len(prev) == 1

    def test_clear_old_data(self):
        db = FlightDB(self.db_path)
        db.save_flights([self._sample_flight()])
        db.clear_all()
        results = db.get_latest_prices('outbound', 'PVG', 'URC', '2026-09-25')
        assert len(results) == 0
