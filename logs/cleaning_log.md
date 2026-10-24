# Data Cleaning Log

Row counts are on the final de-duplicated rows, so they reconcile with the clean files.

## orders

| # | Column | Issue found | Rows | Fix |
|---|---|---|---|---|
| 1 | order_id / customer_id | Synthetic test records (ORD-999xxx, CUST-TESTxx, amount -999.00, all CANCELLED_BEFORE_SHIP) | 45 | Removed (not real customer orders) |
| 2 | all columns | Exact duplicate rows | 22 | Removed, kept first occurrence |
| 3 | product_category | 12 spelling variants (case, trailing spaces, snake_case, synonyms) for 4 real values | 886 | Trimmed, lower-cased and mapped to one canonical label |
| 4 | courier_partner | 8 spelling variants (case, trailing spaces, snake_case, synonyms) for 4 real values | 775 | Trimmed, lower-cased and mapped to one canonical label |
| 5 | customer_city | 12 spelling variants (case, trailing spaces, snake_case, synonyms) for 6 real values | 1,034 | Trimmed, lower-cased and mapped to one canonical label |
| 6 | order_date | Dates stored as text in 9 different formats (plus stray spaces); slash dates are DD/MM/YYYY | 6,200 | Parsed each format explicitly into one datetime (YYYY-MM-DD HH:MM:SS) |
| 7 | order_amount | Amount stored as text with currency symbols/commas (₹1,999.00, INR 699) | 1,113 | Stripped ₹ / INR / commas and converted to a number |
| 8 | order_id | Same order_id repeated with the date written in another format (max date difference 59s, 0 with any other field differing) | 233 | De-duplicated on order_id, kept first occurrence |
| 9 | delivery_status | Validated against allowed values - no issues | 0 | No change |
| 10 | payment_method | Validated against allowed values - no issues | 0 | No change |
| 11 | shipping_fee | Validated numeric values [0, 49, 79, 99] - no issues | 0 | No change |
| 30 | row count | Reconciliation: 6500 raw - 233 duplicate order_id (re-formatted copy) - 45 test record - 22 exact duplicate row = 6200 clean rows | 300 | Removed rows saved to data/clean/removed_rows.csv |

## support_tickets

| # | Column | Issue found | Rows | Fix |
|---|---|---|---|---|
| 12 | all columns | Exact duplicate rows | 33 | Removed, kept first occurrence |
| 13 | order_id | Malformed order reference (' ord_701234 ', bare '701234', trailing spaces) - 624 tickets could not be joined to orders | 624 | Trimmed, upper-cased, '_'->'-', added missing 'ORD-' prefix |
| 14 | ticket_created_at | Timestamps stored as text in 9 different formats | 5,200 | Parsed each format explicitly into one datetime |
| 15 | ticket_resolved_at | Timestamps stored as text in 9 different formats | 4,618 | Parsed each format explicitly into one datetime |
| 16 | refund_amount | Refund stored as text with ₹ / 'Rs.' / commas | 1,120 | Stripped symbols and converted to number |
| 17 | refund_amount | Missing refund written as blank or 'NIL' (only on statuses: Open - Awaiting Courier Update, Resolved - No Refund (Explanation), Resolved - Replacement Sent) | 562 | Set to ₹0 - none of these statuses pays a cash refund |
| 18 | csat_score | CSAT outside the 1-5 scale (99, -1) | 30 | Set to missing (invalid survey response) |
| 19 | csat_score | CSAT blank (customer did not rate) | 2,213 | Kept as missing - excluded from average, not treated as 0 |
| 20 | csat_score | Valid CSAT ratings (1-5) used for the average | 2,957 | Average CSAT is computed on these rows only |
| 21 | ticket_id | Same ticket_id repeated with timestamps written in another format (0 with any other field differing) | 317 | De-duplicated on ticket_id, kept first occurrence |
| 22 | issue_category | Validated 5 distinct values - no spelling variants | 0 | No change |
| 23 | channel | Validated 4 distinct values - no spelling variants | 0 | No change |
| 24 | resolution_status | Validated 5 distinct values - no spelling variants | 0 | No change |
| 25 | ticket_resolved_at / resolution_status | Open tickets have no resolved time (582 open) - checked consistency | 0 | No change needed (status and timestamp agree) |
| 26 | ticket_resolved_at | Resolved timestamp earlier than created timestamp (negative duration, -2.9h to -17.6h) | 38 | Flagged invalid_duration=True; resolution_hours set to missing and excluded from SLA metrics |
| 27 | customer_message | Messages contain masked tokens [ORDER-REF] and much of the text is unrelated to e-commerce (appears to be recycled complaint text) | 3,691 | Left unchanged; not used for quantitative answers |
| 28 | order_id | Tickets whose order_id is not in cleaned orders (after fix) | 0 | None - every ticket joins to an order |
| 29 | customer_id | Ticket customer_id differs from the order's customer_id | 0 | No change needed |
| 31 | row count | Reconciliation: 5550 raw - 317 duplicate ticket_id (re-formatted copy) - 33 exact duplicate row = 5200 clean rows | 350 | Removed rows saved to data/clean/removed_rows.csv |

