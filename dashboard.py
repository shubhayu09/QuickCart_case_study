"""
QuickCart Case Study - Part 1 dashboard.

Reads the outputs of clean_data.py and answers questions A-D from the brief, plus extra insights,
a data explorer and the data cleaning log. All styling lives in the ui/ package:

  ui/theme.py       colours, fonts, Plotly template
  ui/styles.css     page styles
  ui/components.py  hero, KPI cards, cards, callouts, sidebar pieces
  ui/charts.py      chart builders
  ui/formatters.py  ₹ / % / hours formatting

Run:  .venv/Scripts/streamlit run dashboard.py
"""
from pathlib import Path

import pandas as pd
import streamlit as st

from ui import charts as ch
from ui import components as ui
from ui.formatters import hours, inr, num, pct
from ui.theme import (ACCENTS, BRAND, CATEGORIES, CATEGORY_COLOR, COURIER_COLOR, COURIERS, HIGHLIGHT, MUTED_MARK,
                      RULE_COLOR, RULE_SHORT, RULES, SERIES, STATUS_COLOR, STATUS_LABEL, STATUSES,
                      register_plotly_template)

ROOT = Path(__file__).parent
CLEAN = ROOT / "data" / "clean"
LOGS = ROOT / "logs"

st.set_page_config(page_title="QuickCart Support Analytics", page_icon="📦", layout="wide",
                   initial_sidebar_state="expanded")
register_plotly_template()
ui.inject_css()

# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------
DATA_FILES = [CLEAN / "orders_clean.csv", CLEAN / "support_tickets_clean.csv", LOGS / "cleaning_log.csv",
              CLEAN / "removed_rows.csv"]


@st.cache_data
def load(mtimes):
    """mtimes is only a cache key: re-running clean_data.py invalidates the cache."""
    o = pd.read_csv(CLEAN / "orders_clean.csv", parse_dates=["order_date"])
    t = pd.read_csv(CLEAN / "support_tickets_clean.csv",
                    parse_dates=["ticket_created_at", "ticket_resolved_at", "order_date"])
    log = pd.read_csv(LOGS / "cleaning_log.csv")
    removed = pd.read_csv(CLEAN / "removed_rows.csv", usecols=["dataset", "removal_reason"])
    return o, t, log, removed


if not all(p.exists() for p in DATA_FILES):
    st.error("Clean data not found. Run `python clean_data.py` first.")
    st.stop()

orders_all, tickets_all, cleaning_log, removed_rows = load(tuple(p.stat().st_mtime for p in DATA_FILES))

# --------------------------------------------------------------------------------------
# Admin / Customer view switch (customer view lives in customer_view/ and chatbot/)
# --------------------------------------------------------------------------------------
_, switch_col = st.columns([3, 1])
with switch_col:
    app_view = st.segmented_control("View", ["Admin View", "Customer View"], default="Admin View", key="app_view",
                                    label_visibility="collapsed", width="stretch") or "Admin View"
if app_view == "Customer View":
    from customer_view.view import render as render_customer_view
    render_customer_view(orders_all, tickets_all)
    st.stop()

# --------------------------------------------------------------------------------------
# Sidebar: brand, smart filters, metric guide
# --------------------------------------------------------------------------------------
FILTERS = {
    "f_courier": COURIERS,
    "f_cat": CATEGORIES,
    "f_city": sorted(orders_all["customer_city"].unique()),
    "f_pay": sorted(orders_all["payment_method"].unique()),
    "f_month": sorted(orders_all["order_month"].unique()),
}
# Streamlit drops a widget's value on runs where the widget isn't drawn (e.g. while the customer view is open),
# so each filter's selection is also kept under a "saved_" key and restored before the widgets are drawn.
for k, v in FILTERS.items():
    st.session_state.setdefault(f"saved_{k}", v)
    st.session_state[k] = st.session_state[f"saved_{k}"]


def save_filter(key):
    st.session_state[f"saved_{key}"] = st.session_state[key]


def reset_filters():
    for key, options in FILTERS.items():
        st.session_state[key] = options
        st.session_state[f"saved_{key}"] = options


with st.sidebar:
    ui.sidebar_brand("QuickCart", "Support & refund analytics")
    ui.sidebar_heading("Filters")
    st.multiselect("Courier Partner", FILTERS["f_courier"], key="f_courier", on_change=save_filter, args=("f_courier",))
    st.multiselect("Product Category", FILTERS["f_cat"], key="f_cat", on_change=save_filter, args=("f_cat",))
    st.multiselect("City", FILTERS["f_city"], key="f_city", on_change=save_filter, args=("f_city",))
    st.multiselect("Payment Method", FILTERS["f_pay"], key="f_pay", on_change=save_filter, args=("f_pay",))
    st.multiselect("Order Month", FILTERS["f_month"], key="f_month", on_change=save_filter, args=("f_month",))
    st.button("↺  Reset All Filters", on_click=reset_filters, width="stretch")
    st.caption("Filters apply to every tab.")
    ui.sidebar_heading("Metric Definitions")
    with st.expander("How Each Metric Is Defined"):
        ui.metric_guide([
            ("Total Order Value", "Value of all orders placed, excluding shipping fees."),
            ("Lost & Delayed Rate", "Share of a courier's orders that were lost or delayed in transit."),
            ("Resolution Time", "Hours from a ticket being raised to it being resolved."),
            ("CSAT", "Average customer satisfaction rating, out of 5."),
            ("Policy Leakage", "Refunds paid above what QuickCart's refund policy allows."),
        ])


