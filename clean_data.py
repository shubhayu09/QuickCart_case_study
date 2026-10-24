"""
QuickCart Case Study - Part 1: data cleaning pipeline.

Reads the raw CSVs from data/raw/, cleans them, derives the analysis columns
(resolution time, SOP refund-rule checks) and writes:

  data/clean/orders_clean.csv
  data/clean/support_tickets_clean.csv     (ticket + joined order fields + derived flags)
  data/clean/refund_violations.csv         (tickets that break the SOP rules)
  data/clean/removed_rows.csv              (every row dropped, with the reason)
  logs/cleaning_log.csv / cleaning_log.md  (issue -> rows affected -> fix)
  logs/cleaning_run.log                    (full run log)

Run:  .venv/Scripts/python clean_data.py
"""
import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
CLEAN = ROOT / "data" / "clean"
LOGS = ROOT / "logs"
CLEAN.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOGS / "cleaning_run.log", mode="w", encoding="utf-8"),
              logging.StreamHandler()],
)
log = logging.getLogger("clean")

# --------------------------------------------------------------------------------------
# Cleaning log: every step records what it found and what it did
# --------------------------------------------------------------------------------------
CLEANING_LOG = []
REMOVED = []


def record(dataset, column, issue, rows_affected, fix, examples=""):
    CLEANING_LOG.append(dict(step=len(CLEANING_LOG) + 1, dataset=dataset, column=column, issue=issue,
                             rows_affected=int(rows_affected), fix=fix, examples=examples))
    log.info(f"[{dataset}] {column}: {issue} -> {rows_affected} rows | {fix}")


def examples_of(series, n=4):
    vals = series.dropna().astype(str).unique()[:n]
    return " | ".join(repr(v) for v in vals)


# --------------------------------------------------------------------------------------
# Shared parsers
# --------------------------------------------------------------------------------------
# All formats seen in the raw files. Slash dates are DD/MM/YYYY: in the raw data the first
# part exceeds 12 in hundreds of rows while the second part never does.
DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S",      # 2026-01-04 20:04:15
    "%Y/%m/%d %H:%M:%S",      # 2026/02/12 19:20:43
    "%d/%m/%Y %H:%M",         # 02/01/2026 08:53
    "%d-%m-%Y %H:%M",         # 11-01-2026 19:47
    "%d.%m.%Y %H:%M",         # 12.02.2026 12:22
    "%d-%b-%Y %I:%M %p",      # 07-Jan-2026 05:19 PM
    "%d-%b-%y %H:%M",         # 15-Mar-26 18:19
    "%b %d, %Y %H:%M",        # Feb 24, 2026 14:55
    "%B %d, %Y %I:%M %p",     # January 23, 2026 11:41 AM
]


def parse_dates(raw: pd.Series):
    s = raw.astype("string").str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    fmt_used = pd.Series(pd.NA, index=s.index, dtype="string")
    for fmt in DATE_FORMATS:
        todo = out.isna() & s.notna() & (s != "")
        if not todo.any():
            break
        parsed = pd.to_datetime(s[todo], format=fmt, errors="coerce")
        hit = parsed.notna()
        out.loc[parsed[hit].index] = parsed[hit]
        fmt_used.loc[parsed[hit].index] = fmt
    unparsed = s.notna() & (s != "") & out.isna()
    return out, fmt_used, unparsed


NULL_TOKENS = {"", "NIL", "NULL", "NONE", "NA", "N/A", "-"}


