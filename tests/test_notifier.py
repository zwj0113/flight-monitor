# tests/test_notifier.py
import pytest
from notifier import format_report, send_feishu_notification


class TestFormatReport:
    def test_formats_top_combinations(self):
        combinations = [
            {
                'total_price': 2430,
                'outbound': {
                    'flight_no': 'CA1234', 'airline': '中国国航',
                    'departure_airport': 'HGH', 'arrival_airport': 'URC',
                    'dep_time': '08:00', 'arr_time': '14:00', 'stops': 0, 'price': 1280,
                },
                'return': {
                    'flight_no': 'CA5678', 'airline': '中国国航',
                    'departure_airport': 'URC', 'arrival_airport': 'PVG',
                    'dep_time': '16:00', 'arr_time': '22:00', 'stops': 0, 'price': 1150,
                },
            }
        ]
        changes = []
        report = format_report(combinations, changes, {'direction': 'down', 'percent': -3.5})

        assert '2,430' in report
        assert 'CA1234' in report
        assert 'HGH' in report
        assert 'URC' in report
        assert '直飞' in report
        assert '1,280' in report
        assert '降3.5%' in report

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

        assert '降200' in report or '-200' in report

    def test_reports_no_history_on_first_run(self):
        combinations = [
            {
                'total_price': 2500,
                'outbound': {
                    'flight_no': 'XX1111', 'airline': '测试航空',
                    'departure_airport': 'PVG', 'arrival_airport': 'URC',
                    'dep_time': '08:00', 'arr_time': '14:00', 'stops': 1, 'price': 1300,
                },
                'return': {
                    'flight_no': 'XX2222', 'airline': '测试航空',
                    'departure_airport': 'URC', 'arrival_airport': 'PVG',
                    'dep_time': '16:00', 'arr_time': '22:00', 'stops': 0, 'price': 1200,
                },
            }
        ]
        report = format_report(combinations, [], {'direction': 'unchanged', 'percent': 0.0})

        assert "首次查询" in report
        assert "2,500" in report


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