def apply_filters(df):
    s = st.session_state
    return df[df["courier_partner"].isin(s.f_courier) & df["product_category"].isin(s.f_cat)
              & df["customer_city"].isin(s.f_city) & df["payment_method"].isin(s.f_pay)
              & df["order_month"].isin(s.f_month)]


orders = apply_filters(orders_all)
tickets = apply_filters(tickets_all)
filtered = len(orders) != len(orders_all)
if orders.empty:
    st.warning("No orders match the current filters.")
    st.stop()

resolved = tickets[~tickets["is_open"] & tickets["resolution_hours"].notna()]
violations = tickets[tickets["is_policy_violation"]]

# --------------------------------------------------------------------------------------
# Hero + headline KPIs
# --------------------------------------------------------------------------------------
ui.hero(
    "Delivery, Support & Refund Performance",
    "Delivery reliability, customer support performance and refund control across QuickCart.",
    eyebrow="QuickCart · Leadership Dashboard",
    chips=[f"{orders_all['order_date'].min():%d %b} – {orders_all['order_date'].max():%d %b %Y}",
           f"{len(orders_all):,} Orders · {len(tickets_all):,} Tickets"]
          + (["Filters Active"] if filtered else []),
)

ui.kpi_row([
    ui.kpi("Total Orders", num(len(orders)), "Orders Placed", "inventory_2", "blue"),
    ui.kpi("Support Tickets", num(len(tickets)), "Tickets Raised", "confirmation_number", "violet"),
    ui.kpi("Total Order Value", inr(orders["order_amount"].sum()), "Gross Merchandise Value", "payments", "green"),
    ui.kpi("Total Refunds", inr(tickets["refund_amount"].sum()), "Refunds & Vouchers Paid", "currency_exchange", "amber"),
    ui.kpi("Avg Resolution Time", hours(resolved["resolution_hours"].mean()), "Resolved Tickets", "schedule", "slate"),
    ui.kpi("Policy Leakage", inr(violations["excess_refund"].sum()), f"{len(violations)} Tickets Over-Refunded",
           "warning", "coral", alert=True),
])

tabs = st.tabs(["Overview", "Courier Performance", "Support & CSAT", "Refund Leakage", "Insights",
                "Data Explorer", "Data Quality"])

