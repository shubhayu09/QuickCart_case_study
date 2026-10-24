"""
Policy engine: picks the knowledge-base row for (intent, delivery status) and applies the SOP rules
that depend on the order and its existing ticket. Everything here is deterministic.

  Rule 1  LOST / RETURNED -> full refund; ticket open > 24 h -> + ₹100 voucher; DELAYED -> ₹100 voucher, wait 48 h
  Rule 2  Damaged -> replacement OR refund, never both
  Rule 3  COD + CANCELLED_BEFORE_SHIP -> refund ₹0 (customer never paid)
  Rule 4  A refund never exceeds order_amount + ₹100
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

KB_PATH = Path(__file__).with_name("knowledge_base.csv")
LATE_VOUCHER = 100.0
VOUCHER = 100.0


@dataclass
class Action:
    kind: str          # refund | voucher | replacement | report_missing | ask_damage | pickup | escalate_*
    label: str         # button text shown to the customer
    amount: float = 0.0


@dataclass
class Decision:
    reply: str
    actions: list[Action] = field(default_factory=list)
    rule_ref: str = "-"   # internal only - never shown to the customer


def load_kb() -> pd.DataFrame:
    return pd.read_csv(KB_PATH).set_index(["intent", "delivery_status"])


def rupees(x: float) -> str:
    return f"₹{x:,.0f}"


def _fill(template: str, order: pd.Series) -> str:
    return template.format(
        order_id=order["order_id"], category=order["product_category"], courier=order["courier_partner"].split("_")[0],
        order_amount=rupees(order["order_amount"]), shipping_fee=rupees(order["shipping_fee"]),
        order_date=f"{pd.Timestamp(order['order_date']):%d %b %Y}",
    )


def _drop_refund_offer(reply: str) -> str:
    """Removes 'you're eligible for a full refund…' sentences when the refund has already been paid."""
    sentences = re.split(r"(?<=[.!?])\s+", reply)
    return " ".join(s for s in sentences if "eligible for a full refund" not in s and "will be refunded" not in s)


def _ticket_age_hours(ticket: pd.Series, now: pd.Timestamp) -> float:
    return (now - pd.Timestamp(ticket["ticket_created_at"])).total_seconds() / 3600


