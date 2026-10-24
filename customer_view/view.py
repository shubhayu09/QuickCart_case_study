"""
Customer view: sign in with a customer ID, see a short profile and your orders, and chat with the help assistant.

Called from dashboard.py when the "Customer view" switch is selected. Only this customer's rows are ever shown.
"""
import os

import pandas as pd
import streamlit as st

from chatbot import bot, policy
from chatbot.data import CustomerData
from chatbot.intents import INTENTS
from customer_view import components as cv
from ui import components as ui
from ui.formatters import inr, num

QUICK_QUESTIONS = {chip: label for label, (_, chip) in INTENTS.items() if chip}


@st.cache_resource
def _knowledge_base():
    return policy.load_kb()


def _api_key() -> str | None:
    try:
        return st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
    except Exception:          # no secrets.toml -> keyword matching only
        return os.environ.get("GROQ_API_KEY")


# ---- session helpers -------------------------------------------------------------------------
def _sign_in(customer_id: str):
    st.session_state["cv_customer"] = customer_id
    st.session_state["cv_chat"] = bot.new_state(customer_id)
    st.session_state.pop("cv_login_error", None)


def _sign_out():
    for k in ("cv_customer", "cv_chat"):
        st.session_state.pop(k, None)


def _try_sign_in(data: CustomerData):
    cid = st.session_state.get("cv_login_id", "").strip().upper()
    if cid.isdigit():
        cid = f"CUST-{cid}"
    if data.exists(cid):
        _sign_in(cid)
    else:
        st.session_state["cv_login_error"] = f"No customer found with ID {cid or '…'}. Check the ID or try a demo customer."


def _on_quick_question(data, kb):
    chip = st.session_state.get("cv_quick")
    if chip:
        bot.handle_message(st.session_state["cv_chat"], data, kb, chip, _api_key())
    st.session_state["cv_quick"] = None


def _on_action(data, kb, action: dict):
    bot.handle_action(st.session_state["cv_chat"], data, kb, action)


def _on_get_help(data, kb, order_id: str):
    chat = st.session_state["cv_chat"]
    chat["messages"].append({"role": "user", "text": f"Help with {order_id}", "actions": [], "order_id": None})
    bot.select_order(chat, data, order_id, kb)


# ---- screens -----------------------------------------------------------------------------------
def _login_screen(data: CustomerData):
    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        with ui.card("Sign in to your account", "Enter your customer ID to see your orders and get help"):
            st.text_input("Customer ID", placeholder="CUST-10055", key="cv_login_id", label_visibility="collapsed",
                          on_change=_try_sign_in, args=(data,))
            st.button("Continue", on_click=_try_sign_in, args=(data,), type="primary")
            if err := st.session_state.get("cv_login_error"):
                st.error(err)
    with c2:
        with ui.card("Try a demo customer", "Each one shows a different support situation"):
            for cid, label in data.demo_customers():
                st.button(f"{label} · {cid}", key=f"demo-{cid}", on_click=_sign_in, args=(cid,), width="stretch")


def _chat_panel(data: CustomerData, kb):
    chat = st.session_state["cv_chat"]
    if not chat["messages"]:
        bot.greet(chat, data)

    with ui.card("QuickCart assistant", "Ask about tracking, damaged items, refunds, payments, returns or cancellations"):
        box = st.container(height=470, border=False)
        with box:
            for i, m in enumerate(chat["messages"]):
                with st.chat_message(m["role"], avatar=":material/support_agent:" if m["role"] == "assistant"
                                     else ":material/person:"):
                    if m["role"] == "user":   # invisible marker so styles.css can style customer bubbles
                        st.markdown('<span class="cv-user"></span>', unsafe_allow_html=True)
                    st.markdown(m["text"].replace("\n", "  \n"))
            last = chat["messages"][-1]
            if last["role"] == "assistant" and last["actions"]:
                cols = st.columns(len(last["actions"]))
                for j, (col, a) in enumerate(zip(cols, last["actions"])):
                    payload = {"kind": a.kind, "label": a.label, "amount": a.amount, "order_id": last["order_id"]}
                    col.button(a.label, key=f"act-{len(chat['messages'])}-{j}", on_click=_on_action,
                               args=(data, kb, payload), width="stretch")

        st.pills("Quick questions", list(QUICK_QUESTIONS), key="cv_quick", label_visibility="collapsed",
                 on_change=_on_quick_question, args=(data, kb))
        if prompt := st.chat_input("Type your question…", key="cv_input"):
            bot.handle_message(chat, data, kb, prompt, _api_key())
            st.rerun()


def _account_screen(data: CustomerData, kb):
    cid = st.session_state["cv_customer"]
    prof = data.profile(cid)
    orders = data.orders_of(cid)
    chat = st.session_state["cv_chat"]

    head, out = st.columns([5, 1])
    with head:
        cv.profile_header(cid, prof["city"], prof["since"])
    with out:
        st.button("Sign out", on_click=_sign_out, width="stretch")
    st.write("")
    ui.kpi_row([
        ui.kpi("Orders", num(prof["orders"]), icon_name="inventory_2", accent="blue"),
        ui.kpi("Total spent", inr(prof["spent"]), "excludes cancelled orders", "payments", "green"),
        ui.kpi("Open tickets", num(prof["open_tickets"]), icon_name="support_agent", accent="amber"),
        ui.kpi("Customer since", f"{prof['since']:%b %Y}", icon_name="calendar_month", accent="violet"),
    ])

    left, right = st.columns([5, 7], gap="medium")
    with left:
        with ui.card("Your orders", "Pick an order to get help with it"):
            for _, o in orders.iterrows():
                cv.order_card(o, data.ticket_for(o["order_id"]), active=o["order_id"] == chat["order_id"])
                st.button("Get help with this order", key=f"help-{o['order_id']}", on_click=_on_get_help,
                          args=(data, kb, o["order_id"]), width="stretch")
    with right:
        _chat_panel(data, kb)


def render(orders: pd.DataFrame, tickets: pd.DataFrame):
    cv.inject_css()
    data = CustomerData(orders, tickets)
    kb = _knowledge_base()
    signed_in = "cv_customer" in st.session_state
    ui.hero("How can we help?",
            "Track your orders, report a problem and get refunds or replacements instantly.",
            eyebrow="QuickCart · Help centre",
            chips=["Instant answers", "Refunds in 5–7 days", "24×7"] if not signed_in else [st.session_state["cv_customer"]])
    if signed_in:
        _account_screen(data, kb)
    else:
        _login_screen(data)
