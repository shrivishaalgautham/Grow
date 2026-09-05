from datetime import datetime

from app.config import settings
from app.schemas import Item, Signal

MAX_ITEMS = 8


def verification_message(to: str, token: str) -> tuple[str, str]:
    link = f"{settings.app_base_url}/?verify={token}"
    text = (
        "Confirm alerts for your Smart Market Watchlist.\n\n"
        f"Open this link to start receiving alerts at {to}:\n{link}\n\n"
        "The link works once and expires in 24 hours. If you did not ask for this, ignore it; "
        "nothing is sent until the address is confirmed.\n"
    )
    return "Confirm your watchlist alerts", text


def alert_message(
    items: list[tuple[Item, list[Signal]]], now: datetime, unsubscribe_token: str
) -> tuple[str, str]:
    symbols = [_base(item.symbol) for item, _ in items]
    count = len(items)
    listed = ", ".join(symbols[:4]) + ("…" if count > 4 else "")
    subject = f"Watchlist: {count} {'stock' if count == 1 else 'stocks'} did something ({listed})"
    lines = [
        f"{count} of your watched stocks moved for reasons their peers do not explain, "
        f"as of {now:%d %b %H:%M} IST.",
        "",
    ]
    for item, signals in items[:MAX_ITEMS]:
        lines.append(
            f"{_base(item.symbol)}  ₹{item.quote.price:,.2f}  "
            f"today {item.today_change_pct:+.1f}% | peers {item.peer_change_pct:+.1f}% | "
            f"stock-specific {item.residual_pct:+.1f}%"
        )
        for signal in signals:
            lines.append(f"  - {signal.headline}: {signal.detail}")
        if item.catalyst_status == "none_found":
            lines.append("  - No public catalyst found.")
        lines.append("")
    if count > MAX_ITEMS:
        lines.append(f"…and {count - MAX_ITEMS} more on the watchlist page.")
        lines.append("")
    lines += [
        f"Open the watchlist: {settings.app_base_url}/watchlist",
        "",
        "This is an attention tool, not advice. It surfaces what is statistically unusual, "
        "which is not the same as what is important.",
        "Stop these emails: "
        f"{settings.api_base_url}/api/notifications/unsubscribe?token={unsubscribe_token}",
    ]
    return subject, "\n".join(lines)


def _base(symbol: str) -> str:
    return symbol.split(".")[0]
