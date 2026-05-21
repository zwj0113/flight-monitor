# tests/test_notifier.py
import subprocess
from unittest import mock

import pytest
from notifier import format_report, send_feishu_notification, send_lark_notification, send_price_drop_alert


class TestFormatReport:
    def test_formats_top_combinations(self):
        combinations = [
            {
                'total_price': 2430,
                'outbound': {
                    'flight_no': 'CA1234', 'airline': '中国国航',
                    'departure_airport': 'HGH', 'arrival_airport': 'URC',
                    'dep_time': '2026-09-25 08:00:00', 'arr_time': '2026-09-25 14:00:00',
                    'stops': 0, 'price': 1280,
                    'aircraft_code': '', 'aircraft_name': '',
                    'dep_terminal': '', 'arr_terminal': '',
                    'duration_minutes': 0, 'baggage_tag': '',
                    'operate_airline': '',
                },
                'return': {
                    'flight_no': 'CA5678', 'airline': '中国国航',
                    'departure_airport': 'URC', 'arrival_airport': 'PVG',
                    'dep_time': '2026-09-25 16:00:00', 'arr_time': '2026-09-25 22:00:00',
                    'stops': 0, 'price': 1150,
                    'aircraft_code': '', 'aircraft_name': '',
                    'dep_terminal': '', 'arr_terminal': '',
                    'duration_minutes': 0, 'baggage_tag': '',
                    'operate_airline': '',
                },
            }
        ]
        changes = []
        report = format_report(combinations, changes, {'direction': 'down', 'percent': -3.5})

        assert '2,430' in report
        assert 'CA1234' in report
        assert 'HGH' in report
        assert 'URC' in report
        assert '1,280' in report
        assert '降3.5%' in report

    def test_shows_baseline_when_provided(self):
        combinations = [
            {
                'total_price': 4710,
                'outbound': {
                    'flight_no': 'CA3272', 'airline': '中国国航',
                    'departure_airport': 'SHA', 'arrival_airport': 'URC',
                    'dep_time': '2026-09-25 10:05:00', 'arr_time': '2026-09-25 15:25:00',
                    'stops': 0, 'price': 2630,
                    'aircraft_code': '320', 'aircraft_name': '空客320(中)',
                    'dep_terminal': 'T2', 'arr_terminal': 'T1',
                    'duration_minutes': 320, 'baggage_tag': '托运行李额20KG',
                    'operate_airline': '',
                },
                'return': {
                    'flight_no': 'SC2185', 'airline': '山东航空',
                    'departure_airport': 'URC', 'arrival_airport': 'NKG',
                    'dep_time': '2026-09-25 19:00:00', 'arr_time': '2026-09-25 23:50:00',
                    'stops': 0, 'price': 2080,
                    'aircraft_code': '737', 'aircraft_name': '波音737(中)',
                    'dep_terminal': 'T1', 'arr_terminal': 'T2',
                    'duration_minutes': 290, 'baggage_tag': '托运行李额20KG',
                    'operate_airline': '',
                },
            }
        ]
        baseline = {'outbound_min': 2630, 'return_min': 2080, 'airport': 'SHA'}
        report = format_report(combinations, [], {'direction': 'unchanged', 'percent': 0.0},
                               baseline=baseline)

        assert '上海基准' in report
        assert '2,630' in report
        assert 'SHA' in report
        assert '2,080' in report
        assert '空客320' in report
        assert '波音737' in report
        assert 'T2' in report
        assert '5h20m' in report
        assert '托运行李额20KG' in report
        assert '较上海基准 +¥0' in report

    def test_shows_price_change_when_present(self):
        combinations = [
            {
                'total_price': 2500,
                'outbound': {
                    'flight_no': 'MU1111', 'airline': '东方航空',
                    'departure_airport': 'PVG', 'arrival_airport': 'URC',
                    'dep_time': '08:00', 'arr_time': '14:00', 'stops': 0, 'price': 1300,
                },
                'return': {
                    'flight_no': 'MU2222', 'airline': '东方航空',
                    'departure_airport': 'URC', 'arrival_airport': 'PVG',
                    'dep_time': '16:00', 'arr_time': '22:00', 'stops': 0, 'price': 1200,
                },
            }
        ]
        changes = [
            {'flight_no': 'MU1111', 'curr_price': 1300, 'prev_price': 1500, 'change': -200}
        ]
        report = format_report(combinations, changes, {'direction': 'down', 'percent': -10.0})

        assert '↓' in report
        assert '-200' in report

    def test_reports_no_history_on_first_run(self):
        combinations = [
            {
                'total_price': 2500,
                'outbound': {
                    'flight_no': 'XX1111', 'airline': '测试航空',
                    'departure_airport': 'PVG', 'arrival_airport': 'URC',
                    'dep_time': '08:00', 'arr_time': '14:00', 'stops': 1, 'price': 1300,
                    'aircraft_code': '', 'aircraft_name': '',
                    'dep_terminal': '', 'arr_terminal': '',
                    'duration_minutes': 0, 'baggage_tag': '',
                    'operate_airline': '',
                },
                'return': {
                    'flight_no': 'XX2222', 'airline': '测试航空',
                    'departure_airport': 'URC', 'arrival_airport': 'PVG',
                    'dep_time': '16:00', 'arr_time': '22:00', 'stops': 0, 'price': 1200,
                    'aircraft_code': '', 'aircraft_name': '',
                    'dep_terminal': '', 'arr_terminal': '',
                    'duration_minutes': 0, 'baggage_tag': '',
                    'operate_airline': '',
                },
            }
        ]
        report = format_report(combinations, [], {'direction': 'unchanged', 'percent': 0.0})

        assert "首次查询" in report
        assert "2,500" in report

    def test_shows_upward_trend(self):
        combinations = [
            {
                'total_price': 3000,
                'outbound': {
                    'flight_no': 'AA1111', 'airline': '测试航空',
                    'departure_airport': 'PVG', 'arrival_airport': 'URC',
                    'dep_time': '08:00', 'arr_time': '14:00', 'stops': 0, 'price': 1500,
                },
                'return': {
                    'flight_no': 'AA2222', 'airline': '测试航空',
                    'departure_airport': 'URC', 'arrival_airport': 'PVG',
                    'dep_time': '16:00', 'arr_time': '22:00', 'stops': 0, 'price': 1500,
                },
            }
        ]
        report = format_report(combinations, [], {'direction': 'up', 'percent': 10.0})
        assert '涨10.0%' in report

    def test_empty_combinations_shows_warning(self):
        report = format_report([], [], {'direction': 'unchanged', 'percent': 0.0})
        assert '未获取到航班数据' in report

    def test_shows_price_breakdown_and_channel(self):
        """Should show price breakdown and channel info."""
        combinations = [
            {
                'total_price': 3410,
                'outbound': {
                    'flight_no': 'HO1255', 'airline': '吉祥航空',
                    'departure_airport': 'SHA', 'arrival_airport': 'URC',
                    'dep_airport_name': '虹桥国际机场', 'arr_airport_name': '地窝堡国际机场',
                    'dep_time': '2026-09-25 10:05:00', 'arr_time': '2026-09-25 15:25:00',
                    'stops': 0, 'price': 3410,
                    'adult_price': 3190, 'fuel_surcharge': 170,
                    'price_key': 'JPFWB', 'price_channel_cn': '机票服务包',
                    'aircraft_code': '321', 'aircraft_name': '空客321(中)',
                    'dep_terminal': 'T2', 'arr_terminal': 'T1',
                    'duration_minutes': 320, 'baggage_tag': '托运行李额20KG',
                    'operate_airline': '',
                },
                'return': {
                    'flight_no': 'HO1256', 'airline': '吉祥航空',
                    'departure_airport': 'URC', 'arrival_airport': 'SHA',
                    'dep_airport_name': '地窝堡国际机场', 'arr_airport_name': '虹桥国际机场',
                    'dep_time': '2026-09-25 17:00:00', 'arr_time': '2026-09-25 22:00:00',
                    'stops': 0, 'price': 3200,
                    'adult_price': 2980, 'fuel_surcharge': 170,
                    'price_key': 'JPFWB', 'price_channel_cn': '机票服务包',
                    'aircraft_code': '321', 'aircraft_name': '空客321(中)',
                    'dep_terminal': 'T2', 'arr_terminal': 'T1',
                    'duration_minutes': 300, 'baggage_tag': '托运行李额20KG',
                    'operate_airline': '',
                },
            }
        ]
        report = format_report(combinations, [], {'direction': 'unchanged', 'percent': 0.0})

        # Airport display format
        assert 'SHA(上海虹桥)' in report
        assert 'URC(乌鲁木齐天山)' in report
        # Price breakdown
        assert '裸票¥3,190' in report
        assert '燃油¥170' in report
        assert '机建¥50' in report
        # Channel info
        assert 'JPFWB' in report
        assert '机票服务包' in report
        # Total price still shows
        assert '¥3,410' in report

    def test_limits_to_top_5(self):
        combo = {
            'total_price': 1000,
            'outbound': {
                'flight_no': 'XX0001', 'airline': '测试航空',
                'departure_airport': 'AAA', 'arrival_airport': 'BBB',
                'dep_time': '08:00', 'arr_time': '14:00', 'stops': 0, 'price': 500,
            },
            'return': {
                'flight_no': 'XX0002', 'airline': '测试航空',
                'departure_airport': 'BBB', 'arrival_airport': 'AAA',
                'dep_time': '16:00', 'arr_time': '22:00', 'stops': 0, 'price': 500,
            },
        }
        combinations = [combo] * 10
        report = format_report(combinations, [], {'direction': 'unchanged', 'percent': 0.0})
        assert report.count('总价:') == 5