# ======================================================================================
# A. OVERVIEW
# ======================================================================================
with tabs[0]:
    ui.section("", "Business Overview", "Order volume, order value and refunds at a glance.")
    gmv = orders["order_amount"].sum()
    refunds = tickets["refund_amount"].sum()
    leak = violations["excess_refund"].sum()
    ui.kpi_row(cols=4, cards=[
        ui.kpi("Order Value Incl. Shipping", inr(gmv + orders["shipping_fee"].sum()), icon_name="local_shipping", accent="green"),
        ui.kpi("Order Value Excl. Cancelled", inr(orders.loc[orders["delivery_status"] != "CANCELLED_BEFORE_SHIP", "order_amount"].sum()),
               icon_name="remove_shopping_cart", accent="green"),
        ui.kpi("Refund Rate", pct(refunds / gmv), "Of Total Order Value", "trending_down", "coral"),
        ui.kpi("Ticket Rate", pct(tickets["order_id"].nunique() / len(orders)), "Orders Needing Support", "confirmation_number", "violet"),
        ui.kpi("Avg Order Value", f"₹{orders['order_amount'].mean():,.0f}", icon_name="receipt_long", accent="blue"),
        ui.kpi("Active Customers", num(orders["customer_id"].nunique()), icon_name="group", accent="blue"),
        ui.kpi("Open Tickets", num(tickets["is_open"].sum()), icon_name="inbox", accent="amber"),
        ui.kpi("Total Refunds Issued", num((tickets["refund_amount"] > 0).sum()), "Tickets Refunded or Compensated",
               "currency_exchange", "amber"),
    ])

    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        ui.chart_card(ch.treemap(orders, ["product_category", "customer_city"], "order_amount", CATEGORY_COLOR, height=360),
                      "Order Value by Category and City", "Click a tile to drill in; click the bar above it to go back")
    with c2:
        d = orders["delivery_status"].value_counts().reindex(STATUSES).dropna()
        ui.chart_card(ch.donut([STATUS_LABEL[s] for s in d.index], d.values, [STATUS_COLOR[s] for s in d.index], "Orders",
                               num(d.sum()), height=360), "Delivery Outcomes", "Share of orders by final delivery status")

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        ui.chart_card(ch.waterfall([("Order Value", gmv, "total"),
                                    ("Policy-Compliant Refunds", -(refunds - leak), "delta", MUTED_MARK),
                                    ("Policy Leakage", -leak, "delta", HIGHLIGHT),
                                    ("Retained Revenue", gmv - refunds, "total")], height=340),
                      "Order Value to Retained Revenue", "Refunds consume a large share of order value; coral is leakage")
    with c2:
        d = tickets.groupby("issue_category")["refund_amount"].sum().sort_values(ascending=False).reset_index()
        ui.chart_card(ch.hbar(d, "issue_category", "refund_amount", text=[inr(v) for v in d["refund_amount"]],
                              hover="%{y}<br>Refunds ₹%{x:,.0f}<extra></extra>", height=340),
                      "Refunds by Issue Type", "Which complaints cost the most")

    with ui.card("Customer Ticket Journey", "Delivery status → customer complaint → support resolution. "
                                            "Hover a band to see ticket counts"):
        ui.chart(ch.sankey(tickets.assign(delivery_status=tickets["delivery_status"].map(STATUS_LABEL)),
                           ["delivery_status", "issue_category", "resolution_status"],
                           stage_colors=[{STATUS_LABEL[k]: v for k, v in STATUS_COLOR.items()}, {}, {}], height=460))

    m = orders.groupby("order_month")["order_amount"].sum()
    r = tickets.groupby("order_month")["refund_amount"].sum().reindex(m.index).fillna(0)
    month_labels = pd.to_datetime(m.index).strftime("%b %Y").tolist()
    ui.chart_card(ch.grouped_columns(month_labels, {"Order Value": m.values, "Refunds": r.values}, height=320),
                  "Order Value vs Refunds by Month", "March is a partial month (data to 25 Mar 2026)")

