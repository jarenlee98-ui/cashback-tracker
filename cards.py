"""
Card configuration and cashback calculation logic.

NOTE: The original project's lib/cards.ts (which held the real cashback
rates, category caps, and minimum-spend rules) was not available when this
was ported from the v0/Next.js app, so the numbers below are reasonable
placeholders recreated from scratch. Double-check them against your actual
card's terms & conditions and adjust CARD_CONFIG to match — everything else
in the app (periods, progress bars, breakdowns, settlement) will just work
once the numbers are right.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

CardId = str  # "UOB_ONE" | "HLB_WISE"
UserId = str  # "JRen" | "Sarah"

USERS: list[UserId] = ["JRen", "Sarah"]

USER_COLORS = {
    "JRen": "#4C6FE0",
    "Sarah": "#E0548C",
}

CATEGORY_COLORS = {
    "Dining": "#3FA796",
    "Petrol": "#4C6FE0",
    "Groceries": "#E0A83F",
    "Grab": "#D14E4E",
    "Online Whitelist": "#8F6FE0",
    "Others": "#9AA3AF",
}


@dataclass
class Category:
    key: str
    rate: float  # cashback rate, e.g. 0.05 = 5%
    cap: float | None = None  # RM cap on cashback earned in this category this period
    weekend_only: bool = False  # bonus rate only applies to weekend transactions


@dataclass
class CardConfig:
    id: CardId
    name: str
    issuer: str
    period_type: str  # "cycle" (17th-16th) or "calendar" (1st-end of month)
    min_spend: float
    categories: list[Category]


CARD_CONFIG: dict[CardId, CardConfig] = {
    "UOB_ONE": CardConfig(
        id="UOB_ONE",
        name="UOB ONE",
        issuer="United Overseas Bank",
        period_type="cycle",
        min_spend=800.0,
        categories=[
            Category("Dining", rate=0.05, cap=10),
            Category("Petrol", rate=0.05, cap=10),
            Category("Groceries", rate=0.05, cap=10),
            Category("Grab", rate=0.05, cap=10),
            Category("Others", rate=0.002, cap=None),
        ],
    ),
    "HLB_WISE": CardConfig(
        id="HLB_WISE",
        name="HLB WISE",
        issuer="Hong Leong Bank",
        period_type="calendar",
        min_spend=1000.0,
        categories=[
            Category("Dining", rate=0.08, cap=20, weekend_only=True),
            Category("Petrol", rate=0.08, cap=15, weekend_only=True),
            Category("Groceries", rate=0.08, cap=15, weekend_only=True),
            Category("Online Whitelist", rate=0.08, cap=15, weekend_only=True),
            Category("Others", rate=0.002, cap=None),
        ],
    ),
}


def to_key(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def parse_key(k: str) -> date:
    return datetime.strptime(k, "%Y-%m-%d").date()


def is_weekend(date_key: str) -> bool:
    d = parse_key(date_key)
    return d.weekday() >= 4  # Fri(4), Sat(5), Sun(6) — matches "weekend" bonus window


def format_rm(amount: float) -> str:
    return f"RM{amount:,.2f}"


def format_dmy(date_key: str) -> str:
    d = parse_key(date_key)
    return d.strftime("%d %b %Y")


def _month_add(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def period_for(card_id: CardId, offset: int) -> dict:
    """Returns {label, start_key, end_key} for the period `offset` cycles/months
    away from the current one (offset=0 is the period containing today,
    negative = past, and offset is clamped so you can't go into the future)."""
    config = CARD_CONFIG[card_id]
    today = date.today()

    if config.period_type == "cycle":
        # Cycle runs 17th of one month to 16th of the next.
        anchor = today if today.day >= 17 else _month_add(today, -1)
        anchor = date(anchor.year, anchor.month, 17)
        target = _month_add(anchor, offset)
        start = date(target.year, target.month, 17)
        end = _month_add(start, 1) - timedelta(days=1)
        label = f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"
    else:
        anchor = date(today.year, today.month, 1)
        target = _month_add(anchor, offset)
        start = date(target.year, target.month, 1)
        end = _month_add(start, 1) - timedelta(days=1)
        label = start.strftime("%B %Y")

    return {"label": label, "start_key": to_key(start), "end_key": to_key(end)}


def compute_cashback(config: CardConfig, transactions: list[dict]) -> dict:
    total_spend = sum(t["amount"] for t in transactions)
    qualified = total_spend >= config.min_spend

    categories = []
    total_cashback = 0.0

    for cat in config.categories:
        cat_txns = [t for t in transactions if t["category"] == cat.key]
        spend = sum(t["amount"] for t in cat_txns)

        if cat.weekend_only:
            bonus_spend = sum(t["amount"] for t in cat_txns if is_weekend(t["date"]))
            base_spend = spend - bonus_spend
            raw_cashback = bonus_spend * cat.rate + base_spend * 0.001
        else:
            raw_cashback = spend * cat.rate

        cashback = raw_cashback if not qualified else raw_cashback
        # Cashback is only actually paid out once minimum spend is met.
        if not qualified:
            cashback = 0.0
        capped = False
        if cat.cap is not None and cashback > cat.cap:
            cashback = cat.cap
            capped = True

        total_cashback += cashback
        categories.append({
            "key": cat.key,
            "spend": spend,
            "cashback": cashback,
            "cap": cat.cap,
            "capped": capped,
        })

    return {
        "total_spend": total_spend,
        "total_cashback": total_cashback,
        "qualified": qualified,
        "categories": categories,
    }
