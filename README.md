# QuickCart Case Study: Delivery, Support & Refund Analytics

QuickCart is an online shopping app (Electronics, Fashion & Apparel, Home & Kitchen, Beauty & Groceries).
Delivery complaints have spiked, support replies are slow, and some refunds break company policy.

This project:

- **Part 1:** cleans the raw order and support-ticket data, finds the root cause, and presents it in a
  leadership dashboard.
- **Part 2:** adds a customer-facing help chatbot that looks up a customer's real order, applies
  QuickCart's 4 refund rules, and replies with an instant action.

Both parts run in one Streamlit web app with an **Admin View / Customer View** switch.
To run it, see [INSTRUCTIONS.md](INSTRUCTIONS.md).

---

## Key findings

| Area | Result |
|---|---|
| Orders / tickets | **6,200** unique orders and **5,200** unique tickets (from 6,500 and 5,550 raw rows) |
| Total order value | **₹2.29 Cr** (sum of order value; ₹2.30 Cr with shipping) |
| Total refunds | **₹1.00 Cr**, about 44% of order value |
| Courier bottleneck | **Shadowfax_Local**: 31.3% of its orders lost or delayed (others ~18%) and 32.6 h average resolution (others ~19 h). It carries 37% of all orders. |
| Support speed | **24.6 h** average resolution (median 20 h); 40% of tickets take over 24 h; **582** tickets still open |
| Customer satisfaction | **3.70 / 5** average CSAT (2,957 valid ratings). CSAT falls from 4.1 (resolved within 24 h) to 2.0 (over 48 h). |
| Refund policy leakage | **149 tickets, ₹4,68,054** paid above policy |

Refund leakage by rule:

| Rule | Tickets | ₹ over-paid |
|---|---|---|
| R1a: ₹100 late bonus given although resolved within 24 h | 4 | 400 |
| R1b: delayed order refunded above the ₹100 voucher | 0 | 0 |
| R2: damaged item got a replacement **and** a refund | 40 | 1,32,510 |
| R3: unpaid COD order (cancelled before shipping) was refunded | 55 | 2,48,995 |
| R4: refund above order value + ₹100 | 50 | 86,149 |

Other insights: 928 full refunds were paid on orders marked delivered; 109 of 702 apology vouchers
weren't the ₹100 the policy specifies (they match shipping fees instead); email and phone tickets
are the slowest to resolve.

---

## Part 1: Data cleaning

`clean_data.py` cleans both CSVs and writes a log of every issue it found, how many rows it
affected, and how it was fixed. All counts are on the final de-duplicated rows.
`audit_cleaning_log.py` independently recounts every logged number from the raw files.

**Orders (6,500 → 6,200 rows):**
- 45 test records removed (`ORD-999xxx`, `CUST-TESTxx`, amount −999).
- 22 exact duplicate rows removed, plus 233 duplicates that differed only in date format.
- Dates in 9 different formats parsed. Slash dates are DD/MM.
- Amounts stored as text (`₹1,999.00`, `INR 699`) converted to numbers.
- Spelling variants fixed: categories 12 → 4, couriers 8 → 4, cities 12 → 6 (e.g. Bangalore → Bengaluru).

**Support tickets (5,550 → 5,200 rows):**
- 33 exact duplicate rows removed, plus 317 duplicates that differed only in date format.
- 624 malformed order references fixed (` ord_701234 `, bare `701234`); every ticket now matches an order.
- Refunds written as `NIL`, blank, `Rs. 1499` or `₹3,499.00` standardised.
- 30 invalid CSAT scores (99, −1) set to missing; blanks are treated as "not rated", not as 0.
- 38 tickets resolved before they were created are flagged and left out of resolution-time averages.

Outputs: `data/clean/` (cleaned CSVs, the list of policy violations, and every removed row with its
reason) and `logs/` (the cleaning log as CSV and Markdown, plus the run log).

## Part 1: Leadership dashboard (Admin View)

`dashboard.py` is an interactive Streamlit and Plotly dashboard. Sidebar filters (courier,
category, city, payment method, month) apply to every tab.