# ======================================================================================
# B. COURIERS
# ======================================================================================
with tabs[1]:
    ui.section("", "Courier Performance", "Delivery reliability and support resolution speed by courier partner.")
    g = orders.groupby("courier_partner").agg(
        orders=("order_id", "count"),
        lost=("delivery_status", lambda s: (s == "LOST_IN_TRANSIT").sum()),
        delayed=("delivery_status", lambda s: (s == "DELAYED_IN_TRANSIT").sum()))
    g["lost_rate"] = g["lost"] / g["orders"]
    g["delayed_rate"] = g["delayed"] / g["orders"]
    g["lost_delayed_rate"] = g["lost_rate"] + g["delayed_rate"]
    tg = tickets.groupby("courier_partner").agg(
        tickets=("ticket_id", "count"), open_tickets=("is_open", "sum"),
        csat=("csat_score", "mean"), refunds=("refund_amount", "sum"), leak=("excess_refund", "sum"))
    rg = resolved.groupby("courier_partner")["resolution_hours"].agg(avg_res="mean", median_res="median",
                                                                    breach_24h=lambda s: (s > 24).mean())
    cour = g.join(tg).join(rg).reset_index()

    worst_rate = cour.loc[cour["lost_delayed_rate"].idxmax()]
    worst_res = cour.loc[cour["avg_res"].idxmax()]

    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        ui.chart_card(ch.bubble_quadrant(
            cour, "lost_delayed_rate", "avg_res", "orders", "courier_partner", highlight=worst_rate["courier_partner"],
            x_title="Lost & Delayed Rate", y_title="Avg Resolution Time (h)", height=380,
            hover="<b>%{text}</b><br>Lost + delayed %{x:.1%}<br>Avg resolution %{y:.1f} h<br>%{customdata[0]:,} orders<extra></extra>"),
            "Delivery Failures vs Resolution Time", "Bubble size = order volume; lines mark the courier average")
    with c2:
        d = cour.sort_values("lost_delayed_rate", ascending=False)
        ui.chart_card(ch.stacked_hbar(d, "courier_partner", [("lost_rate", "Lost in Transit"),
                                                             ("delayed_rate", "Delayed in Transit")],
                                      total_col="lost_delayed_rate", height=380),
                      "Lost & Delayed Rate", "Share of each courier's orders")

    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        hm = orders.pivot_table(index="courier_partner", columns="customer_city", values="is_lost_or_delayed",
                                aggfunc="mean").reindex([c for c in COURIERS if c in orders["courier_partner"].unique()])
        ui.chart_card(ch.heatmap(hm, hover="%{y} · %{x}<br>Lost + delayed %{z:.1%}<extra></extra>", height=300, zfmt=".0%"),
                      "Lost & Delayed Rate by Courier and City", "Darker cells mean more failed deliveries")
    with c2:
        d = cour.sort_values("avg_res", ascending=False)
        ui.chart_card(ch.hbar(d, "courier_partner", "avg_res", text=[hours(v) for v in d["avg_res"]],
                              highlight=worst_res["courier_partner"], height=300,
                              hover="%{y}<br>Avg resolution %{x:.1f} h<extra></extra>"),
                      "Avg Resolution Time by Courier", "Resolved tickets, in hours")

    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        mix = orders.groupby(["courier_partner", "delivery_status"]).size().unstack(fill_value=0)
        mix = mix.div(mix.sum(axis=1), axis=0)
        ui.chart_card(ch.stacked_share(mix.rename(columns=STATUS_LABEL), [STATUS_LABEL[s] for s in STATUSES],
                                       {STATUS_LABEL[k]: v for k, v in STATUS_COLOR.items()}, height=340),
                      "Delivery Status Mix by Courier", "Share of each courier's orders")
    with c2:
        d = cour.sort_values("breach_24h", ascending=False)
        fig = ch.hbar(d, "courier_partner", "breach_24h", text=[pct(v, 0) for v in d["breach_24h"]],
                      highlight=worst_res["courier_partner"], height=340,
                      hover="%{y}<br>%{x:.1%} of resolved tickets > 24 h<extra></extra>")
        ui.chart_card(fig, "Tickets Resolved After 24 Hours", "Each one qualifies for a ₹100 late voucher")

    with ui.card("Courier Deep-Dive", "Select a courier to see its numbers and complaint mix"):
        focus = st.pills("Courier", list(cour["courier_partner"]), default=worst_rate["courier_partner"],
                         key="focus_courier", label_visibility="collapsed") or worst_rate["courier_partner"]
        row = cour.set_index("courier_partner").loc[focus]
        ui.kpi_row([
            ui.kpi("Orders", num(row["orders"]), f"{row['orders'] / cour['orders'].sum():.0%} of Total Orders", "inventory_2", "blue"),
            ui.kpi("Lost & Delayed", pct(row["lost_delayed_rate"]), f"{num(row['lost'] + row['delayed'])} Orders", "report", "coral"),
            ui.kpi("Avg Resolution Time", hours(row["avg_res"]), f"Median {hours(row['median_res'])}", "schedule", "slate"),
            ui.kpi("Avg CSAT", f"{row['csat']:.2f}", f"{num(row['open_tickets'])} Open Tickets", "star", "amber"),
            ui.kpi("Refunds", inr(row["refunds"]), f"Policy Leakage {inr(row['leak'])}", "currency_exchange", "violet"),
        ])
        d = tickets[tickets["courier_partner"] == focus]["issue_category"].value_counts().reset_index()
        d.columns = ["issue", "tickets"]
        ui.chart(ch.hbar(d, "issue", "tickets", text=[num(v) for v in d["tickets"]], color=COURIER_COLOR.get(focus),
                         hover="%{y}<br>%{x:,} tickets<extra></extra>", height=250))

    with ui.card("Courier Scorecard", "All courier metrics side by side; click a column header to sort"):
        tbl = cour.sort_values("lost_delayed_rate", ascending=False)[
            ["courier_partner", "orders", "lost", "delayed", "lost_delayed_rate", "tickets", "avg_res", "median_res",
             "breach_24h", "open_tickets", "csat", "refunds", "leak"]]
        st.dataframe(tbl, hide_index=True, width="stretch", column_config={
            "courier_partner": "Courier", "orders": "Orders", "lost": "Lost", "delayed": "Delayed",
            "lost_delayed_rate": st.column_config.ProgressColumn("Lost & Delayed", format="percent", min_value=0,
                                                                 max_value=float(tbl["lost_delayed_rate"].max())),
            "tickets": "Tickets", "avg_res": st.column_config.NumberColumn("Avg Resolution (h)", format="%.1f"),
            "median_res": st.column_config.NumberColumn("Median Resolution (h)", format="%.1f"),
            "breach_24h": st.column_config.ProgressColumn("Resolved After 24h", format="percent", min_value=0, max_value=1),
            "open_tickets": "Open Tickets", "csat": st.column_config.NumberColumn("Avg CSAT", format="%.2f"),
            "refunds": st.column_config.NumberColumn("Refunds (₹)", format="%,.0f"),
            "leak": st.column_config.NumberColumn("Policy Leakage (₹)", format="%,.0f")})

