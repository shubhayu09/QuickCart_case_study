"""
Intent understanding: turns a customer's free-text message into one of 10 intents.

The Groq LLM is used ONLY for this classification step. It never writes replies or decides
amounts - those come from knowledge_base.csv and policy.py. If the API key is missing, the
call fails or the model answers with something unexpected, a keyword matcher takes over.
"""
import os
import re

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")

# label -> (description given to the LLM, chip label shown to the customer)
INTENTS = {
    "where_is_order": ("Customer wants to know where their order is or its delivery status", "Where is my order?"),
    "not_delivered": ("Order has not arrived, is late, or customer says they never received it", "Not delivered yet"),
    "damaged_item": ("Item arrived broken, damaged, defective, wrong or not working", "Item damaged"),
    "refund": ("Customer asks for a refund, money back, or the status of a refund", "I want a refund"),
    "double_charged": ("Customer was charged twice, money deducted without order, payment problem", "Charged twice"),
    "return_pickup": ("Customer wants to return an item or asks about a return pickup", "Return pickup"),
    "shipping_fee_coupon": ("Question or complaint about shipping/delivery fee, coupon or discount", "Shipping fee / coupon"),
    "cancel_order": ("Customer wants to cancel the order", "Cancel my order"),
    "human_agent": ("Customer wants to talk to a human, agent, executive or call support", "Talk to an agent"),
    "other": ("Greeting, thanks, or anything that fits none of the above", None),
}

# Ordered: the first matching pattern wins, so specific intents come before generic ones.
_KEYWORDS = [
    ("human_agent", r"\b(human|agent|executive|real person|call me|customer care|speak to|talk to (a |an )?(person|someone))\b"),
    ("double_charged", r"\b(twice|double|two times|charged (again|extra)|deducted|debited|extra charge|payment (failed|issue|problem))\b"),
    ("shipping_fee_coupon", r"\b(shipping (fee|charge)|delivery (fee|charge)|coupon|promo|discount|voucher code)\b"),
    ("cancel_order", r"\b(cancel|cancellation)\b"),
    ("return_pickup", r"\b(return|pick ?up|pickup|send (it )?back|exchange)\b"),
    ("damaged_item", r"\b(damag|broken|broke|crack|defect|faulty|not working|doesn'?t work|torn|leak|spoil|wrong item|scratch)"),
    ("refund", r"\b(refund|money back|reimburse|get my money)\b"),
    ("not_delivered", r"\b(not (yet )?(delivered|received|arrived|reached|come)|never (got|received|came|arrived)|didn'?t (get|receive|arrive)|haven'?t (got|received)|still waiting|late|delay)"),
    ("where_is_order", r"\b(where|track|tracking|status|when will|eta|arriv|deliver|shipped|reach)"),
]


def keyword_classify(text: str) -> str:
    t = text.lower()
    for label, pattern in _KEYWORDS:
        if re.search(pattern, t):
            return label
    return "other"


def _system_prompt() -> str:
    lines = "\n".join(f"- {k}: {desc}" for k, (desc, _) in INTENTS.items())
    return ("You classify messages sent to an e-commerce customer support chatbot.\n"
            f"Choose exactly one intent label:\n{lines}\n"
            "Reply with the label only, no punctuation or explanation.")


def groq_classify(text: str, api_key: str, timeout: float = 8.0) -> str | None:
    """Returns an intent label, or None if the call fails or the answer isn't a known label."""
    try:
        r = requests.post(GROQ_URL, timeout=timeout, headers={"Authorization": f"Bearer {api_key}"}, json={
            "model": GROQ_MODEL, "temperature": 0, "max_tokens": 300, "reasoning_effort": "low",
            "messages": [{"role": "system", "content": _system_prompt()}, {"role": "user", "content": text[:500]}],
        })
        r.raise_for_status()
        label = r.json()["choices"][0]["message"]["content"].strip().lower().strip(".`'\" ")
        return label if label in INTENTS else None
    except (requests.RequestException, KeyError, IndexError, ValueError):
        return None


def classify(text: str, api_key: str | None) -> tuple[str, str]:
    """Returns (intent, source) where source is 'llm' or 'keywords'."""
    if api_key:
        label = groq_classify(text, api_key)
        if label:
            return label, "llm"
    return keyword_classify(text), "keywords"


ORDER_REF = re.compile(r"\b(?:ORD[-_ ]?)?(7\d{5})\b", re.IGNORECASE)
TICKET_REF = re.compile(r"\bTKT[-_ ]?(9\d{5})\b", re.IGNORECASE)


def extract_refs(text: str) -> tuple[str | None, str | None]:
    """Finds an order id (ORD-7xxxxx or a bare 7xxxxx) and/or a ticket id (TKT-9xxxxx) in the text."""
    t = TICKET_REF.search(text)
    ticket = f"TKT-{t.group(1)}" if t else None
    o = ORDER_REF.search(TICKET_REF.sub(" ", text))
    order = f"ORD-{o.group(1)}" if o else None
    return order, ticket
