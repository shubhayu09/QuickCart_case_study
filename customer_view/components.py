"""Small HTML building blocks for the customer view (styled by customer_view/styles.css)."""
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

from ui.components import pill
from ui.formatters import inr

_CSS = Path(__file__).with_name("styles.css")

# delivery status -> (customer-friendly label, text colour, tint)
STATUS_PILL = {
    "DELIVERED": ("Delivered", "#128a5f", "#E8F6EF"),
    "DELAYED_IN_TRANSIT": ("Delayed", "#b07800", "#FDF4E1"),
    "LOST_IN_TRANSIT": ("Lost in transit", "#BD1E59", "#FFF1F3"),
    "RETURNED_TO_SELLER": ("Returned to seller", "#6250d6", "#EFEDFB"),
    "CANCELLED_BEFORE_SHIP": ("Cancelled", "#52514e", "#F0F0EE"),
}

# ticket resolution status -> what the customer sees
TICKET_TEXT = {
    "Open - Awaiting Courier Update": "Support ticket open",
    "Resolved - Full Refund Issued": "Refund issued",
    "Resolved - Replacement Sent": "Replacement sent",
    "Resolved - Apology Voucher Issued": "Voucher issued",
    "Resolved - No Refund (Explanation)": "Ticket resolved",
}


def inject_css():
    st.markdown(f"<style>{_CSS.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def _html(markup: str):
    st.markdown(markup, unsafe_allow_html=True)


def profile_header(customer_id: str, city: str, since: pd.Timestamp):
    _html(f'<div class="cv-profile"><div class="cv-avatar">{escape(customer_id[-2:])}</div><div>'
          f'<div class="cv-name">Welcome back, {escape(customer_id)}</div>'
          f'<div class="cv-meta">{escape(city)} · customer since {since:%b %Y}</div></div></div>')


def order_card(order: pd.Series, ticket: pd.Series | None, active: bool):
    label, fg, bg = STATUS_PILL.get(order["delivery_status"], (order["delivery_status"], "#52514e", "#F0F0EE"))
    ticket_line = ""
    if ticket is not None:
        ticket_line = (f'<div class="ticket">{escape(ticket["ticket_id"])} · '
                       f'{escape(TICKET_TEXT.get(ticket["resolution_status"], "Ticket"))}</div>')
    _html(f'<div class="cv-order{" active" if active else ""}"><div class="top">'
          f'<span class="id">{escape(order["order_id"])}</span>{pill(label, fg, bg)}</div>'
          f'<div class="meta">{escape(order["product_category"])} · {inr(order["order_amount"])} · '
          f'ordered {order["order_date"]:%d %b %Y}</div>{ticket_line}</div>')


def hint(text: str):
    _html(f'<div class="cv-demo-hint">{escape(text)}</div>')