# ======================================================================================
# C. SLA & CSAT
# ======================================================================================
with tabs[2]:
    ui.section("", "Customer Support & Satisfaction", "Resolution speed, open backlog and customer satisfaction.")
    rated = tickets["csat_score"].dropna()
    ui.kpi_row([
        ui.kpi("Avg Resolution Time", hours(resolved["resolution_hours"].mean()), "Resolved Tickets", "schedule", "slate"),
        ui.kpi("Median Resolution Time", hours(resolved["resolution_hours"].median()), "Typical Ticket", "pin_drop", "blue"),
        ui.kpi("Resolved After 24 Hours", pct((resolved["resolution_hours"] > 24).mean()), "Above 24h Target", "alarm", "coral"),
        ui.kpi("Open Tickets", num(tickets["is_open"].sum()), "Awaiting Courier Update", "inbox", "amber"),
        ui.kpi("Avg CSAT (out of 5)", f"{rated.mean():.2f}", f"{len(rated):,} Ratings · {len(rated) / len(tickets):.0%} Response Rate", "star", "violet"),
    ])

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        ui.chart_card(ch.histogram(resolved["resolution_hours"], threshold=24, threshold_label="24h Target",
                                   x_title="Hours to Resolve", y_title="Tickets", height=330),
                      "Ticket Resolution Time", "Tickets in the shaded zone took longer than 24 hours")
    with c2:
        labels = ["0–12 h", "12–24 h", "24–48 h", "48 h +"]
        rr = resolved.assign(bucket=pd.cut(resolved["resolution_hours"], [0, 12, 24, 48, 1e9], labels=labels, right=False))
        d = rr.groupby("bucket", observed=False).agg(csat=("csat_score", "mean"), n=("csat_score", "count")).reset_index()
        ui.chart_card(ch.ordinal_columns(d["bucket"].astype(str), d["csat"], d["n"], height=330, y_title="Avg CSAT"),
                      "CSAT by Resolution Time", "Slower resolution means lower satisfaction")

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        lk = tickets.dropna(subset=["csat_score"]).groupby("channel")["csat_score"].value_counts(normalize=True).unstack(fill_value=0)
        lk.columns = lk.columns.astype(int)
        lk = lk.loc[tickets.groupby("channel")["csat_score"].mean().sort_values().index]
        ui.chart_card(ch.likert(lk, height=320), "CSAT Rating Mix by Channel", "Red = unhappy (1–2), blue = happy (4–5)")
    with c2:
        d = resolved.groupby("channel")["resolution_hours"].mean().sort_values(ascending=False).reset_index()
        ui.chart_card(ch.hbar(d, "channel", "resolution_hours", text=[hours(v) for v in d["resolution_hours"]],
                              hover="%{y}<br>%{x:.1f} h<extra></extra>", height=320),
                      "Avg Resolution Time by Channel", "Resolved tickets, in hours")

    c1, c2 = st.columns([3, 2], gap="medium")
    with c1:
        op = tickets[tickets["is_open"]].pivot_table(index="issue_category", columns="courier_partner",
                                                     values="ticket_id", aggfunc="count").fillna(0)
        op.columns = [c.split("_")[0] for c in op.columns]
        ui.chart_card(ch.heatmap(op, text_fmt="{:.0f}", hover="%{y} · %{x}<br>%{z:.0f} open tickets<extra></extra>",
                                 height=320, zfmt=",.0f"),
                      "Open Ticket Backlog", "Open tickets by issue type and courier")
    with c2:
        d = rated.value_counts().sort_index()
        ui.chart_card(ch.column([str(int(i)) for i in d.index], d.values, text=[num(v) for v in d.values],
                                colors=[SERIES[7], SERIES[7], MUTED_MARK, SERIES[0], SERIES[0]],
                                hover="CSAT %{x}<br>%{y:,} tickets<extra></extra>", height=300, y_title="Tickets"),
                      "CSAT Rating Distribution", "Number of tickets by rating")

