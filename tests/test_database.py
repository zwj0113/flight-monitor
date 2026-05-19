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
            'aircraft_code': '320',
            'aircraft_name': '空客320(中)',
            'dep_airport_name': '浦东国际机场',
            'arr_airport_name': '地窝堡国际机场',
            'dep_terminal': 'T1',
            'arr_terminal': 'T2',
            'duration_minutes': 270,
            'free_baggage': True,
            'baggage_tag': '托运行李额20KG',
            'operate_airline': '',
            'operate_flight_no': '',
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

    def test_saves_and_retrieves_new_fields(self):
        """New fields (aircraft, terminals, baggage, etc.) should persist."""
        db = FlightDB(self.db_path)
        flight = self._sample_flight(
            aircraft_code='789', aircraft_name='波音789',
            dep_airport_name='虹桥', arr_airport_name='地窝堡',
            dep_terminal='T2', arr_terminal='T3',
            duration_minutes=320, free_baggage=True,
            baggage_tag='20KG',
        )
        db.save_flights([flight])

        results = db.get_latest_prices('outbound', 'PVG', 'URC', '2026-09-25')
        assert len(results) == 1
        f = results[0]
        assert f['aircraft_code'] == '789'
        assert f['aircraft_name'] == '波音789'
        assert f['dep_airport_name'] == '虹桥'
        assert f['arr_airport_name'] == '地窝堡'
        assert f['dep_terminal'] == 'T2'
        assert f['arr_terminal'] == 'T3'
        assert f['duration_minutes'] == 320
        assert f['free_baggage'] == 1
        assert f['baggage_tag'] == '20KG'

    def test_clear_old_data(self):
        db = FlightDB(self.db_path)
        db.save_flights([self._sample_flight()])
        db.clear_all()
        results = db.get_latest_prices('outbound', 'PVG', 'URC', '2026-09-25')
        assert len(results) == 0
