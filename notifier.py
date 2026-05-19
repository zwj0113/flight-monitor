import subprocess
from datetime import datetime
from pathlib import Path

import httpx

LARK_CLI = str(Path.home() / "AppData" / "Roaming" / "npm" / "lark-cli.exe")


def format_report(
    combinations: list[dict],
    price_changes: list[dict],
    trend: dict,
    baseline: dict | None = None,
) -> str:
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [f"✈️ 机票监控报告 - {now}", ""]

    if not combinations:
        lines.append("⚠️ 本次查询未获取到航班数据，请检查携程页面是否可用。")
        return "\n".join(lines)

    # Show baseline if available
    if baseline:
        lines.append(
            f"📊 上海基准: 去程最低 ¥{baseline['outbound_min']:,} ({baseline['airport']})"
            f" | 回程最低 ¥{baseline['return_min']:,} ({baseline['airport']})"
        )
        lines.append("")

    lines.append("🏆 最优组合 Top 5:")
    lines.append("")

    for i, combo in enumerate(combinations[:5], 1):
        ob = combo['outbound']
        rt = combo['return']
        ob_change = _get_flight_change(ob['flight_no'], price_changes)
        rt_change = _get_flight_change(rt['flight_no'], price_changes)

        # Format outbound line with full details
        ob_line = _format_flight_line(ob, '去程', ob_change)
        lines.append(f"{i}. {ob_line}")

        # Format return line with full details
        rt_line = _format_flight_line(rt, '回程', rt_change)
        lines.append(f"   {rt_line}")

        total_price = combo['total_price']
        # Show diff from baseline if available
        if baseline:
            baseline_total = baseline['outbound_min'] + baseline['return_min']
            diff = total_price - baseline_total
            diff_str = f"+¥{diff:,}" if diff > 0 else f"-¥{abs(diff):,}" if diff < 0 else "+¥0"
            lines.append(f"   总价: ¥{total_price:,}  (较上海基准 {diff_str})")
        else:
            lines.append(f"   总价: ¥{total_price:,}")
        lines.append("")

    lines.append("---")
    if trend['direction'] == 'down':
        lines.append(f"📉 价格趋势: 较上次查询 降{abs(trend['percent'])}%")
    elif trend['direction'] == 'up':
        lines.append(f"📈 价格趋势: 较上次查询 涨{trend['percent']}%")
    else:
        lines.append("📌 价格趋势: 首次查询，暂无对比数据")

    return "\n".join(lines)


def _format_flight_line(flight: dict, label: str, change_str: str) -> str:
    """Format a single flight line with full details.

    Example: 去程: SHA→URC CA3272 中国国航 空客320(中)
             虹桥T2 10:05→15:25 (5h20m) 托运行李额20KG ¥2,630
    """
    dep_code = flight.get('departure_airport', '')
    arr_code = flight.get('arrival_airport', '')
    flight_no = flight.get('flight_no', '')
    airline = flight.get('airline', '')
    aircraft = flight.get('aircraft_name', '')
    dep_terminal = flight.get('dep_terminal', '')
    arr_terminal = flight.get('arr_terminal', '')
    dep_time = flight.get('dep_time', '')
    arr_time = flight.get('arr_time', '')
    duration_min = flight.get('duration_minutes', 0)
    baggage_tag = flight.get('baggage_tag', '')
    price = flight.get('price', 0)
    operate_airline = flight.get('operate_airline', '')

    # Build the first part: route + flight info
    parts = [f"{label}: {dep_code}→{arr_code} {flight_no}"]
    if operate_airline:
        parts.append(f"{operate_airline}(实际承运)")
    else:
        parts.append(airline)
    if aircraft:
        parts.append(aircraft)

    line1 = " ".join(parts)

    # Build the second part: times, terminals, duration, baggage, price
    details = []
    # Departure time formatting
    dep_time_short = dep_time[-8:-3] if len(dep_time) >= 8 else dep_time
    arr_time_short = arr_time[-8:-3] if len(arr_time) >= 8 else arr_time
    time_str = f"{dep_time_short}→{arr_time_short}"
    if duration_min > 0:
        hours = duration_min // 60
        mins = duration_min % 60
        time_str += f" ({hours}h{mins}m)"
    details.append(time_str)

    # Terminal info
    terminal_parts = []
    if dep_terminal:
        terminal_parts.append(dep_terminal)
    if arr_terminal:
        terminal_parts.append(arr_terminal)
    if terminal_parts:
        details.insert(0, " ".join(terminal_parts))

    details.append(f"¥{price:,}")
    if change_str:
        details.append(change_str)

    line2 = " ".join(details)

    # Baggage on its own line if available
    result = f"{line1}\n        {line2}"
    if baggage_tag:
        result += f"\n        行李: {baggage_tag}"

    return result


def _get_flight_change(flight_no: str, changes: list[dict]) -> str:
    for c in changes:
        if c['flight_no'] == flight_no:
            direction = "↓" if c['change'] < 0 else "↑"
            return f" {direction}较上次{c['change']:+d}"
    return ""


def send_feishu_notification(webhook_url: str, title: str, content: str) -> bool:
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue",
            },
            "elements": [
                {"tag": "markdown", "content": content},
            ],
        },
    }
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        return resp.status_code == 200
    except httpx.RequestError:
        return False


def send_lark_notification(chat_id: str, title: str, content: str) -> bool:
    """Send report via lark-cli IM API to a group chat."""
    markdown = f"**{title}**\n\n{content}"
    try:
        result = subprocess.run(
            [LARK_CLI, "im", "+messages-send",
             "--chat-id", chat_id,
             "--markdown", markdown,
             "--as", "bot"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def send_price_drop_alert(
    webhook_url: str,
    combinations: list[dict],
    threshold: int,
) -> bool:
    """Send alert if best combination price dropped below threshold."""
    if not combinations:
        return False

    best = combinations[0]
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    content = (
        f"🔥 机票降价提醒 - {now}\n\n"
        f"最优组合: {best['outbound']['departure_airport']}→"
        f"{best['outbound']['arrival_airport']} + "
        f"{best['return']['departure_airport']}→"
        f"{best['return']['arrival_airport']}\n"
        f"当前最低总价: ¥{best['total_price']:,}"
    )
    return send_feishu_notification(webhook_url, "机票降价提醒", content)