# ======================================================================================
# D. REFUND LEAKS
# ======================================================================================
with tabs[3]:
    ui.section("", "Refund Policy Leakage", "Refunds paid above what QuickCart's refund policy allows.")
    leak_total = violations["excess_refund"].sum()
    ui.kpi_row([
        ui.kpi("Tickets Over-Refunded", num(len(violations)), icon_name="flag", accent="coral", alert=True),
        ui.kpi("Total Leakage", inr(leak_total), icon_name="money_off", accent="coral", alert=True),
        ui.kpi("Leakage (Exact)", f"₹{leak_total:,.0f}", icon_name="calculate", accent="slate"),
        ui.kpi("Share of Total Refunds", pct(leak_total / max(tickets["refund_amount"].sum(), 1)), icon_name="pie_chart", accent="amber"),
    ])

    with st.expander("How Leakage Is Measured"):
        st.markdown("""
| Policy Rule | What Counts as Leakage | Amount Counted |
|---|---|---|
| **R1a** Late support bonus | ₹100 voucher added although the ticket was resolved within 24 hours | The extra ₹100 |
| **R1b** Delayed orders still on the way | Refund above the ₹100 apology voucher | Amount above ₹100 |
| **R2** Damaged item: replacement **or** refund | Refund paid on top of a replacement | Full refund |
| **R3** Unpaid COD order cancelled before shipping | Any refund paid | Full refund (customer never paid) |
| **R4** Refund limit | Refund above order value + ₹100 | Amount above the limit |

A ticket breaking several rules is counted once, at its largest over-payment.
""")

    if violations.empty:
        st.info("No policy leakage for the current filters.")
    else:
        by_rule = (violations.groupby("primary_violation").agg(tickets=("ticket_id", "count"), lost=("excess_refund", "sum"))
                   .reindex(RULES).dropna().query("tickets > 0").sort_values("lost", ascending=False))
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            steps = [(f"<b>{RULE_SHORT[r].split(' · ')[0]}</b> · {RULE_SHORT[r].split(' · ')[1]}<br>{int(v.tickets)} tickets",
                      v.lost, "delta", RULE_COLOR[r]) for r, v in by_rule.iterrows()]
            steps.append(("<b>Total Leakage</b>", leak_total, "total", HIGHLIGHT))
            ui.chart_card(ch.waterfall(steps, height=380, wrap_labels=True), "Leakage by Policy Rule", "₹ paid above policy, by rule")
        with c2:
            tm = violations.assign(rule=violations["primary_violation"].map(RULE_SHORT))
            ui.chart_card(ch.treemap(tm, ["rule", "courier_partner"], "excess_refund",
                                     {RULE_SHORT[r]: c for r, c in RULE_COLOR.items()}, height=380),
                          "Leakage by Rule and Courier", "Click a rule to see which couriers it came from")

        with ui.card("Leakage Breakdown", "Choose a dimension"):
            dim_labels = {"courier_partner": "Courier", "product_category": "Category", "channel": "Channel",
                          "issue_category": "Issue", "customer_city": "City"}
            dim = st.segmented_control("Dimension", list(dim_labels), default="courier_partner",
                                       format_func=dim_labels.get, key="leak_dim",
                                       label_visibility="collapsed") or "courier_partner"
            d = violations.groupby(dim)["excess_refund"].sum().sort_values(ascending=False).reset_index()
            ui.chart(ch.hbar(d, dim, "excess_refund", text=[inr(v) for v in d["excess_refund"]], color=BRAND,
                             hover="%{y}<br>₹%{x:,.0f}<extra></extra>"))

        with ui.card("Over-Refunded Tickets", "Filter by rule, sort any column, or download as CSV"):
            present = [r for r in RULES if r in set(violations["primary_violation"])]
            chosen = st.pills("Rule", present, selection_mode="multi", default=present, format_func=RULE_SHORT.get,
                              key="leak_rules", label_visibility="collapsed") or present
            cols = ["ticket_id", "order_id", "primary_violation", "issue_category", "resolution_status", "delivery_status",
                    "payment_method", "order_amount", "refund_amount", "max_allowed_refund", "excess_refund",
                    "resolution_hours", "courier_partner", "channel"]
            view = (violations[violations["primary_violation"].isin(chosen)][cols].sort_values("excess_refund", ascending=False)
                    .assign(primary_violation=lambda v: v["primary_violation"].map(RULE_SHORT)))
            st.dataframe(view, hide_index=True, width="stretch", height=380, column_config={
                "ticket_id": "Ticket", "order_id": "Order", "primary_violation": "Policy Rule",
                "order_amount": st.column_config.NumberColumn("Order Value (₹)", format="%,.0f"),
                "refund_amount": st.column_config.NumberColumn("Refunded (₹)", format="%,.0f"),
                "max_allowed_refund": st.column_config.NumberColumn("Allowed (₹)", format="%,.0f"),
                "excess_refund": st.column_config.ProgressColumn("Leakage (₹)", format="%,.0f", min_value=0,
                                                                 max_value=float(violations["excess_refund"].max())),
                "resolution_hours": st.column_config.NumberColumn("Resolution (h)", format="%.1f")})
            st.download_button("⬇  Download CSV", view.to_csv(index=False), "refund_violations.csv", "text/csv")

