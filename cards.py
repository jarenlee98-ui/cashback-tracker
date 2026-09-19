"""Credit card configurations, cashback calculation engine, and period helpers."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class CategoryConfig:
    key: str
    rate: float = 0.002
    weekend_rate: float | None = None
    weekday_rate: float | None = None
    cap: float | None = None


@dataclass(frozen=True)
class CardInfo:
    id: str
    name: str
    issuer: str
    min_spend: float
    period_type: str  # "calendar" or custom cycle handling
    categories: list[CategoryConfig]


# --- Card Configurations ---
CARD_CONFIG: dict[str, CardInfo] = {
    "UOB_ONE": CardInfo(
        id="UOB_ONE",
        name="UOB ONE",
        issuer="UOB",
        min_spend=800.0,
        period_type="cycle",
        categories=[
            CategoryConfig(key="Dining", rate=0.10, cap=10.0),
            CategoryConfig(key="Petrol", rate=0.10, cap=10.0),
            CategoryConfig(key="Groceries", rate=0.10, cap=10.0),
            CategoryConfig(key="Grab", rate=0.10, cap=10.0),
            CategoryConfig(key="Others", rate=0.002, cap=None),
        ],
    ),
    "HLB_WISE": CardInfo(
        id="HLB_WISE",
        name="HLB WISE",
        issuer="Hong Leong Bank",
        min_spend=1000.0,
        period_type="calendar",
        categories=[
            CategoryConfig(key="Dining", weekend_rate=0.15, weekday_rate=0.005, cap=20.0),
            CategoryConfig(key="Petrol", weekend_rate=0.10, weekday_rate=0.005, cap=15.0),
            CategoryConfig(key="Groceries", weekend_rate=0.10, weekday_rate=0.005, cap=15.0),
            CategoryConfig(key="Online Whitelist", rate=0.01, cap=15.0),
            CategoryConfig(key="Others", rate=0.002, cap=None),
        ],
    ),
}

CATEGORY_COLORS: dict[str, str] = {
    "Dining": "#F97316",
    "Petrol": "#3B82F6",
    "Groceries": "#10B981",
    "Grab": "#06B6D4",
    "Online Whitelist": "#8B5CF6",
    "Others": "#6B7280",
}

USERS: list[str] = ["JRen", "Sarah"]
USER_COLORS: dict[str, str] = {
    "JRen": "#1E4FD8",
    "Sarah": "#E11D48",
}


def to_key(d: date | str) -> str:
    if isinstance(d, str):
        return d
    return d.isoformat()


def is_weekend(d: date | str) -> bool:
    if isinstance(d, str):
        d = date.fromisoformat(d.split("T")[0])
    return d.weekday() in (5, 6)


def format_rm(val: float | int | None) -> str:
    if val is None:
        return "RM0.00"
    return f"RM{float(val):,.2f}"


def format_dmy(d: date | str) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d.split("T")[0])
    return d.strftime("%d/%b/%Y")


def _shift_month(y: int, m: int, offset: int) -> tuple[int, int]:
    total_m = (y * 12 + (m - 1)) + offset
    return total_m // 12, (total_m % 12) + 1


def _generate_uob_periods() -> list[tuple[date, date]]:
    """Builds historical and forward periods accounting for the transition cycle."""
    periods: list[tuple[date, date]] = []

    # Old cycle (17th to 16th): Oct 2024 up to 17 Aug - 16 Sep 2026
    start_y, start_m = 2024, 10
    while (start_y, start_m) <= (2026, 8):
        ey, em = _shift_month(start_y, start_m, 1)
        periods.append((date(start_y, start_m, 17), date(ey, em, 16)))
        start_y, start_m = ey, em

    # Transitional cycle: 17 Sept 2026 - 01 Oct 2026
    periods.append((date(2026, 9, 17), date(2026, 10, 1)))

    # New cycle (2nd to 1st next month): starting 02 Oct 2026 onward
    curr_y, curr_m = 2026, 10
    for _ in range(60):  # Projections for future months
        ey, em = _shift_month(curr_y, curr_m, 1)
        periods.append((date(curr_y, curr_m, 2), date(ey, em, 1)))
        curr_y, curr_m = ey, em

    return periods


def period_for(card_id: str, offset: int = 0) -> dict[str, str]:
    today = date.today()
    config = CARD_CONFIG[card_id]

    if card_id == "UOB_ONE":
        all_periods = _generate_uob_periods()
        active_idx = len(all_periods) - 1
        for idx, (s_dt, e_dt) in enumerate(all_periods):
            if s_dt <= today <= e_dt:
                active_idx = idx
                break

        target_idx = max(0, min(len(all_periods) - 1, active_idx + offset))
        start_dt, end_dt = all_periods[target_idx]
        label = f"{start_dt.strftime('%d %b')} – {end_dt.strftime('%d %b %Y')}"
    else:
        # HLB WISE: standard calendar month (1st to end of month)
        y, m = _shift_month(today.year, today.month, offset)
        last_day = calendar.monthrange(y, m)[1]
        start_dt = date(y, m, 1)
        end_dt = date(y, m, last_day)
        label = start_dt.strftime("%B %Y")

    return {
        "start_key": start_dt.isoformat(),
        "end_key": end_dt.isoformat(),
        "label": label,
    }


def compute_cashback(config: CardInfo, in_period: list[dict]) -> dict:
    total_spend = sum(float(t.get("amount", 0.0)) for t in in_period)
    qualified = total_spend >= config.min_spend

    cat_txns: dict[str, list[dict]] = {c.key: [] for c in config.categories}
    for t in in_period:
        k = t.get("category", "Others")
        if k in ("Groceries & Essentials", "Grocery"):
            k = "Groceries"
        if k not in cat_txns:
            k = "Others"
        cat_txns[k].append(t)

    categories_result = []
    total_cashback = 0.0

    for cat_cfg in config.categories:
        txs = cat_txns[cat_cfg.key]
        spend = sum(float(t.get("amount", 0.0)) for t in txs)
        earned = 0.0

        for t in txs:
            amt = float(t.get("amount", 0.0))
            txn_date = t.get("date", "")
            weekend = is_weekend(txn_date) if txn_date else False

            if cat_cfg.weekend_rate is not None and cat_cfg.weekday_rate is not None:
                rate = cat_cfg.weekend_rate if weekend else cat_cfg.weekday_rate
            else:
                rate = cat_cfg.rate

            earned += amt * rate

        capped = False
        if cat_cfg.cap is not None:
            if earned >= cat_cfg.cap:
                earned = cat_cfg.cap
                capped = True

        earned = round(earned, 2)
        total_cashback += earned

        categories_result.append({
            "key": cat_cfg.key,
            "spend": round(spend, 2),
            "cashback": earned,
            "cap": cat_cfg.cap,
            "capped": capped,
        })

    return {
        "total_spend": round(total_spend, 2),
        "total_cashback": round(total_cashback, 2),
        "qualified": qualified,
        "categories": categories_result,
    }