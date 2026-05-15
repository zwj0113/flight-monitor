import yaml


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    _validate_config(config)
    return config


def _validate_config(config: dict) -> None:
    required_sections = ['flight', 'schedule', 'notification', 'anti_detect', 'database']
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required config section: {section}")

    flight = config['flight']
    required_flight = ['outbound_date', 'return_date', 'departure_airports', 'arrival_airport', 'return_airports']
    for key in required_flight:
        if key not in flight:
            raise ValueError(f"Missing required flight config key: {key}")
    if not isinstance(flight['departure_airports'], list) or len(flight['departure_airports']) == 0:
        raise ValueError("departure_airports must be a non-empty list")
    if not isinstance(flight['return_airports'], list) or len(flight['return_airports']) == 0:
        raise ValueError("return_airports must be a non-empty list")

    for airport in flight['departure_airports'] + flight['return_airports']:
        if 'code' not in airport or 'city' not in airport:
            raise ValueError(f"Each airport must have 'code' and 'city': {airport}")
    if 'code' not in flight['arrival_airport'] or 'city' not in flight['arrival_airport']:
        raise ValueError("arrival_airport must have 'code' and 'city'")
