"""Cashback Tracker — UOB ONE & HLB WISE (Streamlit port)"""

from __future__ import annotations

import json
from datetime import date

import plotly.graph_objects as go
import streamlit as st

import db
from cards import (
    CARD_CONFIG,
    CATEGORY_COLORS,
    USER_COLORS,
    USERS,
    compute_cashback,
    format_rm,
    is_weekend,
    period_for,
    to_key,
)

st.set_page_config(page_title="Cashback Tracker", page_icon="💳", layout="centered")
db.init_db()

CATEGORY_ICONS = {
    "Dining": "🍽️",
    "Petrol": "⛽",
    "Groceries": "🛒",
    "Grab": "🚗",
    "Online Whitelist": "🌐",
    "Others": "👛",
}

TAB_LABELS = {"UOB_ONE": "UOB ONE", "HLB_WISE": "HLB WISE", "BY_USER": "By User"}
ACCENTS = {"UOB_ONE": "#1E4FD8", "HLB_WISE": "#C23B3B", "BY_USER": "#111318"}

# ---------- session state ----------
if "offsets" not in st.session_state:
    st.session_state.offsets = {"UOB_ONE": 0, "HLB_WISE": 0}
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "UOB_ONE"

active_tab = st.session_state.active_tab
accent = ACCENTS[active_tab]


# ---------- date display helper ----------
def format_display_date(d_val) -> str:
    """Formats dates as DD/MMM/YYYY (e.g. 15/Sep/2026)."""
    if isinstance(d_val, str):
        try:
            d_val = date.fromisoformat(d_val)
        except ValueError:
            return d_val
    return d_val.strftime("%d/%b/%Y")


