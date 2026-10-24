"""Customer-scoped lookups on the cleaned data. The customer view only ever sees its own rows."""
import pandas as pd


class CustomerData:
    def __init__(self, orders: pd.DataFrame, tickets: pd.DataFrame):
        self.orders = orders
        self.tickets = tickets
        # "Now" for ticket ages = the latest timestamp in the dataset (the data is a snapshot)
        self.now = max(tickets["ticket_created_at"].max(), tickets["ticket_resolved_at"].max())

    def exists(self, customer_id: str) -> bool:
        return bool((self.orders["customer_id"] == customer_id).any())

    def orders_of(self, customer_id: str) -> pd.DataFrame:
        return self.orders[self.orders["customer_id"] == customer_id].sort_values("order_date", ascending=False)

    def tickets_of(self, customer_id: str) -> pd.DataFrame:
        return self.tickets[self.tickets["customer_id"] == customer_id]

    def order(self, customer_id: str, order_id: str) -> pd.Series | None:
        """Only returns the order if it belongs to this customer."""
        rows = self.orders[(self.orders["order_id"] == order_id) & (self.orders["customer_id"] == customer_id)]
        return rows.iloc[0] if len(rows) else None

    def order_for_ticket(self, customer_id: str, ticket_id: str) -> pd.Series | None:
        rows = self.tickets[(self.tickets["ticket_id"] == ticket_id) & (self.tickets["customer_id"] == customer_id)]
        return self.order(customer_id, rows.iloc[0]["order_id"]) if len(rows) else None

    def ticket_for(self, order_id: str) -> pd.Series | None:
        rows = self.tickets[self.tickets["order_id"] == order_id]
        return rows.iloc[0] if len(rows) else None

    def profile(self, customer_id: str) -> dict:
        o = self.orders_of(customer_id)
        t = self.tickets_of(customer_id)
        return {
            "orders": len(o),
            "spent": o.loc[o["delivery_status"] != "CANCELLED_BEFORE_SHIP", "order_amount"].sum(),
            "open_tickets": int(t["is_open"].sum()),
            "city": o["customer_city"].iloc[0] if len(o) else "–",
            "since": o["order_date"].min(),
        }

    def demo_customers(self) -> list[tuple[str, str]]:
        """One customer per support scenario, so every rule path can be tried in one click.
        Prefers customers with few orders whose relevant order has no settled ticket yet."""
        o = self.orders.merge(self.tickets[["order_id", "resolution_status", "is_open"]], on="order_id", how="left")
        unsettled = o["resolution_status"].isna() | o["is_open"].fillna(False).astype(bool)
        counts = self.orders.groupby("customer_id").size()
        o["n_orders"] = o["customer_id"].map(counts)
        scenarios = [
            ("Lost order", (o["delivery_status"] == "LOST_IN_TRANSIT") & unsettled),
            ("Delayed order", (o["delivery_status"] == "DELAYED_IN_TRANSIT") & unsettled),
            ("Delivered, damaged item", (o["delivery_status"] == "DELIVERED") & o["resolution_status"].isna()),
            ("COD order cancelled", (o["delivery_status"] == "CANCELLED_BEFORE_SHIP")
             & (o["payment_method"] == "Cash on Delivery (COD)") & o["resolution_status"].isna()),
            ("Returned to seller", (o["delivery_status"] == "RETURNED_TO_SELLER") & unsettled),
            ("Already refunded", o["resolution_status"] == "Resolved - Full Refund Issued"),
        ]
        picks, used = [], set()
        for label, mask in scenarios:
            cand = o[mask & ~o["customer_id"].isin(used)].sort_values(["n_orders", "customer_id"])
            if len(cand):
                cid = cand.iloc[0]["customer_id"]
                used.add(cid)
                picks.append((cid, label))
        return picks
