import sqlite3
from datetime import datetime
from pathlib import Path


class FlightDB:
    def __init__(self, db_path: str = "data/flights.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS flight_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_time DATETIME NOT NULL,
                    direction TEXT NOT NULL,
                    departure_airport TEXT NOT NULL,
                    arrival_airport TEXT NOT NULL,
                    date TEXT NOT NULL,
                    flight_no TEXT NOT NULL,
                    airline TEXT DEFAULT '',
                    dep_time TEXT DEFAULT '',
                    arr_time TEXT DEFAULT '',
                    stops INTEGER DEFAULT 0,
                    price INTEGER NOT NULL,
                    price_class TEXT DEFAULT '',
                    aircraft_code TEXT DEFAULT '',
                    aircraft_name TEXT DEFAULT '',
                    dep_airport_name TEXT DEFAULT '',
                    arr_airport_name TEXT DEFAULT '',
                    dep_terminal TEXT DEFAULT '',
                    arr_terminal TEXT DEFAULT '',
                    duration_minutes INTEGER DEFAULT 0,
                    free_baggage INTEGER DEFAULT 0,
                    baggage_tag TEXT DEFAULT '',
                    operate_airline TEXT DEFAULT '',
                    operate_flight_no TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_flight_query
                ON flight_prices(direction, departure_airport, arrival_airport, date, query_time)
            """)
            # Migrate existing databases: add columns if they don't exist
            new_columns = [
                ('aircraft_code', 'TEXT DEFAULT \'\''),
                ('aircraft_name', 'TEXT DEFAULT \'\''),
                ('dep_airport_name', 'TEXT DEFAULT \'\''),
                ('arr_airport_name', 'TEXT DEFAULT \'\''),
                ('dep_terminal', 'TEXT DEFAULT \'\''),
                ('arr_terminal', 'TEXT DEFAULT \'\''),
                ('duration_minutes', 'INTEGER DEFAULT 0'),
                ('free_baggage', 'INTEGER DEFAULT 0'),
                ('baggage_tag', 'TEXT DEFAULT \'\''),
                ('operate_airline', 'TEXT DEFAULT \'\''),
                ('operate_flight_no', 'TEXT DEFAULT \'\''),
            ]
            for col_name, col_type in new_columns:
                try:
                    conn.execute(f"ALTER TABLE flight_prices ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists

    def save_flights(self, flights: list[dict]) -> int:
        now = datetime.now().isoformat(timespec='seconds')
        with sqlite3.connect(str(self.db_path)) as conn:
            count = 0
            for f in flights:
                conn.execute("""
                    INSERT INTO flight_prices
                    (query_time, direction, departure_airport, arrival_airport,
                     date, flight_no, airline, dep_time, arr_time, stops, price, price_class,
                     aircraft_code, aircraft_name, dep_airport_name, arr_airport_name,
                     dep_terminal, arr_terminal, duration_minutes, free_baggage, baggage_tag,
                     operate_airline, operate_flight_no)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?)
                """, (
                    now, f['direction'], f['departure_airport'], f['arrival_airport'],
                    f['date'], f['flight_no'], f.get('airline', ''),
                    f.get('dep_time', ''), f.get('arr_time', ''),
                    f.get('stops', 0), f['price'], f.get('price_class', ''),
                    f.get('aircraft_code', ''), f.get('aircraft_name', ''),
                    f.get('dep_airport_name', ''), f.get('arr_airport_name', ''),
                    f.get('dep_terminal', ''), f.get('arr_terminal', ''),
                    f.get('duration_minutes', 0), 1 if f.get('free_baggage') else 0,
                    f.get('baggage_tag', ''),
                    f.get('operate_airline', ''), f.get('operate_flight_no', ''),
                ))
                count += 1
            return count

    def get_latest_prices(self, direction: str, departure: str, arrival: str, date: str) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            latest_time = conn.execute("""
                SELECT MAX(query_time) FROM flight_prices
                WHERE direction=? AND departure_airport=? AND arrival_airport=? AND date=?
            """, (direction, departure, arrival, date)).fetchone()[0]

            if not latest_time:
                return []

            cursor = conn.execute("""
                SELECT * FROM flight_prices
                WHERE direction=? AND departure_airport=? AND arrival_airport=?
                  AND date=? AND query_time=?
                ORDER BY price ASC
            """, (direction, departure, arrival, date, latest_time))
            return [dict(row) for row in cursor.fetchall()]

    def get_previous_prices(self, direction: str, departure: str, arrival: str, date: str) -> list[dict]:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            times = conn.execute("""
                SELECT DISTINCT query_time FROM flight_prices
                WHERE direction=? AND departure_airport=? AND arrival_airport=? AND date=?
                ORDER BY query_time DESC LIMIT 2
            """, (direction, departure, arrival, date)).fetchall()

            if len(times) < 2:
                return []

            prev_time = times[1][0]
            cursor = conn.execute("""
                SELECT * FROM flight_prices
                WHERE direction=? AND departure_airport=? AND arrival_airport=?
                  AND date=? AND query_time=?
                ORDER BY price ASC
            """, (direction, departure, arrival, date, prev_time))
            return [dict(row) for row in cursor.fetchall()]

    def clear_all(self):
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM flight_prices")