def parse_money(raw: pd.Series):
    s = raw.astype("string").str.strip()
    is_null_token = s.isna() | s.str.upper().isin(NULL_TOKENS)
    cleaned = (s.str.replace(r"(?i)^(rs\.?|inr)\s*", "", regex=True)
                .str.replace("₹", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip())
    num = pd.to_numeric(cleaned.where(~is_null_token), errors="coerce")
    unparsed = ~is_null_token & num.isna()
    return num, is_null_token, unparsed


def drop_rows(df, mask, dataset, reason):
    removed = df[mask].copy()
    removed.insert(0, "removal_reason", reason)
    removed.insert(0, "dataset", dataset)
    REMOVED.append(removed)
    return df[~mask].copy()


# --------------------------------------------------------------------------------------
# ORDERS
# --------------------------------------------------------------------------------------
CATEGORY_MAP = {
    "electronics": "Electronics",
    "fashion & apparel": "Fashion & Apparel", "fashion_apparel": "Fashion & Apparel",
    "home & kitchen": "Home & Kitchen", "home_kitchen": "Home & Kitchen",
    "beauty & groceries": "Beauty & Groceries", "beauty_groceries": "Beauty & Groceries",
}
COURIER_MAP = {
    "shadowfax_local": "Shadowfax_Local", "delhivery_express": "Delhivery_Express",
    "ecomexpress_surface": "EcomExpress_Surface", "bluedart_air": "BlueDart_Air",
}
CITY_MAP = {
    "bengaluru": "Bengaluru", "bangalore": "Bengaluru",
    "delhi ncr": "Delhi NCR", "new delhi": "Delhi NCR",
    "mumbai": "Mumbai", "hyderabad": "Hyderabad", "pune": "Pune", "chennai": "Chennai",
}
DELIVERY_STATUSES = {"DELIVERED", "LOST_IN_TRANSIT", "CANCELLED_BEFORE_SHIP", "DELAYED_IN_TRANSIT",
                     "RETURNED_TO_SELLER"}
PAYMENT_METHODS = {"UPI", "Credit/Debit Card", "Cash on Delivery (COD)"}


def normalise_categorical(df, col, mapping, dataset, keep):
    raw = df[col].astype("string")
    key = raw.str.strip().str.lower()
    mapped = key.map(mapping)
    unmapped = mapped.isna() & raw.notna()
    if unmapped.any():
        raise ValueError(f"Unmapped {col} values: {raw[unmapped].unique()[:10]}")
    changed = raw != mapped
    record(dataset, col,
           f"{raw[keep].nunique()} spelling variants (case, trailing spaces, snake_case, synonyms) for "
           f"{mapped[keep].nunique()} real values",
           (changed & keep).sum(), "Trimmed, lower-cased and mapped to one canonical label",
           examples_of(raw[changed]))
    df[col] = mapped
    return df


def clean_orders():
    ds = "orders"
    df = pd.read_csv(RAW / "orders.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw_rows = len(df)
    log.info(f"Loaded orders.csv: {raw_rows} rows, {df.shape[1]} columns")

    # whitespace in IDs
    for col in ["order_id", "customer_id"]:
        stripped = df[col].str.strip().str.upper()
        n = (stripped != df[col]).sum()
        if n:
            record(ds, col, "Leading/trailing whitespace or lower case in ID", n, "Trimmed and upper-cased")
        df[col] = stripped

    # test / synthetic rows
    test_mask = df["customer_id"].str.contains("TEST") | df["order_id"].str.startswith("ORD-999")
    record(ds, "order_id / customer_id",
           "Synthetic test records (ORD-999xxx, CUST-TESTxx, amount -999.00, all CANCELLED_BEFORE_SHIP)",
           test_mask.sum(), "Removed (not real customer orders)", examples_of(df.loc[test_mask, "order_id"]))
    df = drop_rows(df, test_mask, ds, "test record")

    # exact duplicate rows
    exact = df.duplicated(keep="first")
    record(ds, "all columns", "Exact duplicate rows", exact.sum(), "Removed, kept first occurrence")
    df = drop_rows(df, exact, ds, "exact duplicate row")

    # Re-formatted duplicate order_ids are dropped further down, once parsing proves the copies are identical.
    # Fix counts below are taken on the rows that survive (first occurrence of each order_id), so every
    # number in the log refers to the final clean dataset.
    keep = ~df["order_id"].duplicated(keep="first")

    # categoricals
    df = normalise_categorical(df, "product_category", CATEGORY_MAP, ds, keep)
    df = normalise_categorical(df, "courier_partner", COURIER_MAP, ds, keep)
    df = normalise_categorical(df, "customer_city", CITY_MAP, ds, keep)

    # dates
    parsed, fmt_used, unparsed = parse_dates(df["order_date"])
    if unparsed.any():
        raise ValueError(f"Unparsed order dates: {df.loc[unparsed, 'order_date'].head().tolist()}")
    record(ds, "order_date",
           f"Dates stored as text in {fmt_used[keep].nunique()} different formats (plus stray spaces); "
           "slash dates are DD/MM/YYYY",
           keep.sum(), "Parsed each format explicitly into one datetime (YYYY-MM-DD HH:MM:SS)",
           examples_of(df["order_date"], 5))
    df["order_date"] = parsed

    # amounts
    amount, null_tok, unparsed = parse_money(df["order_amount"])
    if unparsed.any() or null_tok.any():
        raise ValueError(f"Bad order_amount values: {df.loc[unparsed | null_tok, 'order_amount'].head().tolist()}")
    texty = ~df["order_amount"].str.fullmatch(r"\d+(\.\d+)?")
    record(ds, "order_amount", "Amount stored as text with currency symbols/commas (₹1,999.00, INR 699)",
           (texty & keep).sum(), "Stripped ₹ / INR / commas and converted to a number",
           examples_of(df.loc[texty, "order_amount"]))
    df["order_amount"] = amount
    df["shipping_fee"] = pd.to_numeric(df["shipping_fee"])

    # duplicate order_ids that are the same order written differently
    dup_ids = df["order_id"].duplicated(keep="first")
    dupe_groups = df[df["order_id"].isin(df.loc[dup_ids, "order_id"])]
    non_date_cols = [c for c in df.columns if c != "order_date"]
    conflicts = dupe_groups.groupby("order_id")[non_date_cols].nunique().gt(1).any(axis=1).sum()
    date_spread = dupe_groups.groupby("order_id")["order_date"].agg(lambda x: (x.max() - x.min()).total_seconds())
    record(ds, "order_id",
           f"Same order_id repeated with the date written in another format "
           f"(max date difference {date_spread.max():.0f}s, {conflicts} with any other field differing)",
           dup_ids.sum(), "De-duplicated on order_id, kept first occurrence",
           examples_of(df.loc[dup_ids, "order_id"]))
    df = drop_rows(df, dup_ids, ds, "duplicate order_id (re-formatted copy)")

    # validation of the already-clean columns
    for col, allowed in [("delivery_status", DELIVERY_STATUSES), ("payment_method", PAYMENT_METHODS)]:
        bad = ~df[col].isin(allowed)
        if bad.any():
            raise ValueError(f"Unexpected {col}: {df.loc[bad, col].unique()}")
        record(ds, col, "Validated against allowed values - no issues", 0, "No change")
    record(ds, "shipping_fee", f"Validated numeric values {sorted(int(v) for v in df['shipping_fee'].unique())} - no issues", 0,
           "No change")

    df = df.sort_values("order_id").reset_index(drop=True)
    df["order_month"] = df["order_date"].dt.to_period("M").astype(str)
    df["is_lost_or_delayed"] = df["delivery_status"].isin(["LOST_IN_TRANSIT", "DELAYED_IN_TRANSIT"])
    df["is_cod"] = df["payment_method"].eq("Cash on Delivery (COD)")

    assert df["order_id"].is_unique
    assert (df["order_amount"] > 0).all()
    assert df.notna().all().all()
    log.info(f"orders: {raw_rows} raw -> {len(df)} clean rows")
    return df, raw_rows


# --------------------------------------------------------------------------------------
# SUPPORT TICKETS
# --------------------------------------------------------------------------------------
def normalise_order_ref(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip().str.upper().str.replace("_", "-", regex=False)
    return s.where(~s.str.fullmatch(r"\d{6}"), "ORD-" + s)


def clean_tickets(orders: pd.DataFrame):
    ds = "support_tickets"
    df = pd.read_csv(RAW / "support_tickets.csv", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw_rows = len(df)
    log.info(f"Loaded support_tickets.csv: {raw_rows} rows, {df.shape[1]} columns")

    df["ticket_id"] = df["ticket_id"].str.strip().str.upper()
    df["customer_id"] = df["customer_id"].str.strip().str.upper()

    # exact duplicate rows
    exact = df.duplicated(keep="first")
    record(ds, "all columns", "Exact duplicate rows", exact.sum(), "Removed, kept first occurrence")
    df = drop_rows(df, exact, ds, "exact duplicate row")

    # Re-formatted duplicate ticket_ids are dropped further down, once parsing proves the copies are identical.
    # Fix counts below are taken on the rows that survive (first occurrence of each ticket_id), so every
    # number in the log refers to the final clean dataset.
    keep = ~df["ticket_id"].duplicated(keep="first")

    # broken order_id foreign key
    norm = normalise_order_ref(df["order_id"])
    changed = norm != df["order_id"]
    unmatched_before = (~df["order_id"].isin(orders["order_id"]) & keep).sum()
    record(ds, "order_id",
           f"Malformed order reference (' ord_701234 ', bare '701234', trailing spaces) - "
           f"{unmatched_before} tickets could not be joined to orders",
           (changed & keep).sum(), "Trimmed, upper-cased, '_'->'-', added missing 'ORD-' prefix",
           examples_of(df.loc[changed, "order_id"]))
    df["order_id"] = norm

    # dates
    for col in ["ticket_created_at", "ticket_resolved_at"]:
        parsed, fmt_used, unparsed = parse_dates(df[col])
        if unparsed.any():
            raise ValueError(f"Unparsed {col}: {df.loc[unparsed, col].head().tolist()}")
        record(ds, col, f"Timestamps stored as text in {fmt_used[keep].nunique()} different formats",
               (parsed.notna() & keep).sum(), "Parsed each format explicitly into one datetime",
               examples_of(df[col], 5))
        df[col] = parsed

    # refund amount
    amount, null_tok, unparsed = parse_money(df["refund_amount"])
    if unparsed.any():
        raise ValueError(f"Bad refund values: {df.loc[unparsed, 'refund_amount'].head().tolist()}")
    texty = ~null_tok & ~df["refund_amount"].str.fullmatch(r"\d+(\.\d+)?")
    record(ds, "refund_amount", "Refund stored as text with ₹ / 'Rs.' / commas", (texty & keep).sum(),
           "Stripped symbols and converted to number", examples_of(df.loc[texty, "refund_amount"]))
    statuses_with_null = sorted(df.loc[null_tok & keep, "resolution_status"].unique())
    record(ds, "refund_amount",
           f"Missing refund written as blank or 'NIL' (only on statuses: {', '.join(statuses_with_null)})",
           (null_tok & keep).sum(), "Set to ₹0 - none of these statuses pays a cash refund")
    df["refund_amount"] = amount.fillna(0.0)

    # CSAT
    csat = pd.to_numeric(df["csat_score"].str.strip(), errors="coerce")
    out_of_range = csat.notna() & ~csat.between(1, 5)
    record(ds, "csat_score", "CSAT outside the 1-5 scale (99, -1)", (out_of_range & keep).sum(),
           "Set to missing (invalid survey response)", examples_of(df.loc[out_of_range, "csat_score"]))
    record(ds, "csat_score", "CSAT blank (customer did not rate)", (csat.isna() & keep).sum(),
           "Kept as missing - excluded from average, not treated as 0")
    record(ds, "csat_score", "Valid CSAT ratings (1-5) used for the average", (csat.between(1, 5) & keep).sum(),
           "Average CSAT is computed on these rows only")
    df["csat_score"] = csat.where(~out_of_range).astype("Int64")

    # duplicate ticket ids (same ticket, dates re-formatted)
    dup_ids = df["ticket_id"].duplicated(keep="first")
    grp = df[df["ticket_id"].isin(df.loc[dup_ids, "ticket_id"])]
    other_cols = [c for c in df.columns if c not in ("ticket_created_at", "ticket_resolved_at")]
    conflicts = grp.groupby("ticket_id")[other_cols].nunique(dropna=False).gt(1).any(axis=1).sum()
    record(ds, "ticket_id",
           f"Same ticket_id repeated with timestamps written in another format "
           f"({conflicts} with any other field differing)",
           dup_ids.sum(), "De-duplicated on ticket_id, kept first occurrence",
           examples_of(df.loc[dup_ids, "ticket_id"]))
    df = drop_rows(df, dup_ids, ds, "duplicate ticket_id (re-formatted copy)")

    # validation of the already-clean columns
    for col in ["issue_category", "channel", "resolution_status"]:
        untidy = df[col] != df[col].str.strip()
        if untidy.any():
            raise ValueError(f"Untidy {col} values: {df.loc[untidy, col].unique()}")
        record(ds, col, f"Validated {df[col].nunique()} distinct values - no spelling variants", 0, "No change")

    # open / resolved consistency
    is_open = df["resolution_status"].str.startswith("Open")
    inconsistent = (is_open & df["ticket_resolved_at"].notna()) | (~is_open & df["ticket_resolved_at"].isna())
    record(ds, "ticket_resolved_at / resolution_status",
           f"Open tickets have no resolved time ({is_open.sum()} open) - checked consistency",
           inconsistent.sum(), "No change needed (status and timestamp agree)")
    df["is_open"] = is_open

    # resolution time
    hours = (df["ticket_resolved_at"] - df["ticket_created_at"]).dt.total_seconds() / 3600
    negative = hours < 0
    record(ds, "ticket_resolved_at",
           f"Resolved timestamp earlier than created timestamp "
           f"(negative duration, {hours[negative].max():.1f}h to {hours[negative].min():.1f}h)",
           negative.sum(),
           "Flagged invalid_duration=True; resolution_hours set to missing and excluded from SLA metrics",
           examples_of(df.loc[negative, "ticket_id"]))
    df["invalid_duration"] = negative
    df["resolution_hours"] = hours.where(~negative)

    # free-text
    masked = df["customer_message"].str.contains(r"\[ORDER-REF\]", regex=True)
    record(ds, "customer_message",
           "Messages contain masked tokens [ORDER-REF] and much of the text is unrelated to e-commerce "
           "(appears to be recycled complaint text)", masked.sum(),
           "Left unchanged; not used for quantitative answers")

    # foreign-key check after fixing
    orphan = ~df["order_id"].isin(orders["order_id"])
    record(ds, "order_id", "Tickets whose order_id is not in cleaned orders (after fix)", orphan.sum(),
           "None - every ticket joins to an order" if orphan.sum() == 0 else "Kept, flagged")
    cust_mismatch = df.merge(orders[["order_id", "customer_id"]], on="order_id", suffixes=("", "_o"))
    cust_mismatch = (cust_mismatch["customer_id"] != cust_mismatch["customer_id_o"]).sum()
    record(ds, "customer_id", "Ticket customer_id differs from the order's customer_id", cust_mismatch,
           "No change needed")

    log.info(f"support_tickets: {raw_rows} raw -> {len(df)} clean rows")
    return df.sort_values("ticket_id").reset_index(drop=True), raw_rows


# --------------------------------------------------------------------------------------
# SOP refund rules
# --------------------------------------------------------------------------------------
LATE_VOUCHER = 100.0


def apply_sop_rules(t: pd.DataFrame) -> pd.DataFrame:
    """Return per-ticket: expected outcome under the SOP, rules broken and money over-paid."""
    amt = t["order_amount"]
    refund = t["refund_amount"]
    late = t["resolution_hours"] > 24
    voucher = np.where(late, LATE_VOUCHER, 0.0)

    r3 = t["is_cod"] & t["delivery_status"].eq("CANCELLED_BEFORE_SHIP") & (refund > 0)
    r2 = t["resolution_status"].eq("Resolved - Replacement Sent") & (refund > 0)
    r4 = refund > amt + LATE_VOUCHER
    r1_voucher = (refund > amt) & (refund <= amt + LATE_VOUCHER) & ~late
    r1_delayed = t["delivery_status"].eq("DELAYED_IN_TRANSIT") & (refund > LATE_VOUCHER)

    excess = pd.DataFrame({
        "R3": np.where(r3, refund, 0.0),                                   # should have been 0
        "R2": np.where(r2, refund, 0.0),                                   # replacement => cash 0
        "R4": np.where(r4, refund - (amt + LATE_VOUCHER), 0.0),            # over the hard cap
        "R1_voucher": np.where(r1_voucher, refund - amt, 0.0),             # +100 without >24h
        "R1_delayed": np.where(r1_delayed, refund - LATE_VOUCHER, 0.0),    # delayed: voucher only
    }, index=t.index)

    labels = {
        "R3": "Rule 3: COD cancelled-before-ship refunded",
        "R2": "Rule 2: replacement AND cash refund",
        "R4": "Rule 4: refund above order_amount + ₹100",
        "R1_voucher": "Rule 1: ₹100 late voucher without >24h resolution",
        "R1_delayed": "Rule 1: delayed order refunded beyond ₹100 voucher",
    }
    flags = excess.gt(0)
    t = t.copy()
    t["is_late_resolution"] = late
    t["max_allowed_refund"] = amt + voucher
    t["violated_rules"] = flags.apply(lambda r: "; ".join(labels[k] for k, v in r.items() if v), axis=1)
    t["primary_violation"] = flags.idxmax(axis=1).map(labels).where(flags.any(axis=1), "")
    t["is_policy_violation"] = flags.any(axis=1)
    # rules can overlap on one ticket; the money lost is the largest single over-payment, never the sum
    t["excess_refund"] = excess.max(axis=1)
    for k in excess:
        t[f"excess_{k}"] = excess[k]
    return t


# --------------------------------------------------------------------------------------
def main():
    orders, orders_raw = clean_orders()
    tickets, tickets_raw = clean_tickets(orders)

    order_cols = ["order_id", "customer_city", "order_date", "order_month", "product_category", "courier_partner",
                  "order_amount", "shipping_fee", "payment_method", "is_cod", "delivery_status", "is_lost_or_delayed"]
    tickets = tickets.merge(orders[order_cols], on="order_id", how="left", validate="many_to_one")
    tickets = apply_sop_rules(tickets)

    # final integrity checks
    assert tickets["ticket_id"].is_unique
    assert tickets["order_amount"].notna().all(), "every ticket must join to an order"
    assert tickets["csat_score"].dropna().between(1, 5).all()
    assert (tickets["resolution_hours"].dropna() >= 0).all()
    assert (tickets["refund_amount"] >= 0).all()

    orders.to_csv(CLEAN / "orders_clean.csv", index=False)
    tickets.to_csv(CLEAN / "support_tickets_clean.csv", index=False)
    violations = tickets[tickets["is_policy_violation"]]
    violations.drop(columns=["customer_message"]).to_csv(CLEAN / "refund_violations.csv", index=False)
    pd.concat(REMOVED, ignore_index=True).to_csv(CLEAN / "removed_rows.csv", index=False)

    # reconciliation rows
    removed = pd.concat(REMOVED)
    for ds, raw_n, clean_n in [("orders", orders_raw, len(orders)), ("support_tickets", tickets_raw, len(tickets))]:
        by_reason = removed[removed["dataset"] == ds]["removal_reason"].value_counts()
        detail = " - ".join(f"{n} {r}" for r, n in by_reason.items())
        record(ds, "row count", f"Reconciliation: {raw_n} raw - {detail} = {clean_n} clean rows",
               raw_n - clean_n, "Removed rows saved to data/clean/removed_rows.csv")

    log_df = pd.DataFrame(CLEANING_LOG)
    log_df.to_csv(LOGS / "cleaning_log.csv", index=False)
    with open(LOGS / "cleaning_log.md", "w", encoding="utf-8") as f:
        f.write("# Data Cleaning Log\n\nRow counts are on the final de-duplicated rows, so they reconcile "
                "with the clean files.\n\n")
        for ds, g in log_df.groupby("dataset", sort=False):
            f.write(f"## {ds}\n\n| # | Column | Issue found | Rows | Fix |\n|---|---|---|---|---|\n")
            for r in g.itertuples():
                f.write(f"| {r.step} | {r.column} | {r.issue} | {r.rows_affected:,} | {r.fix} |\n")
            f.write("\n")

    log.info(f"Wrote {CLEAN / 'orders_clean.csv'} ({len(orders)} rows)")
    log.info(f"Wrote {CLEAN / 'support_tickets_clean.csv'} ({len(tickets)} rows)")
    log.info(f"Wrote {CLEAN / 'refund_violations.csv'} ({len(violations)} rows)")
    log.info(f"Cleaning log: {len(log_df)} entries -> logs/cleaning_log.csv, logs/cleaning_log.md")


if __name__ == "__main__":
    main()