# ---------- global styling ----------
st.markdown(
    f"""
    <style>
    .stApp {{ background: #F2F4F8; }}
    .main .block-container {{
        max-width: 480px; padding-top: 1.2rem; padding-bottom: 6rem;
    }}
    #MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height:0; }}

    .card {{
        background: white; border-radius: 18px; padding: 18px 20px;
        box-shadow: 0 1px 2px rgba(16,24,40,.04); margin-bottom: 16px;
        color: #111318;
    }}
    [data-testid="stMarkdownContainer"] {{ color: #111318; }}
    .pill {{
        display:inline-block; padding:4px 10px; border-radius:999px;
        font-size:11px; font-weight:600; background:#EEF0F4; color:#555;
    }}
    .pill-ok {{ background:#DCFCE7; color:#166534; }}
    .cat-row {{ display:flex; align-items:center; gap:12px; padding:9px 0; }}
    .cat-icon {{
        width:34px; height:34px; border-radius:10px; display:flex;
        align-items:center; justify-content:center; font-size:16px; flex-shrink:0;
    }}
    .cat-main {{ flex:1; min-width:0; }}
    .cat-title-row {{ display:flex; justify-content:space-between; font-weight:600; font-size:14px; }}
    .cat-sub-row {{ display:flex; justify-content:space-between; font-size:12px; color:#8A8F98; }}
    .txn-row {{ display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid #F0F1F4; }}
    .txn-row:last-child {{ border-bottom:none; }}
    .badge {{ font-size:10px; font-weight:700; padding:2px 7px; border-radius:999px; color:white; }}

    /* Ghost buttons scoped strictly to nav arrows, edit, and delete */
    div[class*="st-key-prev_"] button,
    div[class*="st-key-next_"] button,
    div[class*="st-key-del_"] button,
    div[class*="st-key-edit_"] button {{
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 4px 6px !important;
    }}
    div[class*="st-key-prev_"] button:hover,
    div[class*="st-key-next_"] button:hover,
    div[class*="st-key-del_"] button:hover,
    div[class*="st-key-edit_"] button:hover {{
        background: #F2F4F8 !important;
        color: {accent} !important;
        border-radius: 8px !important;
    }}

    /* Fixed bottom Add Transaction bar */
    .st-key-bottom_bar {{
        position: fixed; left:50%; transform: translateX(-50%);
        bottom: 0; width: 100%; max-width: 480px;
        padding: 10px 20px 22px; background: linear-gradient(180deg, rgba(242,244,248,0) 0%, #F2F4F8 35%);
        z-index: 999;
    }}
    .st-key-add_txn_btn button {{
        background: {accent} !important; color: white !important;
        border: 2px solid {accent} !important;
        border-radius: 14px !important; height: 52px !important;
        font-weight: 700 !important; font-size: 15px !important; width: 100%;
        box-shadow: 0 6px 16px rgba(0,0,0,.18) !important;
    }}
    .st-key-add_txn_btn button:hover {{ opacity:.92; color:white !important; }}

    /* Dialog submit buttons outline & box styling */
    .st-key-dialog_add_txn button,
    .st-key-dialog_edit_txn button,
    div[data-testid="stDialog"] button[kind="primary"] {{
        border: 2px solid {accent} !important;
        background: {accent} !important;
        color: white !important;
        border-radius: 12px !important;
        height: 46px !important;
        font-weight: 700 !important;
        font-size: 15px !important;
        width: 100% !important;
        box-shadow: 0 2px 8px rgba(0,0,0,.12) !important;
    }}
    .st-key-dialog_add_txn button:hover,
    .st-key-dialog_edit_txn button:hover,
    div[data-testid="stDialog"] button[kind="primary"]:hover {{
        opacity: .92 !important;
        color: white !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def get_transactions() -> list[dict]:
    return db.get_transactions()


def cat_icon_html(key: str) -> str:
    color = CATEGORY_COLORS.get(key, "#9AA3AF")
    icon = CATEGORY_ICONS.get(key, "👛")
    return f'<div class="cat-icon" style="background:{color}2e;">{icon}</div>'


def save_edited_transaction(txn_id, card: str, user: str, amount: float, txn_date: str, category: str, remark: str | None):
    """Safely updates a transaction record across different db implementations."""
    for fn_name in ("update_transaction", "edit_transaction", "modify_transaction"):
        if hasattr(db, fn_name):
            try:
                getattr(db, fn_name)(
                    id=txn_id, card=card, user=user, amount=amount,
                    date=txn_date, category=category, remark=remark,
                )
                return
            except TypeError:
                try:
                    getattr(db, fn_name)(txn_id, card, user, amount, txn_date, category, remark)
                    return
                except Exception:
                    pass

    # Fallback to replace_all if available
    if hasattr(db, "replace_all"):
        txns = db.get_transactions()
        for t in txns:
            if str(t.get("id")) == str(txn_id):
                t["card"] = card
                t["user"] = user
                t["amount"] = amount
                t["date"] = txn_date
                t["category"] = category
                t["remark"] = remark
                break
        db.replace_all(txns)
        return

    # Secondary fallback: remove and add
    db.remove_transaction(txn_id)
    db.add_transaction(
        card=card, user=user, amount=amount,
        date=txn_date, category=category, remark=remark,
    )


# ---------- donut chart ----------
def donut_chart(slices: list[dict], center_value: str, center_label: str, key: str):
    slices = [s for s in slices if s["value"] > 0]
    if not slices:
        fig = go.Figure()
        fig.update_layout(
            annotations=[dict(
                text=f"<b>{center_value}</b><br><span style='font-size:11px;color:#8A8F98'>{center_label}</span>",
                x=0.5, y=0.5, showarrow=False, font=dict(size=18, color="#111318"),
            )],
            shapes=[dict(type="circle", xref="paper", yref="paper", x0=0.18, y0=0.18, x1=0.82, y1=0.82,
                         line=dict(color="#EEF0F4", width=18))],
            height=220, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
            paper_bgcolor="white", plot_bgcolor="white",
            xaxis=dict(visible=False, range=[0, 1], fixedrange=True),
            yaxis=dict(visible=False, range=[0, 1], fixedrange=True),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)
        return

    fig = go.Figure(
        data=[go.Pie(
            labels=[s["label"] for s in slices], values=[s["value"] for s in slices],
            hole=0.72, marker=dict(colors=[s["color"] for s in slices], line=dict(width=0)),
            textinfo="none", sort=False,
        )]
    )
    fig.update_layout(
        showlegend=False, height=220, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="white", plot_bgcolor="white",
        annotations=[dict(
            text=f"<b>{center_value}</b><br><span style='font-size:11px;color:#8A8F98'>{center_label}</span>",
            x=0.5, y=0.5, showarrow=False, font=dict(size=18, color="#111318"),
        )],
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key=key)


# ---------- add transaction dialog ----------
@st.dialog("Add transaction")
def add_transaction_dialog(default_card: str):
    card = st.radio(
        "Card", options=list(CARD_CONFIG.keys()),
        format_func=lambda c: CARD_CONFIG[c].name,
        index=list(CARD_CONFIG.keys()).index(default_card), horizontal=True,
    )
    user = st.radio("Paid by", options=USERS, horizontal=True)

    # Starts from 0 without 0.00 decimals
    amount = st.number_input(
        "Amount (RM)", min_value=0.0, value=None, placeholder="0", step=0.01, format="%g"
    )

    # Input format as DD/MM/YYYY
    txn_date = st.date_input("Date", value=date.today(), format="DD/MM/YYYY")

    weekend_flag = is_weekend(to_key(txn_date))
    st.caption(f"{'🟢 Weekend' if weekend_flag else '⚪ Weekday'} · {format_display_date(txn_date)}")

    categories = [c.key for c in CARD_CONFIG[card].categories]
    category = st.selectbox("Category", categories)
    remark = st.text_input("Remark (optional)", max_chars=60, placeholder="e.g. Insurance, Netflix, utilities")

    if st.button("Add transaction", key="dialog_add_txn", type="primary", use_container_width=True):
        actual_amount = amount if amount is not None else 0.0
        if actual_amount <= 0:
            st.error("Enter an amount greater than 0.")
        else:
            db.add_transaction(
                card=card, user=user, amount=round(actual_amount, 2),
                date=to_key(txn_date), category=category, remark=remark.strip() or None,
            )
            st.rerun()


# ---------- edit transaction dialog ----------
@st.dialog("Edit transaction")
def edit_transaction_dialog(txn: dict):
    txn_id = txn["id"]
    default_card = txn["card"] if txn["card"] in CARD_CONFIG else list(CARD_CONFIG.keys())[0]
    card = st.radio(
        "Card", options=list(CARD_CONFIG.keys()),
        format_func=lambda c: CARD_CONFIG[c].name,
        index=list(CARD_CONFIG.keys()).index(default_card), horizontal=True,
        key=f"edit_card_{txn_id}",
    )
    user = st.radio(
        "Paid by", options=USERS,
        index=USERS.index(txn["user"]) if txn["user"] in USERS else 0,
        horizontal=True, key=f"edit_user_{txn_id}",
    )

    amount = st.number_input(
        "Amount (RM)", min_value=0.0, value=float(txn["amount"]),
        step=0.01, format="%g", key=f"edit_amt_{txn_id}",
    )

    try:
        current_date = date.fromisoformat(txn["date"])
    except Exception:
        current_date = date.today()

    txn_date = st.date_input("Date", value=current_date, format="DD/MM/YYYY", key=f"edit_date_{txn_id}")

    weekend_flag = is_weekend(to_key(txn_date))
    st.caption(f"{'🟢 Weekend' if weekend_flag else '⚪ Weekday'} · {format_display_date(txn_date)}")

    categories = [c.key for c in CARD_CONFIG[card].categories]
    cat_idx = categories.index(txn["category"]) if txn["category"] in categories else 0
    category = st.selectbox("Category", categories, index=cat_idx, key=f"edit_cat_{txn_id}")
    remark = st.text_input(
        "Remark (optional)", value=txn.get("remark") or "", max_chars=60,
        placeholder="e.g. Insurance, Netflix, utilities", key=f"edit_rem_{txn_id}",
    )

    if st.button("Save changes", key="dialog_edit_txn", type="primary", use_container_width=True):
        if amount <= 0:
            st.error("Enter an amount greater than 0.")
        else:
            save_edited_transaction(
                txn_id=txn_id, card=card, user=user, amount=round(amount, 2),
                txn_date=to_key(txn_date), category=category, remark=remark.strip() or None,
            )
            st.rerun()


# ---------- card panel ----------
def render_card_panel(card_id: str, transactions: list[dict]):
    config = CARD_CONFIG[card_id]
    offset = st.session_state.offsets[card_id]
    period = period_for(card_id, offset)
    card_accent = ACCENTS[card_id]

    in_period = [
        t for t in transactions
        if t["card"] == card_id and period["start_key"] <= t["date"] <= period["end_key"]
    ]
    in_period.sort(key=lambda t: t["date"], reverse=True)

    result = compute_cashback(config, in_period)
    progress = min(100, round((result["total_spend"] / config.min_spend) * 100)) if config.min_spend else 100
    period_badge = "Cycle 17–16" if config.period_type == "cycle" else "Calendar month"

    st.markdown(
        f"""
        <div style="background:{card_accent};border-radius:18px;padding:22px 20px;color:white;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <div style="font-size:11px;letter-spacing:.08em;opacity:.75;text-transform:uppercase;">{config.issuer}</div>
              <div style="font-size:24px;font-weight:700;margin-top:2px;">{config.name}</div>
            </div>
            <span class="pill" style="background:rgba(255,255,255,.18);color:white;">{period_badge}</span>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-top:26px;">
            <div>
              <div style="font-size:11px;opacity:.75;text-transform:uppercase;">Cashback earned</div>
              <div style="font-family:monospace;font-size:28px;font-weight:700;">{format_rm(result['total_cashback'])}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:11px;opacity:.75;text-transform:uppercase;">Total spend</div>
              <div style="font-family:monospace;font-size:18px;font-weight:700;">{format_rm(result['total_spend'])}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # period nav
    st.markdown('<div class="card" style="padding:6px 8px;">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 5, 1])
    with c1:
        if st.button("‹", key=f"prev_{card_id}", use_container_width=True):
            st.session_state.offsets[card_id] -= 1
            st.rerun()
    with c2:
        st.markdown(f"<div style='text-align:center;padding-top:8px;font-weight:600;font-size:14px;'>{period['label']}</div>", unsafe_allow_html=True)
    with c3:
        if st.button("›", key=f"next_{card_id}", disabled=offset >= 0, use_container_width=True):
            st.session_state.offsets[card_id] += 1
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # min spend
    status_html = (
        '<span class="pill pill-ok">Unlocked</span>' if result["qualified"]
        else f'<span class="pill">{format_rm(max(0, config.min_spend - result["total_spend"]))} to go</span>'
    )
    st.markdown(
        f"""
        <div class="card">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <span style="font-weight:600;font-size:15px;">Minimum spend</span>{status_html}
          </div>
          <div style="height:9px;border-radius:999px;background:#EEF0F4;overflow:hidden;">
            <div style="height:100%;width:{progress}%;border-radius:999px;
                        background:{'#16A34A' if result['qualified'] else card_accent};"></div>
          </div>
          <div style="display:flex;justify-content:space-between;margin-top:6px;font-family:monospace;font-size:12px;color:#8A8F98;">
            <span>{format_rm(result['total_spend'])}</span><span>{format_rm(config.min_spend)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # donut + breakdown
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-weight:600;font-size:15px;margin-bottom:8px;">Spend breakdown</div>', unsafe_allow_html=True)
    slices = [
        {"label": c["key"], "value": c["spend"], "color": CATEGORY_COLORS.get(c["key"], "#9AA3AF")}
        for c in result["categories"] if c["spend"] > 0
    ]
    col_a, col_b = st.columns([1, 1.3])
    with col_a:
        donut_chart(slices, format_rm(result["total_spend"]), "spent", key=f"donut_{card_id}")
    with col_b:
        rows = ""
        for c in result["categories"]:
            cap_txt = f"cap {format_rm(c['cap'])}" if c["cap"] is not None else ""
            capped_txt = " · <b>capped</b>" if c["capped"] else ""
            rows += f"""
            <div class="cat-row">
              {cat_icon_html(c['key'])}
              <div class="cat-main">
                <div class="cat-title-row"><span>{c['key']}</span><span style="font-family:monospace;">{format_rm(c['spend'])}</span></div>
                <div class="cat-sub-row"><span>{format_rm(c['cashback'])} back{capped_txt}</span><span>{cap_txt}</span></div>
              </div>
            </div>"""
        st.markdown(rows, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # transactions
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<div style="font-weight:600;font-size:15px;margin-bottom:4px;">Transactions <span style="color:#8A8F98;">({len(in_period)})</span></div>', unsafe_allow_html=True)
    if not in_period:
        st.caption("No transactions in this period yet.")
    else:
        for t in in_period:
            weekend = is_weekend(t["date"])
            u_color = USER_COLORS.get(t["user"], "#888")
            remark_txt = f" · {t['remark']}" if t.get("remark") else ""
            weekend_badge = '<span class="badge" style="background:#16A34A;">Weekend</span>' if weekend else '<span class="badge" style="background:#B8BCC4;">Weekday</span>'
            col1, col2 = st.columns([4.4, 1.8])
            with col1:
                st.markdown(
                    f"""
                    <div>
                      <div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;">
                        <span style="font-weight:600;font-size:14px;">{t['category']}</span>
                        <span class="badge" style="background:{u_color};">{t['user']}</span>
                        {weekend_badge}
                      </div>
                      <div style="font-size:12px;color:#8A8F98;">{format_display_date(t['date'])}{remark_txt}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(f'<div style="font-family:monospace;text-align:right;font-weight:600;font-size:14px;">{format_rm(t["amount"])}</div>', unsafe_allow_html=True)
                act_c1, act_c2 = st.columns(2)
                with act_c1:
                    if st.button("✏️", key=f"edit_{t['id']}", help="Edit transaction"):
                        edit_transaction_dialog(t)
                with act_c2:
                    if st.button("🗑️", key=f"del_{t['id']}", help="Delete transaction"):
                        db.remove_transaction(t["id"])
                        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ---------- user panel ----------
def render_user_panel(transactions: list[dict]):
    periods = {cid: period_for(cid, st.session_state.offsets[cid]) for cid in CARD_CONFIG}
    current = [t for t in transactions if periods[t["card"]]["start_key"] <= t["date"] <= periods[t["card"]]["end_key"]]
    total_spend = sum(t["amount"] for t in current)

    st.markdown(
        f"""
        <div class="card">
          <div style="font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#8A8F98;">Current periods · both cards</div>
          <div style="font-family:monospace;font-size:28px;font-weight:700;margin-top:4px;">{format_rm(total_spend)}</div>
          <div style="font-size:12px;color:#8A8F98;">combined household spend</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    per_user = []
    for u in USERS:
        items = [t for t in current if t["user"] == u]
        spend = sum(t["amount"] for t in items)
        by_card = {cid: sum(t["amount"] for t in items if t["card"] == cid) for cid in CARD_CONFIG}
        per_user.append({"user": u, "spend": spend, "count": len(items), "by_card": by_card})

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown('<div style="font-weight:600;font-size:15px;margin-bottom:8px;">Who spent what</div>', unsafe_allow_html=True)
    if total_spend == 0:
        st.caption("No transactions in the current periods yet.")
    else:
        slices = [{"label": p["user"], "value": p["spend"], "color": USER_COLORS[p["user"]]} for p in per_user]
        donut_chart(slices, format_rm(total_spend), "total", key="donut_by_user")
        for p in per_user:
            pct = round((p["spend"] / total_spend) * 100) if total_spend else 0
            breakdown = "  ·  ".join(f"{CARD_CONFIG[c].name} {format_rm(v)}" for c, v in p["by_card"].items())
            st.markdown(
                f"""
                <div style="margin-top:10px;">
                  <div style="display:flex;align-items:center;gap:8px;font-size:14px;">
                    <span style="width:10px;height:10px;border-radius:50%;background:{USER_COLORS[p['user']]};display:inline-block;"></span>
                    <span style="font-weight:600;">{p['user']}</span>
                    <span style="margin-left:auto;font-family:monospace;">{format_rm(p['spend'])}</span>
                  </div>
                  <div style="height:6px;border-radius:999px;background:#EEF0F4;margin-top:5px;overflow:hidden;">
                    <div style="height:100%;width:{pct}%;background:{USER_COLORS[p['user']]};border-radius:999px;"></div>
                  </div>
                  <div style="display:flex;justify-content:space-between;font-size:11px;color:#8A8F98;margin-top:3px;">
                    <span>{p['count']} txn(s) · {pct}%</span><span>{breakdown}</span>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)

    # settlement
    a, b = per_user
    diff = a["spend"] - b["spend"]
    if abs(diff) < 0.01:
        settle_text = "All square — both spent the same amount."
    else:
        frm, to, amt = (b["user"], a["user"], diff / 2) if diff > 0 else (a["user"], b["user"], -diff / 2)
        settle_text = f"<b>{frm}</b> owes <b>{to}</b> <span style='font-family:monospace;font-weight:700;'>{format_rm(amt)}</span> to split the shared spend evenly."
    st.markdown(
        f"""
        <div class="card">
          <div style="font-weight:600;font-size:15px;margin-bottom:4px;">Settle up (50/50)</div>
          <div style="font-size:13px;color:#555;">{settle_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # recent activity
    recent = sorted(current, key=lambda t: t["date"], reverse=True)[:20]
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<div style="font-weight:600;font-size:15px;margin-bottom:4px;">Recent activity <span style="color:#8A8F98;">({len(current)})</span></div>', unsafe_allow_html=True)
    if not recent:
        st.caption("Nothing to show yet.")
    else:
        for t in recent:
            weekend = is_weekend(t["date"])
            u_color = USER_COLORS.get(t["user"], "#888")
            remark_txt = f" · {t['remark']}" if t.get("remark") else ""
            weekend_badge = ' · <span class="badge" style="background:#16A34A;">Weekend</span>' if weekend else ""
            col1, col2 = st.columns([4.4, 1.8])
            with col1:
                st.markdown(
                    f"""
                    <div>
                      <div style="display:flex;align-items:center;gap:6px;">
                        <span class="badge" style="background:{u_color};">{t['user']}</span>
                        <span style="font-weight:600;font-size:14px;">{t['category']}</span>
                        <span style="font-size:12px;color:#8A8F98;">{CARD_CONFIG[t['card']].name}{weekend_badge}</span>
                      </div>
                      <div style="font-size:12px;color:#8A8F98;">{format_display_date(t['date'])}{remark_txt}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(f'<div style="font-family:monospace;text-align:right;font-weight:600;font-size:14px;">{format_rm(t["amount"])}</div>', unsafe_allow_html=True)
                act_c1, act_c2 = st.columns(2)
                with act_c1:
                    if st.button("✏️", key=f"edit_recent_{t['id']}", help="Edit transaction"):
                        edit_transaction_dialog(t)
                with act_c2:
                    if st.button("🗑️", key=f"del_recent_{t['id']}", help="Delete transaction"):
                        db.remove_transaction(t["id"])
                        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ---------- header ----------
h1, h2 = st.columns([3, 2])
with h1:
    st.markdown('<div style="font-size:20px;font-weight:700;">Cashback Tracker</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:12px;color:#8A8F98;margin-bottom:10px;">Shared by JRen &amp; Sarah</div>', unsafe_allow_html=True)
with h2:
    b1, b2 = st.columns(2)
    with b1:
        st.download_button(
            "⬇ Export", data=json.dumps(get_transactions(), indent=2, default=str),
            file_name=f"cashback_tracker_backup_{date.today().isoformat()}.json",
            mime="application/json", use_container_width=True,
        )
    with b2:
        uploaded = st.file_uploader("Import", type="json", label_visibility="collapsed")
        if uploaded is not None:
            try:
                parsed = json.load(uploaded)
                if not isinstance(parsed, list):
                    st.error("Invalid backup format. Expected a list of transactions.")
                else:
                    db.replace_all(parsed)
                    st.success("Imported!")
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to parse file: {e}")

# ---------- pill tab bar ----------
selected_label = st.pills(
    "View", options=list(TAB_LABELS.values()), default=TAB_LABELS[active_tab],
    label_visibility="collapsed",
)
new_tab = {v: k for k, v in TAB_LABELS.items()}.get(selected_label, "UOB_ONE")
if new_tab != active_tab:
    st.session_state.active_tab = new_tab
    st.rerun()

st.markdown('<hr style="border:none;border-top:1px solid #E5E7EB;margin:4px 0 16px;">', unsafe_allow_html=True)

transactions = get_transactions()

if active_tab == "UOB_ONE":
    render_card_panel("UOB_ONE", transactions)
elif active_tab == "HLB_WISE":
    render_card_panel("HLB_WISE", transactions)
else:
    render_user_panel(transactions)

with st.container(key="bottom_bar"):
    default_card = active_tab if active_tab in CARD_CONFIG else "UOB_ONE"
    if st.button("➕  Add Transaction", key="add_txn_btn", use_container_width=True):
        add_transaction_dialog(default_card)