class TestSendFeishuNotification:
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_sends_post_to_webhook(self, httpx_mock):
        httpx_mock.add_response(url="https://hook.example.com/test", method="POST", status_code=200)

        result = send_feishu_notification(
            webhook_url="https://hook.example.com/test",
            title="机票监控报告",
            content="测试内容",
        )

        assert result is True

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_returns_false_on_error(self, httpx_mock):
        httpx_mock.add_response(url="https://hook.example.com/fail", method="POST", status_code=500)

        result = send_feishu_notification(
            webhook_url="https://hook.example.com/fail",
            title="机票监控报告",
            content="测试内容",
        )

        assert result is False


class TestSendPriceDropAlert:
    def test_returns_false_for_empty_combinations(self):
        result = send_price_drop_alert("https://hook.example.com/test", [], 500)
        assert result is False

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_sends_alert_when_called(self, httpx_mock):
        httpx_mock.add_response(url="https://hook.example.com/test", method="POST", status_code=200)
        combinations = [
            {
                'total_price': 3000,
                'outbound': {
                    'flight_no': 'XX0001', 'airline': '测试航空',
                    'departure_airport': 'AAA', 'arrival_airport': 'BBB',
                    'dep_time': '08:00', 'arr_time': '14:00', 'stops': 0, 'price': 1500,
                },
                'return': {
                    'flight_no': 'XX0002', 'airline': '测试航空',
                    'departure_airport': 'BBB', 'arrival_airport': 'AAA',
                    'dep_time': '16:00', 'arr_time': '22:00', 'stops': 0, 'price': 1500,
                },
            }
        ]
        result = send_price_drop_alert("https://hook.example.com/test", combinations, 2000)
        assert result is True


class TestSendLarkNotification:
    def test_sends_markdown_via_lark_cli(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            result = send_lark_notification(
                "oc_test123", "机票监控报告", "测试内容"
            )
            assert result is True
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "--markdown" in args
            assert "oc_test123" in args
            assert "**机票监控报告**" in args[args.index("--markdown") + 1]

    def test_returns_false_on_subprocess_error(self):
        with mock.patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(["lark-cli"], 15)
            result = send_lark_notification(
                "oc_test123", "机票监控报告", "测试内容"
            )
            assert result is False
