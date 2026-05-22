#!/usr/bin/env python3
"""Flight price monitor - checks Qunar for cheapest round-trip flights.

Usage:
    python main.py              # start scheduler (every 6 hours)
    python main.py --now        # run immediately on start then schedule
    python main.py --once       # run once and exit (no scheduler)
"""

import argparse
import os
import sys
import time

# Fix Windows console encoding for emoji/Chinese output
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Ensure the project root is on sys.path for direct script execution
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_loader import load_config
from database import FlightDB
from searcher import build_all_search_params, search_all_routes
from analyzer import compute_combinations, detect_price_changes, compute_trend, compute_baseline
from notifier import format_report, FeishuNotifier


def run_query(config: dict) -> None:
    print("=" * 60)
    print(f"Flight monitor query started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    db = FlightDB(config['database']['path'])
    search_params = build_all_search_params(
        config['flight']['departure_airports'],
        config['flight']['arrival_airport'],
        config['flight']['return_airports'],
        config['flight']['outbound_date'],
        config['flight']['return_date'],
    )

    all_flights = search_all_routes(
        search_params,
        headless=True,
        proxy=config['anti_detect']['proxy'],
        min_delay=config['anti_detect']['min_delay'],
        max_delay=config['anti_detect']['max_delay'],
    )

    if not all_flights:
        print("No flights found in this run.")
        _send_empty_report(config)
        return

    db.save_flights(all_flights)

    outbounds = [f for f in all_flights if f['direction'] == 'outbound']
    returns = [f for f in all_flights if f['direction'] == 'return']

    combinations = compute_combinations(outbounds, returns, top_n=5)
    baseline = compute_baseline(all_flights)

    prev_outbounds = []
    prev_returns = []
    for dep in config['flight']['departure_airports']:
        prev_outbounds.extend(
            db.get_previous_prices('outbound', dep['code'], 'URC', config['flight']['outbound_date'])
        )
    for arr in config['flight']['return_airports']:
        prev_returns.extend(
            db.get_previous_prices('return', 'URC', arr['code'], config['flight']['return_date'])
        )
    all_prev = prev_outbounds + prev_returns

    if all_prev:
        prev_combinations = compute_combinations(
            [f for f in all_prev if f['direction'] == 'outbound'],
            [f for f in all_prev if f['direction'] == 'return'],
            top_n=5,
        )
        trend = compute_trend(combinations, prev_combinations)
    else:
        trend = {'direction': 'unchanged', 'percent': 0.0}

    changes = detect_price_changes(all_flights, all_prev)

    report = format_report(combinations, changes, trend, baseline=baseline)
    print(report)

    feishu_cfg = config['notification']['feishu']
    threshold = config['notification']['price_drop_threshold']

    notifier = FeishuNotifier(feishu_cfg['app_id'], feishu_cfg['app_secret'])
    chat_id = feishu_cfg['chat_id']

    notifier.send_card(chat_id, "机票监控报告", report)
    if any(c['change'] < -threshold for c in changes):
        _send_drop_alert(notifier, chat_id, combinations)

    print(f"Query completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")


def _send_empty_report(config: dict) -> None:
    feishu_cfg = config['notification']['feishu']
    notifier = FeishuNotifier(feishu_cfg['app_id'], feishu_cfg['app_secret'])
    msg = f"⚠️ {time.strftime('%Y-%m-%d %H:%M')}\n\n本次查询未获取到航班数据，请检查去哪儿页面是否正常。"
    notifier.send_card(feishu_cfg['chat_id'], "机票监控报告", msg)


def _send_drop_alert(notifier: FeishuNotifier, chat_id: str, combinations: list[dict]) -> None:
    best = combinations[0]
    msg = (
        f"🔥 机票降价提醒 - {time.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"最优组合: {best['outbound']['departure_airport']}→"
        f"{best['outbound']['arrival_airport']} + "
        f"{best['return']['departure_airport']}→"
        f"{best['return']['arrival_airport']}\n"
        f"当前最低总价: ¥{best['total_price']:,}"
    )
    notifier.send_card(chat_id, "机票降价提醒", msg)


def main():
    parser = argparse.ArgumentParser(description='Flight price monitor')
    parser.add_argument('--now', action='store_true', help='Run immediately on start')
    parser.add_argument('--once', action='store_true', help='Run once and exit (no scheduler)')
    args = parser.parse_args()

    config = load_config()

    if args.once or args.now:
        run_query(config)
        if args.once:
            return

    from apscheduler.schedulers.blocking import BlockingScheduler
    scheduler = BlockingScheduler()
    interval = config['schedule']['interval_hours']

    @scheduler.scheduled_job('interval', hours=interval, id='flight_monitor')
    def scheduled_job():
        run_query(config)

    print(f"Scheduler started. Running every {interval} hours. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("\nScheduler stopped.")


if __name__ == '__main__':
    main()
