"""Card configurations and cashback calculation logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

CARD_CONFIG = {
    "UOB_ONE": {
        "name": "UOB ONE Classic",
        "issuer": "UOB",
        "period_type": "cycle",  # Statement cycle 17th to 16th
        "cycle_day": 17,
        "min_spend": 800.0,
        "categories": [
            {"key": "Dining", "rate": 0.10, "cap": 10.0},
            {"key": "Petrol", "rate": 0.10, "cap": 10.0},
            {"key": "Groceries", "rate": 0.10, "cap": 10.0},
            {"key": "Grab", "rate": 0.10, "cap": 10.0},
            {"key": "Others", "rate": 0.002, "cap": None},
        ],
    },
    "HLB_WISE": {
        "name": "HLB Wise Gold",
        "issuer": "Hong Leong Bank",
        "period_type": "cycle",  # Updated to cycle 14th to 13th
        "cycle_day": 14,
        "min_spend": 1000.0,
        "categories": [
            {"key": "Dining", "wknd_rate": 0.15, "wkday_rate": 0.005, "cap": 20.0},
            {"key": "Petrol", "wknd_rate": 0.10, "wkday_rate": 0.005, "cap": 15.0},
            {"key": "Groceries", "wknd_rate": 0.10, "wkday_rate": 0.005, "cap": 15.0},
            {"key": "Online Whitelist", "wknd_rate": 0.01, "wkday_rate": 0.01, "cap": 15.0},
            {"key": "Others", "wknd_rate": 0.002, "wkday_rate": 0.002, "cap": None},
        ],
    },
}

CATEGORY_COLORS = {
    "Dining": "#F59E0B",
    "Petrol": "#EF4444",
    "Groceries": "#10B981",
    "Grab": "#06B6D4",
    "Online Whitelist": "#8B5CF6",
    "Others": "#6B7280",
}

USERS = ["JRen", "Sarah"]
USER_COLORS = {"JRen": "#2563EB", "Sarah": "#EC4899"}


def to_key(d: date) -> str:
    return d.isoformat()


def is_weekend(d_str: str) -> bool:
    dt = date.fromisoformat(d_str.split("T")[0])
    return dt.weekday() in (5, 6)  # 5=Saturday, 6=Sunday


def format_rm(val: float) -> str:
    return f"RM{val:,.2f}"


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    m = month - 1 + delta
    y = year + m // 12
    return y, (m % 12) + 1


def period_for(card_id: str, offset: int = 0) -> dict:
    today = date.today()
    cfg = CARD_CONFIG[card_id]

    if cfg["period_type"] == "cycle":
        start_day = cfg["cycle_day"]
        # If today is before cycle start day, current active period started last month
        base_month = today.month if today.day >= start_day else today.month - 1
        base_year = today.year if today.day >= start_day else (today.year if today.month > 1 else today.year - 1)
        if base_month == 0:
            base_month = 12

        start_y, start_m = shift_month(base_year, base_month, offset)
        end_y, end_m = shift_month(start_y, start_m, 1)

        start_date = date(start_y, start_m, start_day)
        # End date is start_day - 1 of next month
        end_date = date(end_y, end_m, start_day) - timedelta(days=1)

        return {
            "start_key": to_key(start_date),
            "end_key": to_key(end_date),
            "label": f"{start_date.strftime('%d %b')} – {end_date.strftime('%d %b %Y')}",
        }

    # Fallback to standard calendar month
    y, m = shift_month(today.year, today.month, offset)
    start_date = date(y, m, 1)
    next_y, next_m = shift_month(y, m, 1)
    end_date = date(next_y, next_m, 1) - timedelta(days=1)
    return {
        "start_key": to_key(start_date),
        "end_key": to_key(end_date),
        "label": start_date.strftime("%B %Y"),
    }


def compute_cashback(card_config: dict, txs: list[dict]) -> dict:
    total_spend = sum(t["amount"] for t in txs)
    qualified = total_spend >= card_config["min_spend"]
    cat_results = []
    total_cashback = 0.0

    for cat in card_config["categories"]:
        ckey = cat["key"]
        cat_txs = [t for t in txs if t["category"] == ckey]
        spend = sum(t["amount"] for t in cat_txs)
        cap = cat.get("cap")

        earned = 0.0
        if "rate" in cat:
            earned = spend * cat["rate"]
        else:
            for t in cat_txs:
                wknd = is_weekend(t["date"])
                r = cat["wknd_rate"] if wknd else cat["wkday_rate"]
                earned += t["amount"] * r

        capped = False
        if cap is not None and earned > cap:
            earned = cap
            capped = True

        total_cashback += earned
        cat_results.append({
            "key": ckey,
            "spend": spend,
            "cashback": round(earned, 2),
            "cap": cap,
            "capped": capped,
        })

    return {
        "total_spend": round(total_spend, 2),
        "total_cashback": round(total_cashback, 2),
        "qualified": qualified,
        "categories": cat_results,
    }