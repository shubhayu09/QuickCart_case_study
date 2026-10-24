"""Number formatting helpers shared by components and charts."""
import pandas as pd


def inr(x, decimals=2):
    """₹ in Indian units (lakh / crore)."""
    if pd.isna(x):
        return "–"
    if abs(x) >= 1e7:
        return f"₹{x / 1e7:.{decimals}f} Cr"
    if abs(x) >= 1e5:
        return f"₹{x / 1e5:.{decimals}f} L"
    return f"₹{x:,.0f}"


def pct(x, decimals=1):
    return "–" if pd.isna(x) else f"{x:.{decimals}%}"


def hours(x, decimals=1):
    return "–" if pd.isna(x) else f"{x:.{decimals}f} h"


def num(x):
    return "–" if pd.isna(x) else f"{x:,.0f}"