# ======================================================================================
# INSIGHTS
# ======================================================================================
with tabs[4]:
    ui.section("", "Key Insights", "Patterns that need leadership attention.")
    delivered_refunds = tickets[(tickets["delivery_status"] == "DELIVERED")
                                & (tickets["resolution_status"] == "Resolved - Full Refund Issued")]
    vouchers = tickets[tickets["resolution_status"] == "Resolved - Apology Voucher Issued"]
    off_sop_vouchers = vouchers[vouchers["refund_amount"] != 100]
    late = resolved[resolved["resolution_hours"] > 24]
    slow = resolved[resolved["resolution_hours"] > 48]
    fast_csat = resolved.loc[resolved["resolution_hours"] <= 24, "csat_score"].mean()

    i1, i2, i3, i4 = st.columns(4, gap="medium")
    with i1:
        ui.insight("Refunds on Delivered Orders", num(len(delivered_refunds)),
                   f"Full refunds worth <b>{inr(delivered_refunds['refund_amount'].sum())}</b> on orders marked as delivered.", "coral")
    with i2:
        ui.insight("Off-Policy Vouchers", num(len(off_sop_vouchers)),
                   f"of {num(len(vouchers))} apology vouchers were not the ₹100 the policy specifies.", "amber")
    with i3:
        ui.insight("Late-Voucher Exposure", inr(len(late) * 100),
                   f"<b>{num(len(late))}</b> resolved tickets took > 24 h, so each qualifies for a ₹100 voucher.", "violet")
    with i4:
        ui.insight("Slow Tickets Hurt CSAT", f"{slow['csat_score'].mean():.2f}",
                   f"avg CSAT for the <b>{num(len(slow))}</b> tickets taking > 48 h, vs <b>{fast_csat:.2f}</b> within 24 h.", "blue")
    st.write("")

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        d = (delivered_refunds.groupby("issue_category")["refund_amount"].agg(["sum", "count"])
             .sort_values("sum", ascending=False).reset_index())
        ui.chart_card(ch.hbar(d, "issue_category", "sum", text=[f"{inr(s)} · {c:,}" for s, c in zip(d["sum"], d["count"])],
                              hover="%{y}<br>₹%{x:,.0f}<extra></extra>", height=300),
                      "Full Refunds on Delivered Orders", "Refund value and ticket count by issue type")
    with c2:
        d = vouchers["refund_amount"].value_counts().sort_index()
        ui.chart_card(ch.column([f"₹{a:,.0f}" for a in d.index], d.values, text=[num(v) for v in d.values],
                                colors=[SERIES[0] if a == 100 else BRAND for a in d.index],
                                hover="Voucher %{x}<br>%{y:,} tickets<extra></extra>", height=300, y_title="Tickets"),
                      "Apology Voucher Amounts", "Policy is ₹100; coral bars match shipping fees instead")

    c1, c2 = st.columns(2, gap="medium")
    with c1:
        d = tickets.groupby("product_category").agg(tickets=("ticket_id", "count")).join(
            orders.groupby("product_category").agg(orders=("order_id", "count")))
        d["rate"] = d["tickets"] / d["orders"]
        d = d.reindex(CATEGORIES).dropna().reset_index().sort_values("rate", ascending=False)
        ui.chart_card(ch.hbar(d, "product_category", "rate", text=[pct(v, 0) for v in d["rate"]],
                              color=[CATEGORY_COLOR[c] for c in d["product_category"]],
                              hover="%{y}<br>%{x:.1%}<extra></extra>", height=280),
                      "Ticket Rate by Category", "How often an order turns into a support ticket")
    with c2:
        d = tickets.groupby("channel").agg(csat=("csat_score", "mean")).sort_values("csat").reset_index()
        ui.chart_card(ch.hbar(d, "channel", "csat", text=[f"{v:.2f}" for v in d["csat"]],
                              hover="%{y}<br>Avg CSAT %{x:.2f}<extra></extra>", height=280, x_max=5 / 1.04),
                      "Avg CSAT by Support Channel", "Out of 5")


