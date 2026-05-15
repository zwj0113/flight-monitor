from datetime import datetime
import httpx


def format_report(
    combinations: list[dict],
    price_changes: list[dict],
    trend: dict,
) -> str:
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [f"✈️ 机票监控报告 - {now}", ""]

    if not combinations:
        lines.append("⚠️ 本次查询未获取到航班数据，请检查去哪儿页面是否可用。")
        return "\n".join(lines)

    lines.append("🏆 最优组合 Top 5:")
    lines.append("")

    for i, combo in enumerate(combinations, 1):
        ob = combo['outbound']
        rt = combo['return']
        stops_ob = "直飞" if ob.get('stops', 0) == 0 else f"经停{ob.get('stops')}"
        stops_rt = "直飞" if rt.get('stops', 0) == 0 else f"经停{rt.get('stops')}"
        ob_change = _get_flight_change(ob['flight_no'], price_changes)
        rt_change = _get_flight_change(rt['flight_no'], price_changes)

        lines.append(f"{i}. 去程: {ob['departure_airport']}→{ob['arrival_airport']} "
                     f"{ob['flight_no']} ¥{ob['price']:,} ({stops_ob}){ob_change}")
        lines.append(f"   回程: {rt['departure_airport']}→{rt['arrival_airport']} "
                     f"{rt['flight_no']} ¥{rt['price']:,} ({stops_rt}){rt_change}")
        lines.append(f"   总价: ¥{combo['total_price']:,}")
        lines.append("")

    lines.append("---")
    if trend['direction'] == 'down':
        lines.append(f"📉 价格趋势: 较上次查询 降{abs(trend['percent'])}%")
    elif trend['direction'] == 'up':
        lines.append(f"📈 价格趋势: 较上次查询 涨{trend['percent']}%")
    else:
        lines.append("📌 价格趋势: 首次查询，暂无对比数据")

    return "\n".join(lines)


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


def send_price_drop_alert(
    webhook_url: str,
    combinations: list[dict],
    threshold: int,
) -> bool:
    """Send alert if best combination price dropped below threshold."""
    if not combinations:
        return False

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    best = combinations[0]
    content = (
        f"🔥 机票降价提醒 - {now}\n\n"
        f"最优组合: {best['outbound']['departure_airport']}→"
        f"{best['outbound']['arrival_airport']} + "
        f"{best['return']['departure_airport']}→"
        f"{best['return']['arrival_airport']}\n"
        f"当前最低总价: ¥{best['total_price']:,}"
    )
    return send_feishu_notification(webhook_url, "机票降价提醒", content)
