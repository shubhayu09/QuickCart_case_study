"""
Conversation logic. The chat state is a plain dict kept in st.session_state, so this module has no UI code.

Flow for each customer message:
  1. find an order / ticket id in the text (and check it belongs to this customer)
  2. classify the intent (Groq LLM, keyword fallback)
  3. pick the order: the one mentioned, the one selected, the only one, or ask which one
  4. policy.decide() -> reply + action buttons
"""
import hashlib

from chatbot import policy
from chatbot.data import CustomerData
from chatbot.intents import INTENTS, classify, extract_refs

ORDER_INTENTS = set(INTENTS) - {"other", "human_agent"}


def new_state(customer_id: str) -> dict:
    return {"customer": customer_id, "messages": [], "order_id": None, "pending_intent": None, "done": set()}


def _say(state, text, actions=None, order_id=None):
    state["messages"].append({"role": "assistant", "text": text, "actions": actions or [], "order_id": order_id})


def _reference(state, order_id, kind) -> str:
    return "QC-" + hashlib.sha1(f"{state['customer']}{order_id}{kind}".encode()).hexdigest()[:6].upper()


def greet(state, data: CustomerData):
    n = len(data.orders_of(state["customer"]))
    _say(state, f"Hi! I'm the QuickCart help assistant. You have {n} order{'s' if n != 1 else ''} with us. "
                "Pick an order on the left, or tell me what you need help with.")


def _order_picker(data: CustomerData, customer_id: str) -> list[policy.Action]:
    return [policy.Action("select_order", f"{r.order_id} · {r.product_category}", 0) for r in
            data.orders_of(customer_id).head(6).itertuples()]


def select_order(state, data: CustomerData, order_id: str, kb, intent: str | None = None):
    state["order_id"] = order_id
    intent = intent or state.pop("pending_intent", None)
    state["pending_intent"] = None
    if intent:
        _answer(state, data, kb, intent)
    else:
        order = data.order(state["customer"], order_id)
        _say(state, f"Sure, let's look at order {order_id} ({order['product_category']}, "
                    f"{policy.rupees(order['order_amount'])}). What do you need help with?", order_id=order_id)


def _answer(state, data: CustomerData, kb, intent: str):
    order = data.order(state["customer"], state["order_id"])
    ticket = data.ticket_for(order["order_id"])
    decision = policy.decide(kb, intent, order, ticket, data.now)
    # once a money action was confirmed in this chat for this order, don't offer money again (Rule 2 / no double pay)
    if order["order_id"] in state["done"]:
        kept = [a for a in decision.actions if a.kind not in {"refund", "replacement", "voucher", "ask_damage"}]
        if len(kept) < len(decision.actions):
            decision.reply = (f"I've already arranged a refund, replacement or voucher for order {order['order_id']} "
                              "in this chat (see the reference above), so I can't add another one. "
                              "Is there anything else I can help with?")
        decision.actions = kept
    _say(state, decision.reply, decision.actions, order["order_id"])


def handle_message(state, data: CustomerData, kb, text: str, api_key: str | None):
    state["messages"].append({"role": "user", "text": text, "actions": [], "order_id": None})
    customer = state["customer"]

    order_ref, ticket_ref = extract_refs(text)
    if ticket_ref:
        order = data.order_for_ticket(customer, ticket_ref)
        if order is None:
            _say(state, f"I couldn't find ticket {ticket_ref} on your account. Please check the number, "
                        "or pick one of your orders below.", _order_picker(data, customer))
            return
        state["order_id"] = order["order_id"]
    elif order_ref:
        if data.order(customer, order_ref) is None:
            _say(state, f"I couldn't find order {order_ref} on your account. Please check the number, "
                        "or pick one of your orders below.", _order_picker(data, customer))
            return
        state["order_id"] = order_ref

    intent, _source = classify(text, api_key)

    if intent == "other" and (order_ref or ticket_ref):
        select_order(state, data, state["order_id"], kb)
        return
    if intent == "other" and not state["order_id"]:
        _say(state, "I can help with tracking an order, damaged items, refunds, payments, returns or cancellations. "
                    "Which order is this about?", _order_picker(data, customer))
        return
    if intent == "human_agent" and not state["order_id"]:
        _say(state, "Sure. I'll connect you with a support agent. Your reference is "
                    f"{_reference(state, '-', 'agent')}. Expect a call or email within 24 hours.")
        return

    if not state["order_id"]:
        orders = data.orders_of(customer)
        if len(orders) == 1:
            state["order_id"] = orders.iloc[0]["order_id"]
        else:
            state["pending_intent"] = intent
            _say(state, "Which order is this about?", _order_picker(data, customer))
            return

    _answer(state, data, kb, intent)


def handle_action(state, data: CustomerData, kb, action: dict):
    """action: {'kind', 'label', 'amount', 'order_id'} from a clicked button."""
    kind, order_id = action["kind"], action.get("order_id")
    state["messages"].append({"role": "user", "text": action["label"], "actions": [], "order_id": None})

    if kind == "select_order":
        select_order(state, data, action["label"].split(" · ")[0], kb)
        return
    if kind == "ask_damage":
        state["order_id"] = order_id
        _answer(state, data, kb, "damaged_item")
        return
    if kind in {"refund", "replacement", "voucher"}:
        if order_id in state["done"]:
            _say(state, "That's already been taken care of for this order in this chat.")
            return
        state["done"].add(order_id)   # locks the other option (e.g. replacement vs refund)

    text = policy.CONFIRMATIONS[kind].format(amount=policy.rupees(action.get("amount", 0)), order_id=order_id,
                                             ref=_reference(state, order_id, kind))
    _say(state, text + " Is there anything else I can help with?", order_id=order_id)
