import os
import tempfile
from config_loader import load_config


class TestLoadConfig:
    def test_loads_all_sections(self):
        yaml_content = """
flight:
  outbound_date: "2026-09-25"
  return_date: "2026-10-07"
  departure_airports:
    - code: PVG
      city: "上海"
  arrival_airport:
    code: URC
    city: "乌鲁木齐"
  return_airports:
    - code: PVG
      city: "上海"
schedule:
  interval_hours: 6
notification:
  feishu_webhook: "https://hook.example.com"
  price_drop_threshold: 200
anti_detect:
  min_delay: 15
  max_delay: 30
  proxy: null
database:
  path: "data/test.db"
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(yaml_content)
            path = f.name

        try:
            config = load_config(path)
            assert config['flight']['outbound_date'] == "2026-09-25"
            assert config['flight']['return_date'] == "2026-10-07"
            assert len(config['flight']['departure_airports']) == 1
            assert config['flight']['departure_airports'][0]['code'] == 'PVG'
            assert config['flight']['arrival_airport']['code'] == 'URC'
            assert config['schedule']['interval_hours'] == 6
            assert config['notification']['feishu_webhook'] == "https://hook.example.com"
            assert config['notification']['price_drop_threshold'] == 200
            assert config['anti_detect']['min_delay'] == 15
            assert config['anti_detect']['max_delay'] == 30
            assert config['database']['path'] == "data/test.db"
        finally:
            os.unlink(path)

    def test_loads_multiple_departure_airports(self):
        yaml_content = """
flight:
  outbound_date: "2026-09-25"
  return_date: "2026-10-07"
  departure_airports:
    - code: PVG
      city: "上海"
    - code: HGH
      city: "杭州"
  arrival_airport:
    code: URC
    city: "乌鲁木齐"
  return_airports:
    - code: PVG
      city: "上海"
    - code: HGH
      city: "杭州"
schedule:
  interval_hours: 6
notification:
  feishu_webhook: ""
  price_drop_threshold: 0
anti_detect:
  min_delay: 0
  max_delay: 0
  proxy: null
database:
  path: ""
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(yaml_content)
            path = f.name

        try:
            config = load_config(path)
            assert len(config['flight']['departure_airports']) == 2
            assert len(config['flight']['return_airports']) == 2
        finally:
            os.unlink(path)
