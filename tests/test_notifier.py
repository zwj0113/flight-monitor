# tests/test_notifier.py
import json
import time
from unittest import mock

import httpx
import pytest
from notifier import format_report, FeishuNotifier


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


class TestFeishuNotifierToken:
    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_fetches_token_on_first_call(self, httpx_mock):
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 0, "tenant_access_token": "t-test-token", "expire": 7200},
        )

        notifier = FeishuNotifier("test-app-id", "test-secret")
        token = notifier._get_token()

        assert token == "t-test-token"

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_caches_token_within_expiry(self, httpx_mock):
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 0, "tenant_access_token": "t-cached", "expire": 7200},
        )

        notifier = FeishuNotifier("test-app-id", "test-secret")

        mock_time = time.time()
        with mock.patch("time.time", return_value=mock_time):
            token1 = notifier._get_token()
        # Second call: within expiry, should return cached
        with mock.patch("time.time", return_value=mock_time + 100):
            token2 = notifier._get_token()

        assert token1 == "t-cached"
        assert token2 == "t-cached"
        assert len(httpx_mock.get_requests()) == 1  # Only one API call

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_refreshes_token_when_expired(self, httpx_mock):
        httpx_mock.add_response(
           url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 0, "tenant_access_token": "t-old", "expire": 7200},
        )
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 0, "tenant_access_token": "t-new", "expire": 7200},
        )

        notifier = FeishuNotifier("test-app-id", "test-secret")

        mock_time = time.time()
        with mock.patch("time.time", return_value=mock_time):
            token1 = notifier._get_token()
        # Advance past expiry (7200 seconds)
        with mock.patch("time.time", return_value=mock_time + 7200):
            token2 = notifier._get_token()

        assert token1 == "t-old"
        assert token2 == "t-new"
        assert len(httpx_mock.get_requests()) == 2

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_raises_on_token_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 999, "msg": "invalid app secret"},
        )

        notifier = FeishuNotifier("test-app-id", "bad-secret")
        with pytest.raises(RuntimeError, match="Failed to get tenant token"):
            notifier._get_token()


class TestFeishuNotifierSend:
    # Chat id used in these tests
    CHAT_ID = "oc_test123"

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_send_card_success(self, httpx_mock):
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 0, "tenant_access_token": "t-send", "expire": 7200},
        )
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            method="POST",
            json={"code": 0, "data": {"message_id": "om_test"}},
        )

        notifier = FeishuNotifier("test-app-id", "test-secret")
        result = notifier.send_card(self.CHAT_ID, "测试标题", "测试内容")

        assert result is True
        # Verify send request body
        send_req = httpx_mock.get_requests()[1]
        body = json.loads(send_req.content)
        assert body["msg_type"] == "interactive"
        assert body["receive_id"] == self.CHAT_ID

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_send_card_returns_false_on_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 0, "tenant_access_token": "t-send", "expire": 7200},
        )
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            method="POST",
            status_code=500,
        )

        notifier = FeishuNotifier("test-app-id", "test-secret")
        result = notifier.send_card(self.CHAT_ID, "测试标题", "测试内容")

        assert result is False

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_send_card_returns_false_on_network_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 0, "tenant_access_token": "t-send", "expire": 7200},
        )
        httpx_mock.add_exception(
            url="https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            exception=httpx.ConnectError("connection refused"),
        )

        notifier = FeishuNotifier("test-app-id", "test-secret")
        result = notifier.send_card(self.CHAT_ID, "测试标题", "测试内容")

        assert result is False

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_send_text_success(self, httpx_mock):
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 0, "tenant_access_token": "t-send", "expire": 7200},
        )
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            method="POST",
            json={"code": 0, "data": {"message_id": "om_text"}},
        )

        notifier = FeishuNotifier("test-app-id", "test-secret")
        result = notifier.send_text(self.CHAT_ID, "纯文本消息")

        assert result is True
        send_req = httpx_mock.get_requests()[1]
        body = json.loads(send_req.content)
        assert body["msg_type"] == "text"

    @pytest.mark.httpx_mock(can_send_already_matched_responses=True)
    def test_send_text_returns_false_on_api_error(self, httpx_mock):
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            method="POST",
            json={"code": 0, "tenant_access_token": "t-send", "expire": 7200},
        )
        httpx_mock.add_response(
            url="https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            method="POST",
            json={"code": 11222, "msg": "chat not found"},
        )

        notifier = FeishuNotifier("test-app-id", "test-secret")
        result = notifier.send_text(self.CHAT_ID, "测试")

        assert result is False
