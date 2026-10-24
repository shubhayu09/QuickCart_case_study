"""
Design tokens: the single place to change colours, fonts, radii and the chart template.

Brand chrome (hero, accents, active states) uses the coral BRAND colours.
Data colours use the validated categorical palette (SERIES), assigned to entities in a fixed order.
"""
import plotly.graph_objects as go
import plotly.io as pio

# ---- Brand / chrome ------------------------------------------------------------------
BRAND = "#FF385C"          # primary accent (Airbnb-style coral)
BRAND_DARK = "#E31C5F"
BRAND_DEEP = "#BD1E59"
BRAND_TINT = "#FFF1F3"

INK = "#222222"            # primary text
INK_2 = "#6A6A6A"          # secondary text
INK_MUTED = "#929292"      # axis labels, captions
BORDER = "#EBEBEB"
CANVAS = "#F7F7F7"         # page background
CARD = "#FFFFFF"           # card surface
GRID = "#EFEFEF"
AXIS = "#DDDDDD"

FONT_FAMILY = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif"
RADIUS = 16

# ---- Data palette (validated categorical order, never cycled) ------------------------
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
MUTED_MARK = "#D3D3CE"     # de-emphasised bars in highlight charts
HIGHLIGHT = BRAND          # the one mark the story is about

# Sequential (single hue, light -> dark) and an ordinal subset that stays visible on white
SEQUENTIAL = ["#f3f8fe", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
ORDINAL = ["#86b6ef", "#3987e5", "#256abf", "#104281"]
# Diverging (red <-> neutral <-> blue) for 1-5 ratings
DIVERGING_5 = ["#e34948", "#f2a3a2", "#d9d8d2", "#86b6ef", "#2a78d6"]

# ---- Domain entities -> fixed colours ------------------------------------------------
COURIERS = ["BlueDart_Air", "Delhivery_Express", "EcomExpress_Surface", "Shadowfax_Local"]
CATEGORIES = ["Electronics", "Fashion & Apparel", "Home & Kitchen", "Beauty & Groceries"]
STATUSES = ["DELIVERED", "DELAYED_IN_TRANSIT", "LOST_IN_TRANSIT", "RETURNED_TO_SELLER", "CANCELLED_BEFORE_SHIP"]
RULES = ["Rule 3: COD cancelled-before-ship refunded", "Rule 2: replacement AND cash refund",
         "Rule 4: refund above order_amount + ₹100", "Rule 1: ₹100 late voucher without >24h resolution",
         "Rule 1: delayed order refunded beyond ₹100 voucher"]
RULE_SHORT = {RULES[0]: "R3 · Refund on Unpaid COD Order", RULES[1]: "R2 · Replacement Plus Refund",
              RULES[2]: "R4 · Refund Above Limit", RULES[3]: "R1a · Bonus Without 24h Delay",
              RULES[4]: "R1b · Delayed Order Refunded"}
# Display names for delivery statuses (the data keeps the raw codes)
STATUS_LABEL = {"DELIVERED": "Delivered", "DELAYED_IN_TRANSIT": "Delayed in Transit", "LOST_IN_TRANSIT": "Lost in Transit",
                "RETURNED_TO_SELLER": "Returned to Seller", "CANCELLED_BEFORE_SHIP": "Cancelled Before Shipping"}

COURIER_COLOR = {c: SERIES[i] for i, c in enumerate(COURIERS)}
CATEGORY_COLOR = {c: SERIES[i] for i, c in enumerate(CATEGORIES)}
STATUS_COLOR = {s: SERIES[i] for i, s in enumerate(STATUSES)}
RULE_COLOR = {r: SERIES[i] for i, r in enumerate(RULES)}

# KPI card accents (icon chip tint + icon colour)
ACCENTS = {
    "blue": ("#EAF2FC", "#2a78d6"),
    "coral": (BRAND_TINT, BRAND),
    "green": ("#E8F6EF", "#128a5f"),
    "amber": ("#FDF4E1", "#b07800"),
    "violet": ("#EFEDFB", "#6250d6"),
    "slate": ("#F0F0EE", "#52514e"),
}

PLOTLY_CONFIG = {"displayModeBar": False, "displaylogo": False}


def register_plotly_template():
    pio.templates["quickcart"] = go.layout.Template(layout=dict(
        font=dict(family=FONT_FAMILY, color=INK_2, size=12.5),
        title=dict(font=dict(color=INK, size=15, family=FONT_FAMILY), x=0, xanchor="left", y=0.97),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=SERIES,
        xaxis=dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=INK_MUTED),
                   title_font=dict(color=INK_2, size=12), automargin=True),
        yaxis=dict(gridcolor=GRID, linecolor=AXIS, zeroline=False, tickfont=dict(color=INK_MUTED),
                   title_font=dict(color=INK_2, size=12), automargin=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color=INK_2, size=12), title_text=""),
        hoverlabel=dict(bgcolor="white", bordercolor=BORDER, font=dict(color=INK, size=13, family=FONT_FAMILY)),
        margin=dict(l=8, r=16, t=48, b=8),
        bargap=0.35,
    ))
    pio.templates.default = "quickcart"
