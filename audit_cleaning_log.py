"""
Independent audit of logs/cleaning_log.csv.

Recomputes every row count in the cleaning log straight from the raw CSVs, using separate
(deliberately simple) logic, on exactly the rows that end up in the clean files. Any mismatch
means a log entry was counted at the wrong stage or on the wrong rows.

Run:  .venv/Scripts/python audit_cleaning_log.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
raw_o = pd.read_csv(ROOT / "data/raw/orders.csv", dtype=str, keep_default_na=False)
raw_t = pd.read_csv(ROOT / "data/raw/support_tickets.csv", dtype=str, keep_default_na=False)
clean_o = pd.read_csv(ROOT / "data/clean/orders_clean.csv")
clean_t = pd.read_csv(ROOT / "data/clean/support_tickets_clean.csv")
log = pd.read_csv(ROOT / "logs/cleaning_log.csv")

# Raw rows that survive into the clean files: drop test rows, exact copies, then keep the first of each ID.
o = raw_o[~(raw_o["customer_id"].str.contains("TEST") | raw_o["order_id"].str.startswith("ORD-999"))]
o = o.drop_duplicates().drop_duplicates("order_id")
t = raw_t.drop_duplicates().drop_duplicates("ticket_id")
assert len(o) == len(clean_o) and set(o["order_id"]) == set(clean_o["order_id"])
assert len(t) == len(clean_t) and set(t["ticket_id"]) == set(clean_t["ticket_id"])

canonical_cat = {"Electronics", "Fashion & Apparel", "Home & Kitchen", "Beauty & Groceries"}
canonical_courier = {"Shadowfax_Local", "Delhivery_Express", "EcomExpress_Surface", "BlueDart_Air"}
canonical_city = {"Bengaluru", "Delhi NCR", "Mumbai", "Hyderabad", "Pune", "Chennai"}
plain_number = re.compile(r"\d+(\.\d+)?")
csat = pd.to_numeric(t["csat_score"].str.strip(), errors="coerce")

expected = {
    # orders
    ("orders", "order_id / customer_id"): (raw_o["customer_id"].str.contains("TEST") | raw_o["order_id"].str.startswith("ORD-999")).sum(),
    ("orders", "product_category"): (~o["product_category"].isin(canonical_cat)).sum(),
    ("orders", "courier_partner"): (~o["courier_partner"].isin(canonical_courier)).sum(),
    ("orders", "customer_city"): (~o["customer_city"].isin(canonical_city)).sum(),
    ("orders", "order_date"): len(o),
    ("orders", "order_amount"): (~o["order_amount"].apply(lambda v: bool(plain_number.fullmatch(v)))).sum(),
    ("orders", "row count"): len(raw_o) - len(clean_o),
    # tickets
    ("support_tickets", "order_id#malformed"): (~t["order_id"].str.fullmatch(r"ORD-\d{6}")).sum(),
    ("support_tickets", "ticket_created_at"): len(t),
    ("support_tickets", "ticket_resolved_at#parsed"): (t["ticket_resolved_at"].str.strip() != "").sum(),
    ("support_tickets", "refund_amount#text"): t["refund_amount"].str.contains(r"[₹,]|Rs", regex=True).sum(),
    ("support_tickets", "refund_amount#missing"): t["refund_amount"].str.strip().str.upper().isin(["", "NIL"]).sum(),
    ("support_tickets", "csat_score#invalid"): (csat.notna() & ~csat.between(1, 5)).sum(),
    ("support_tickets", "csat_score#blank"): csat.isna().sum(),
    ("support_tickets", "csat_score#valid"): csat.between(1, 5).sum(),
    ("support_tickets", "ticket_resolved_at#negative"): clean_t["invalid_duration"].sum(),
    ("support_tickets", "customer_message"): t["customer_message"].str.contains("[ORDER-REF]", regex=False).sum(),
    ("support_tickets", "row count"): len(raw_t) - len(clean_t),
}


def logged(dataset, column, issue_contains=None):
    rows = log[(log["dataset"] == dataset) & (log["column"] == column)]
    if issue_contains:
        rows = rows[rows["issue"].str.contains(issue_contains, regex=False)]
    assert len(rows) == 1, (dataset, column, issue_contains, len(rows))
    return int(rows["rows_affected"].iloc[0])


lookups = {
    ("support_tickets", "order_id#malformed"): ("order_id", "Malformed"),
    ("support_tickets", "ticket_resolved_at#parsed"): ("ticket_resolved_at", "formats"),
    ("support_tickets", "refund_amount#text"): ("refund_amount", "stored as text"),
    ("support_tickets", "refund_amount#missing"): ("refund_amount", "Missing refund"),
    ("support_tickets", "csat_score#invalid"): ("csat_score", "outside"),
    ("support_tickets", "csat_score#blank"): ("csat_score", "blank"),
    ("support_tickets", "csat_score#valid"): ("csat_score", "Valid"),
    ("support_tickets", "ticket_resolved_at#negative"): ("ticket_resolved_at", "earlier than created"),
}

failures = 0
print(f"{'dataset':<16} {'check':<30} {'log':>7} {'audit':>7}")
for (ds, key), exp in expected.items():
    col, contains = lookups.get((ds, key), (key, None))
    got = logged(ds, col, contains)
    ok = got == int(exp)
    failures += not ok
    print(f"{ds:<16} {key:<30} {got:>7} {int(exp):>7}  {'OK' if ok else 'MISMATCH'}")

# Headline metrics must be computed on the same rows the log describes
assert clean_t["csat_score"].notna().sum() == expected[("support_tickets", "csat_score#valid")]
assert clean_t["csat_score"].notna().sum() + expected[("support_tickets", "csat_score#blank")] \
    + expected[("support_tickets", "csat_score#invalid")] == len(clean_t)

print("\nAll log counts reconcile with the clean data." if failures == 0 else f"\n{failures} mismatches.")
sys.exit(1 if failures else 0)