def decide(kb: pd.DataFrame, intent: str, order: pd.Series, ticket: pd.Series | None, now: pd.Timestamp) -> Decision:
    row = kb.loc[(intent, order["delivery_status"])]
    reply = _fill(row["reply"], order)
    amount = float(order["order_amount"])
    is_cod = order["payment_method"] == "Cash on Delivery (COD)"
    kinds = [] if row["action"] == "none" else row["action"].split("+")
    status = ticket["resolution_status"] if ticket is not None else None
    extra = []

    # ---- What has already happened on this order's existing ticket --------------------------
    # (a COD order cancelled before shipping was never paid, so Rule 3 below decides it, whatever the old ticket says)
    cod_cancelled = is_cod and order["delivery_status"] == "CANCELLED_BEFORE_SHIP"
    already_refunded = (ticket is not None and not cod_cancelled
                        and status == "Resolved - Full Refund Issued" and ticket["refund_amount"] > 0)
    replacement_sent = status == "Resolved - Replacement Sent"
    voucher_given = status == "Resolved - Apology Voucher Issued"
    open_over_24h = ticket is not None and bool(ticket["is_open"]) and _ticket_age_hours(ticket, now) > 24
    money_kinds = {"refund_full", "cancel_refund", "replace_or_refund"}

    if already_refunded and money_kinds & set(kinds):
        kinds = [k for k in kinds if k not in money_kinds]
        reply = _drop_refund_offer(reply)
        extra.append(f"A refund of {rupees(ticket['refund_amount'])} has already been issued for this order "
                     f"on ticket {ticket['ticket_id']}, so there's nothing more to refund.")
    if replacement_sent and {"refund_full", "replace_or_refund"} & set(kinds):
        # Rule 2: never both a free replacement and a cash refund
        kinds = [k for k in kinds if k not in {"refund_full", "replace_or_refund"}]
        extra.append("A free replacement has already been sent for this order, so a cash refund isn't available as well.")
    if voucher_given and "voucher_100" in kinds:
        kinds = [k for k in kinds if k != "voucher_100"]
        extra.append("A ₹100 apology voucher has already been added to your account for this order.")

    # ---- Rule 3: cancelled before shipping ---------------------------------------------------
    if "cancel_refund" in kinds:
        kinds.remove("cancel_refund")
        if is_cod:
            extra.append("It was a Cash on Delivery order, so no money was taken from you and there's nothing to refund.")
        else:
            extra.append(f"Your payment of {rupees(amount)} will be refunded to your original payment method.")
            kinds.append("refund_full")

    if intent == "double_charged" and is_cod and order["delivery_status"] != "CANCELLED_BEFORE_SHIP":
        extra.append("Note: this order was paid by Cash on Delivery, so no online payment was taken for it. "
                     "If you still see a deduction, our payments team will check it.")

    # ---- Rule 1: late-resolution voucher on refunds -------------------------------------------
    refund_amount = amount
    if "refund_full" in kinds and open_over_24h:
        refund_amount += LATE_VOUCHER
        extra.append("Because your support ticket has been open for more than 24 hours, "
                     "we're adding a ₹100 apology voucher to the refund.")

    # ---- Rule 4: hard cap ----------------------------------------------------------------------
    refund_amount = min(refund_amount, amount + LATE_VOUCHER)

    actions = []
    for k in kinds:
        if k == "refund_full":
            actions.append(Action("refund", f"Refund {rupees(refund_amount)}", refund_amount))
        elif k == "voucher_100":
            actions.append(Action("voucher", "Add ₹100 voucher", VOUCHER))
        elif k == "replace_or_refund":
            actions.append(Action("replacement", "Send a free replacement", 0.0))
            actions.append(Action("refund", f"Refund {rupees(amount)}", amount))   # Rule 2: refund = order_amount
        elif k == "report_missing":
            actions.append(Action("report_missing", "I didn't receive it"))
        elif k == "ask_damage":
            actions.append(Action("ask_damage", "Report a damaged item"))
        elif k == "schedule_pickup":
            actions.append(Action("pickup", "Schedule pickup"))
        elif k in ("escalate_payments", "escalate_billing", "escalate_agent"):
            label = {"escalate_payments": "Flag to payments team", "escalate_billing": "Send to billing team",
                     "escalate_agent": "Connect me to an agent"}[k]
            actions.append(Action(k, label))

    if extra:
        reply = reply + "\n\n" + " ".join(extra)
    return Decision(reply=reply, actions=actions, rule_ref=row["rule_ref"])


CONFIRMATIONS = {
    "refund": "Done. A refund of {amount} for order {order_id} has been initiated. It reaches your original "
              "payment method in 5–7 working days. Reference: {ref}.",
    "voucher": "Done. A ₹100 voucher has been added to your QuickCart account. Reference: {ref}.",
    "replacement": "Done. A free replacement for order {order_id} is on its way; we'll share tracking once it ships. "
                   "Reference: {ref}.",
    "report_missing": "I've raised a missing-parcel check with the courier for order {order_id}. You'll hear back "
                      "within 48 hours. Reference: {ref}.",
    "pickup": "Return pickup scheduled for order {order_id}. The courier will contact you within 48 hours. Reference: {ref}.",
    "escalate_payments": "Flagged to our payments team for order {order_id}. They'll update you within 5–7 working days. "
                         "Reference: {ref}.",
    "escalate_billing": "Sent to our billing team for order {order_id}. They'll get back to you within 48 hours. Reference: {ref}.",
    "escalate_agent": "You're in the queue for a support agent about order {order_id}. Expect a call or email within "
                      "24 hours. Reference: {ref}.",
}
