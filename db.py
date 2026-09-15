"""Cloud-backed persistence for transactions.

Uses Streamlit's built-in SQL connection (`st.connection`), configured via
`.streamlit/secrets.toml` locally or the app's "Secrets" settings on
Streamlit Community Cloud once deployed. This talks to whatever database
URL you put in secrets — a Supabase/Postgres database in production, or a
local SQLite file if you just want to test the app without the cloud.

Note: the "user" column is stored as `member` in the database, since USER
is a reserved word in Postgres — the app still sees it as `user` in the
transaction dicts everywhere else.
"""

from __future__ import annotations

import uuid

import streamlit as st
from sqlalchemy import text


def get_connection():
    return st.connection("db", type="sql")


def init_db() -> None:
    conn = get_connection()
    with conn.session as s:
        s.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id TEXT PRIMARY KEY,
                    card TEXT NOT NULL,
                    member TEXT NOT NULL,
                    amount REAL NOT NULL,
                    date TEXT NOT NULL,
                    category TEXT NOT NULL,
                    remark TEXT
                )
                """
            )
        )
        s.commit()


def _row_to_dict(row) -> dict:
    remark = row["remark"]
    if remark is None or (isinstance(remark, float) and remark != remark):  # NaN check without importing pandas/numpy
        remark = None
    return {
        "id": row["id"],
        "card": row["card"],
        "user": row["member"],
        "amount": float(row["amount"]),
        "date": row["date"],
        "category": row["category"],
        "remark": remark,
    }


def get_transactions() -> list[dict]:
    conn = get_connection()
    df = conn.query("SELECT * FROM transactions ORDER BY date DESC", ttl=0)
    return [_row_to_dict(row) for _, row in df.iterrows()]


def add_transaction(card: str, user: str, amount: float, date: str, category: str, remark: str | None = None) -> str:
    tid = str(uuid.uuid4())
    conn = get_connection()
    with conn.session as s:
        s.execute(
            text(
                "INSERT INTO transactions (id, card, member, amount, date, category, remark) "
                "VALUES (:id, :card, :member, :amount, :date, :category, :remark)"
            ),
            {
                "id": tid, "card": card, "member": user, "amount": amount,
                "date": date, "category": category, "remark": remark,
            },
        )
        s.commit()
    return tid


def remove_transaction(transaction_id: str) -> None:
    conn = get_connection()
    with conn.session as s:
        s.execute(text("DELETE FROM transactions WHERE id = :id"), {"id": transaction_id})
        s.commit()


def replace_all(transactions: list[dict]) -> None:
    """Used for JSON import: wipes and reloads the table."""
    conn = get_connection()
    with conn.session as s:
        s.execute(text("DELETE FROM transactions"))
        for t in transactions:
            s.execute(
                text(
                    "INSERT INTO transactions (id, card, member, amount, date, category, remark) "
                    "VALUES (:id, :card, :member, :amount, :date, :category, :remark)"
                ),
                {
                    "id": t.get("id") or str(uuid.uuid4()),
                    "card": t["card"], "member": t["user"], "amount": t["amount"],
                    "date": t["date"], "category": t["category"], "remark": t.get("remark"),
                },
            )
        s.commit()