# ======================================================================================
# DATA EXPLORER
# ======================================================================================
with tabs[5]:
    ui.section("", "Data Explorer", "Look up any order or ticket, or browse and download the data.")

    with ui.card("Order & Ticket Lookup", "Search by order or ticket ID, e.g. ORD-700016 or TKT-900016"):
        query = st.text_input("Order or ticket ID", placeholder="ORD-… or TKT-…", label_visibility="collapsed",
                              key="lookup").strip().upper().replace("_", "-")
        if query:
            if query.isdigit():
                query = f"ORD-{query}"
            trow = tickets_all[tickets_all["ticket_id"] == query]
            oid = trow["order_id"].iloc[0] if len(trow) else query
            orow = orders_all[orders_all["order_id"] == oid]
            if orow.empty:
                st.warning(f"No order or ticket found for **{query}**.")
            else:
                o = orow.iloc[0]
                status_tint = {"DELIVERED": ("#128a5f", "#E8F6EF"), "DELAYED_IN_TRANSIT": ("#b07800", "#FDF4E1"),
                               "LOST_IN_TRANSIT": ("#BD1E59", "#FFF1F3"), "RETURNED_TO_SELLER": ("#6250d6", "#EFEDFB"),
                               "CANCELLED_BEFORE_SHIP": ("#52514e", "#F0F0EE")}
                fg, bg = status_tint.get(o["delivery_status"], ACCENTS["slate"][::-1])
                ui.field_grid([
                    ("Order", o["order_id"]), ("Status", ui.pill(STATUS_LABEL.get(o["delivery_status"], o["delivery_status"]), fg, bg)),
                    ("Order Date", f"{o['order_date']:%d %b %Y, %H:%M}"), ("Amount", f"₹{o['order_amount']:,.0f}"),
                    ("Category", o["product_category"]), ("Courier", o["courier_partner"]),
                    ("Payment", o["payment_method"]), ("City", o["customer_city"]),
                ])
                tk = tickets_all[tickets_all["order_id"] == o["order_id"]]
                for _, t in tk.iterrows():
                    st.write("")
                    verdict = (ui.pill("Over-Refunded: " + RULE_SHORT.get(t["primary_violation"], ""), "#BD1E59", "#FFF1F3")
                               if t["is_policy_violation"] else ui.pill("Within Policy", "#128a5f", "#E8F6EF"))
                    ui.field_grid([
                        ("Ticket", t["ticket_id"]), ("Issue", t["issue_category"]),
                        ("Resolution", t["resolution_status"]), ("Refund", f"₹{t['refund_amount']:,.0f}"),
                        ("Channel", t["channel"]), ("Resolution Time", hours(t["resolution_hours"])),
                        ("CSAT", "–" if pd.isna(t["csat_score"]) else f"{t['csat_score']:.0f} / 5"), ("Policy Check", verdict),
                    ])
                if tk.empty:
                    st.caption("This order has no support ticket.")

    which = st.segmented_control("Table", ["Orders", "Tickets"], default="Orders", key="explorer_table",
                                 label_visibility="collapsed") or "Orders"
    base = orders if which == "Orders" else tickets.drop(columns=["customer_message"])
    with ui.card(f"{which} ({'Filtered' if filtered else 'All'})", "Follows the sidebar filters; type to search any column"):
        search = st.text_input("Search", placeholder="Search text in any column…", key="explorer_search",
                               label_visibility="collapsed")
        view = base
        if search:
            mask = base.astype(str).apply(lambda col: col.str.contains(search, case=False, regex=False)).any(axis=1)
            view = base[mask]
        st.caption(f"{len(view):,} rows")
        st.dataframe(view, hide_index=True, width="stretch", height=420)
        st.download_button(f"⬇  Download {which.lower()} CSV", view.to_csv(index=False), f"{which.lower()}_view.csv", "text/csv")

# ======================================================================================
# CLEANING LOG
# ======================================================================================
with tabs[6]:
    ui.section("", "Data Quality", "How the source data was prepared for this dashboard.")
    raw_total = {"orders": len(orders_all) + (removed_rows["dataset"] == "orders").sum(),
                 "support_tickets": len(tickets_all) + (removed_rows["dataset"] == "support_tickets").sum()}
    c1, c2 = st.columns(2, gap="medium")
    for col, ds, clean_n, title in [(c1, "orders", len(orders_all), "Orders"),
                                    (c2, "support_tickets", len(tickets_all), "Support Tickets")]:
        with col:
            counts = removed_rows[removed_rows["dataset"] == ds]["removal_reason"].value_counts()
            steps = [("Source Records", raw_total[ds], "total", MUTED_MARK)]
            steps += [(reason.replace(" (re-formatted copy)", "").title(), -n, "delta") for reason, n in counts.items()]
            steps.append(("Final Records", clean_n, "total", SERIES[0]))
            ui.chart_card(ch.waterfall(steps, height=300, fmt=lambda v: f"{v:,.0f}"),
                          f"{title}: {raw_total[ds]:,} → {clean_n:,} Records", "Duplicates and test records removed")

    for ds, title in [("orders", "Orders"), ("support_tickets", "Support Tickets")]:
        with ui.card(f"{title}: Issues Found and Fixes Applied"):
            st.dataframe(cleaning_log[(cleaning_log["dataset"] == ds) & (cleaning_log["column"] != "row count")]
                         [["step", "column", "issue", "rows_affected", "fix", "examples"]],
                         hide_index=True, width="stretch",
                         column_config={"step": st.column_config.NumberColumn("#", width="small"),
                                        "column": "Column", "rows_affected": st.column_config.NumberColumn("Rows", format="%,d"),
                                        "issue": st.column_config.TextColumn("Issue Found", width="large"),
                                        "fix": st.column_config.TextColumn("Fix Applied", width="medium"),
                                        "examples": "Examples"})

    with ui.card("Download Data"):
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇  orders_clean.csv", (CLEAN / "orders_clean.csv").read_bytes(), "orders_clean.csv", width="stretch")
        d2.download_button("⬇  support_tickets_clean.csv", (CLEAN / "support_tickets_clean.csv").read_bytes(),
                           "support_tickets_clean.csv", width="stretch")
        d3.download_button("⬇  cleaning_log.csv", (LOGS / "cleaning_log.csv").read_bytes(), "cleaning_log.csv", width="stretch")