| Tab | What it shows |
|---|---|
| Overview | Headline KPIs, order value by category and city (treemap), delivery outcomes, order value → refunds → retained revenue (waterfall), refunds by issue, ticket journey (Sankey), monthly trend |
| Courier Performance | Failure rate vs resolution time (bubble chart), lost and delayed rates, courier × city heatmap, status mix, courier deep-dive, scorecard |
| Support & CSAT | Resolution-time distribution against the 24 h target, CSAT by resolution time, CSAT by channel, open-ticket backlog heatmap |
| Refund Leakage | Leakage by policy rule (waterfall), rule × courier treemap, breakdowns, filterable list of over-refunded tickets with CSV export |
| Insights | Refunds on delivered orders, off-policy vouchers, late-voucher exposure, CSAT drop on slow tickets |
| Data Explorer | Look up any order or ticket ID; searchable, downloadable tables |
| Data Quality | Raw → clean record counts and the full cleaning log |

## Part 2: Customer help chatbot (Customer View)

A customer signs in with a customer ID (or picks one of the demo customers, each showing a
different situation). They see a short profile and their orders, and chat with the help assistant.

**How a message is handled:**

1. **Find the order:** the ID typed in the message, the order clicked, the customer's only order,
   or the bot asks "Which order?". IDs that don't belong to the signed-in customer are refused.
2. **Understand the intent:** one of 10 intents (where is my order, not delivered, damaged item,
   refund, double charged, return pickup, shipping fee/coupon, cancel, talk to an agent, other).
   A Groq-hosted LLM classifies the message; keyword matching is the fallback.
3. **Decide the answer:** a fixed knowledge base (`chatbot/knowledge_base.csv`, 10 intents × 5
   delivery statuses = 50 replies) plus a deterministic policy engine applying the refund rules:
   - **R1:** lost or returned order → full refund; ticket open more than 24 h → +₹100; delayed
     order → ₹100 voucher and wait 48 h.
   - **R2:** damaged item → the customer chooses replacement **or** refund, never both.
   - **R3:** unpaid COD order cancelled before shipping → ₹0.
   - **R4:** refund never exceeds order value + ₹100.

   Existing tickets are respected: an already-refunded order isn't refunded again.
4. **Instant action:** buttons such as *Refund ₹2,599*, *Send a free replacement* or *Add ₹100
   voucher*. Clicking one confirms the action with a reference number. Each order allows only one
   money action per chat.

The AI only reads the question; every answer and every rupee amount comes from the knowledge base
and the policy engine, so replies are always policy-compliant. Without an API key the chatbot
still works, using keyword matching.

---

## Project structure

```
QuickCart_Case_Study/
├── README.md                  this file
├── INSTRUCTIONS.md            how to run
├── requirements.txt
├── clean_data.py              Part 1: cleaning pipeline and cleaning log
├── audit_cleaning_log.py      independent recount of every logged number
├── dashboard.py               the app: Admin View dashboard and the view switch
├── ui/                        dashboard look and feel (reusable)
│   ├── theme.py               colours, fonts, chart template
│   ├── styles.css             page styles
│   ├── components.py          header, KPI cards, cards, sidebar pieces
│   ├── charts.py              chart builders
│   └── formatters.py          ₹ / % / hours formatting
├── chatbot/                   Part 2: chatbot logic (no UI code)
│   ├── knowledge_base.csv     50 replies: 10 intents × 5 delivery statuses
│   ├── intents.py             intent detection (Groq LLM + keyword fallback)
│   ├── policy.py              refund rules R1–R4
│   ├── bot.py                 conversation flow
│   └── data.py                customer-scoped data access
├── customer_view/             Part 2: customer page
│   ├── view.py                sign-in, profile, orders, chat
│   ├── components.py
│   └── styles.css
├── data/
│   ├── raw/                   original CSVs
│   └── clean/                 cleaned outputs
├── logs/                      cleaning log and run log
└── .streamlit/
    ├── config.toml            app theme
    └── secrets.toml           optional Groq API key (not shared)
```

## Assumptions and limitations

- **Total order value** is the sum of `order_amount` (shipping excluded), because the refund
  policy refunds `order_amount`.
- **Ticket age** for the 24-hour rule in the chatbot is measured from the data's snapshot time
  (30 Mar 2026), not today's date.
- **The data is a snapshot:** chatbot actions are simulated and reset when the session ends;
  nothing is written back to the data.
- **The `customer_message` text** in the ticket data is unrelated filler, so it isn't used for
  analysis.
- **Keyword fallback:** without an API key, the chatbot understands typical wording but is weaker
  on Hinglish or slang.
