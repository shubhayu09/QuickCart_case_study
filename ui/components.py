"""
Reusable UI building blocks. Each one renders HTML styled by ui/styles.css, so the look can change
without touching dashboard logic.
"""
from contextlib import contextmanager
from html import escape
from pathlib import Path

import streamlit as st

from ui.theme import ACCENTS, PLOTLY_CONFIG

_CSS = Path(__file__).with_name("styles.css")


def _html(markup: str):
    st.markdown(markup, unsafe_allow_html=True)


def inject_css():
    """Call once at the top of every run: loads the stylesheet and resets per-run card keys."""
    _card_counter["n"] = 0
    _html(f"<style>{_CSS.read_text(encoding='utf-8')}</style>")


# ---- Page furniture ------------------------------------------------------------------
def hero(title: str, subtitle: str, eyebrow: str = "", chips: list[str] | None = None):
    chip_html = "".join(f'<span class="chip">{escape(c)}</span>' for c in chips or [])
    _html(f"""
<div class="qc-hero">
  <div class="eyebrow">{escape(eyebrow)}</div>
  <h1>{escape(title)}</h1>
  <div class="sub">{escape(subtitle)}</div>
  <div class="chips">{chip_html}</div>
</div>""")


def section(kicker: str, title: str, description: str = ""):
    _html(f"""
<div class="qc-section">
  <div class="kicker">{escape(kicker)}</div>
  <h2>{escape(title)}</h2>
  <p>{escape(description)}</p>
</div>""")


def answer(text_html: str, badge: str = "Answer"):
    """Highlighted answer to one of the brief's questions. text_html may contain <b>."""
    _html(f'<div class="qc-answer"><span class="badge">{escape(badge)}</span>'
          f'<div class="text">{text_html}</div></div>')


def note(text_html: str):
    _html(f'<div class="qc-note">{text_html}</div>')


# ---- KPI cards -----------------------------------------------------------------------
def icon(name: str) -> str:
    """Material Symbols icon by name (https://fonts.google.com/icons), e.g. icon('inventory_2')."""
    return f'<span class="qc-icon">{escape(name)}</span>'


def kpi(label: str, value: str, note_text: str = "", icon_name: str = "", accent: str = "blue", alert: bool = False) -> str:
    """Returns the HTML for one KPI card (render several at once with kpi_row). icon_name is a Material Symbol."""
    bg, fg = ACCENTS.get(accent, ACCENTS["blue"])
    icon_html = f'<div class="icon" style="background:{bg};color:{fg}">{icon(icon_name)}</div>' if icon_name else ""
    note_html = f'<div class="note">{escape(note_text)}</div>' if note_text else ""
    return (f'<div class="qc-kpi{" alert" if alert else ""}"><div class="top">{icon_html}'
            f'<div class="label">{escape(label)}</div></div><div class="value">{escape(value)}</div>{note_html}</div>')


def kpi_row(cards: list[str], cols: int | None = None):
    """Grid of KPI cards; `cols` cards per row on wide screens (defaults to all in one row), fewer on narrow ones."""
    n = cols or len(cards)
    _html(f'<div class="qc-kpi-wrap"><div class="qc-kpi-grid" data-cols="{n}" style="--cols:{n}">'
          f'{"".join(cards)}</div></div>')


# ---- Cards ---------------------------------------------------------------------------
_card_counter = {"n": 0}


@contextmanager
def card(title: str = "", subtitle: str = ""):
    """White rounded card container. Anything rendered inside the `with` block goes in the card."""
    _card_counter["n"] += 1
    with st.container(key=f"card-{_card_counter['n']}"):
        if title:
            _html(f'<div class="qc-card-title">{escape(title)}</div>')
        if subtitle:
            _html(f'<div class="qc-card-sub">{escape(subtitle)}</div>')
        yield


def chart(fig, key: str | None = None, on_select=None):
    """Render a Plotly figure with the shared config. Returns the selection event when on_select is set."""
    # theme=None: use our Plotly template (ui/theme.py) instead of Streamlit's, which repaints the background
    kwargs = dict(width="stretch", config=PLOTLY_CONFIG, key=key, theme=None)
    if on_select:
        kwargs.update(on_select=on_select, selection_mode="points")
    return st.plotly_chart(fig, **kwargs)


def chart_card(fig, title: str = "", subtitle: str = "", key: str | None = None):
    with card(title, subtitle):
        chart(fig, key=key)


# ---- Insights ------------------------------------------------------------------------
def insight(tag: str, big: str, body_html: str, accent: str = "coral"):
    _, fg = ACCENTS.get(accent, ACCENTS["coral"])
    _html(f'<div class="qc-insight"><div class="tag" style="color:{fg}">{escape(tag)}</div>'
          f'<div class="big">{escape(big)}</div><div class="body">{body_html}</div></div>')


def recommendations(items: list[tuple[str, str]]):
    rows = "".join(f'<div class="qc-rec"><div class="n">{i}</div><div><div class="t">{escape(t)}</div>'
                   f'<div class="d">{d}</div></div></div>' for i, (t, d) in enumerate(items, 1))
    _html(f"<div>{rows}</div>")


# ---- Sidebar -------------------------------------------------------------------------
def sidebar_brand(name: str, tagline: str):
    _html(f'<div class="qc-brand"><div class="logo">{escape(name[0])}</div>'
          f'<div><div class="name">{escape(name)}</div><div class="tag">{escape(tagline)}</div></div></div>')


def sidebar_heading(text: str):
    _html(f'<div class="qc-side-h">{escape(text)}</div>')


def metric_guide(items: list[tuple[str, str]]):
    _html("".join(f'<div class="qc-guide-item"><b>{escape(k)}</b><div>{escape(v)}</div></div>' for k, v in items))


# ---- Record lookup -------------------------------------------------------------------
def field_grid(fields: list[tuple[str, str]]):
    """Key/value grid used by the Data Explorer lookup. Values may contain trusted pill HTML."""
    _html('<div class="qc-lookup">' + "".join(
        f'<div class="f"><div class="k">{escape(k)}</div><div class="v">{v}</div></div>' for k, v in fields) + "</div>")


def pill(text: str, color: str, tint: str) -> str:
    return f'<span class="qc-pill" style="background:{tint};color:{color}">{escape(text)}</span>'
