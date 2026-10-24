"""
Chart builders. Each function takes tidy data and returns a styled Plotly figure.
Titles live on the surrounding card (ui.components.card), so figures carry no title of their own.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from ui.formatters import inr
from ui.theme import (BORDER, CARD, DIVERGING_5, FONT_FAMILY, HIGHLIGHT, INK, INK_2, INK_MUTED, MUTED_MARK,
                      ORDINAL, SEQUENTIAL, SERIES)

_TIGHT = dict(l=8, r=16, t=10, b=8)


def _layout(fig, height, **kw):
    # Streamlit's frontend fills an unset background/font with its own theme, so set them on every figure.
    fig.update_layout(height=height, margin=kw.pop("margin", _TIGHT), paper_bgcolor=CARD, plot_bgcolor=CARD,
                      font=dict(family=FONT_FAMILY, color=INK_2, size=12.5), **kw)
    return fig


def hbar(df, y, x, text=None, hover=None, color=None, highlight=None, height=None, x_max=None):
    """Horizontal bar, sorted as given. One colour per series, or emphasis: highlight one, grey the rest."""
    colors = color or SERIES[0]
    if highlight is not None:
        colors = [HIGHLIGHT if v == highlight else MUTED_MARK for v in df[y]]
    fig = go.Figure(go.Bar(
        y=df[y], x=df[x], orientation="h", marker=dict(color=colors, cornerradius=6),
        text=text, textposition="outside", cliponaxis=False, textfont=dict(color=INK, size=12.5),
        hovertemplate=hover or "%{y}<br>%{x:,.1f}<extra></extra>",
    ))
    fig.update_yaxes(autorange="reversed", showgrid=False, ticks="", tickfont=dict(color=INK_2, size=12.5))
    # long category names ("Damaged / Defective Item Received") wrap onto two lines at " / " to free width for bars
    cats = [str(v) for v in df[y]]
    if any(len(c) > 22 and " / " in c for c in cats):
        fig.update_yaxes(tickvals=cats, ticktext=[c.replace(" / ", " /<br>", 1) if len(c) > 22 else c for c in cats])
    margin = dict(_TIGHT)
    if text is not None:
        # value labels sit after the bar end: reserve a right margin sized to the longest label (~7px per char)
        margin["r"] = max(16, int(7 * max(len(str(t)) for t in text)) + 12)
        fig.update_xaxes(range=[0, (x_max or df[x].max()) * 1.04], showticklabels=False, showgrid=False)
    height = height or 60 + 44 * len(df)
    # keep bars ~28px thick even when a tall card holds only a few rows
    row_px = (height - 20) / max(len(df), 1)
    return _layout(fig, height, showlegend=False, margin=margin, bargap=max(0.38, min(0.8, 1 - 28 / row_px)))


def column(x, y, text=None, hover=None, colors=None, height=320, y_title=None, y_range=None):
    fig = go.Figure(go.Bar(x=x, y=y, marker=dict(color=colors or SERIES[0], cornerradius=6),
                           text=text, textposition="outside", cliponaxis=False, textfont=dict(color=INK),
                           hovertemplate=hover or "%{x}<br>%{y:,}<extra></extra>"))
    fig.update_yaxes(title=y_title, range=y_range)
    return _layout(fig, height, showlegend=False)


def donut(labels, values, colors, center_title, center_value, height=320, hover=None):
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.68, sort=False, direction="clockwise",
        marker=dict(colors=colors, line=dict(color=CARD, width=3)),
        textinfo="percent", textposition="inside", insidetextorientation="horizontal",
        textfont=dict(color="white", size=12), domain=dict(x=[0, 0.55]),
        hovertemplate=hover or "%{label}<br>%{value:,} (%{percent})<extra></extra>",
    ))
    fig.add_annotation(text=f"<span style='font-size:12px;color:{INK_MUTED}'>{center_title}</span><br>"
                            f"<b style='font-size:22px;color:{INK}'>{center_value}</b>",
                       showarrow=False, x=0.275, y=0.5, xref="paper", yref="paper")
    return _layout(fig, height, showlegend=True,
                   legend=dict(orientation="v", x=0.6, xanchor="left", y=0.5, yanchor="middle",
                               font=dict(size=12), itemclick="toggleothers"),
                   margin=dict(l=4, r=4, t=10, b=10))


def treemap(df, path, value, color_map, height=380, hover_value_fmt="₹%{value:,.0f}"):
    """Two-level treemap (e.g. category -> city). Click a tile to drill in."""
    labels, parents, values, ids, colors = [], [], [], [], []
    top = df.groupby(path[0], sort=False)[value].sum()
    for k, v in top.items():
        ids.append(k); labels.append(k); parents.append(""); values.append(v); colors.append(color_map.get(k, SERIES[0]))
    sub = df.groupby(path, sort=False)[value].sum()
    for (a, b), v in sub.items():
        ids.append(f"{a}/{b}"); labels.append(b); parents.append(a); values.append(v); colors.append(color_map.get(a, SERIES[0]))
    fig = go.Figure(go.Treemap(
        ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
        marker=dict(colors=colors, line=dict(color=CARD, width=2), cornerradius=6),
        texttemplate="<b>%{label}</b><br>%{customdata}", customdata=[inr(v) for v in values],
        hovertemplate="%{label}<br>" + hover_value_fmt + "<br>%{percentParent:.1%} of parent<extra></extra>",
        textfont=dict(color="white", size=13), pathbar=dict(visible=True, thickness=22),
    ))
    return _layout(fig, height, margin=dict(l=0, r=0, t=26, b=0))


def _inr_ticks(fig, max_value, n=4):
    """Y-axis ticks in ₹ lakh / crore to match the rest of the dashboard (instead of Plotly's 2M, 4M)."""
    raw = max_value / n
    mag = 10 ** np.floor(np.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    vals = [i * step for i in range(int(np.ceil(max_value / step)) + 1)]
    fig.update_yaxes(tickvals=vals, ticktext=["0"] + [inr(v, 0) for v in vals[1:]])


def grouped_columns(x, series: dict, height=320, hover_fmt="₹%{y:,.0f}", y_title=None, inr_axis=True):
    fig = go.Figure()
    for i, (name, values) in enumerate(series.items()):
        fig.add_bar(x=x, y=values, name=name, marker=dict(color=SERIES[i], cornerradius=6),
                    hovertemplate=f"{name} · %{{x}}<br>{hover_fmt}<extra></extra>")
    # category axis: stops Plotly reading labels like "2026-01" as dates and inventing its own date ticks
    fig.update_xaxes(type="category")
    fig.update_yaxes(title=y_title)
    if inr_axis:
        _inr_ticks(fig, max(max(v) for v in series.values()))
    return _layout(fig, height, barmode="group", bargroupgap=0.08, margin=dict(l=8, r=16, t=36, b=8))


def waterfall(steps: list[tuple], height=340, fmt=inr, total_color=SERIES[0], wrap_labels=False):
    """Manual waterfall so every step can carry its own colour.
    steps: (label, value, kind[, colour]) where kind is 'total' (absolute bar from 0) or 'delta' (signed change).
    wrap_labels: break long labels onto short lines so they stay horizontal."""
    if wrap_labels:
        steps = [(_wrap(s[0]),) + tuple(s[1:]) for s in steps]
    labels, bases, heights, colors, texts = [], [], [], [], []
    running = 0.0
    for step in steps:
        label, value, kind = step[:3]
        if kind == "total":
            base, h, running = 0.0, value, value
            col = total_color
        else:
            base = running + min(value, 0)
            h = abs(value)
            running += value
            col = HIGHLIGHT if value < 0 else SERIES[2]
        if len(step) > 3:
            col = step[3]
        labels.append(label); bases.append(base); heights.append(h); colors.append(col)
        texts.append(fmt(value) if kind == "total" else ("−" if value < 0 else "+") + fmt(abs(value)))
    fig = go.Figure(go.Bar(x=labels, y=heights, base=bases, marker=dict(color=colors, cornerradius=6),
                           text=texts, textposition="outside", cliponaxis=False, textfont=dict(color=INK, size=12.5),
                           hovertemplate="%{x}<br>%{text}<extra></extra>"))
    fig.update_yaxes(showticklabels=False, showgrid=False, range=[0, max(b + h for b, h in zip(bases, heights)) * 1.15])
    fig.update_xaxes(tickfont=dict(color=INK_2, size=11.5), tickangle=0)
    return _layout(fig, height, showlegend=False, bargap=0.3)


def _wrap(label: str, width: int = 14) -> str:
    """Insert <br> between words so no line is longer than `width` characters (existing <br>s are kept)."""
    out = []
    for part in label.split("<br>"):
        line, lines = "", []
        for word in part.split(" "):
            plain = len((line + " " + word).replace("<b>", "").replace("</b>", "").strip())
            if line and plain > width:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        lines.append(line)
        out.append("<br>".join(lines))
    return "<br>".join(out)


def bubble_quadrant(df, x, y, size, label, highlight=None, x_title="", y_title="", height=380,
                    x_fmt=".0%", hover=None):
    """Scatter with bubble size, average reference lines and direct labels - one chart for a 2-metric question."""
    colors = [HIGHLIGHT if v == highlight else SERIES[0] for v in df[label]]
    sizes = np.sqrt(df[size] / df[size].max()) * 48
    fig = go.Figure(go.Scatter(
        x=df[x], y=df[y], mode="markers", text=df[label],
        marker=dict(size=sizes, color=colors, opacity=0.8, line=dict(color=CARD, width=2)),
        customdata=df[[size]].values,
        hovertemplate=hover or "%{text}<br>x %{x}<br>y %{y}<extra></extra>",
    ))
    # Direct labels: the highlighted entity on its own, the rest as one group (they usually cluster)
    rest = df[df[label] != highlight] if highlight is not None else df.iloc[0:0]
    for _, r in df[df[label] == highlight].iterrows():
        fig.add_annotation(x=r[x], y=r[y], text=f"<b>{r[label]}</b>", showarrow=False, yshift=-34,
                           font=dict(color=HIGHLIGHT, size=13))
    if len(rest):
        names = ", ".join(rest[label].str.split("_").str[0])
        fig.add_annotation(x=rest[x].mean(), y=rest[y].max(), text=names, showarrow=False, yshift=26,
                           font=dict(color=INK_2, size=12))
    for val, axis in [(df[x].mean(), "x"), (df[y].mean(), "y")]:
        if axis == "x":
            fig.add_vline(x=val, line=dict(color=BORDER, width=1.5))
        else:
            fig.add_hline(y=val, line=dict(color=BORDER, width=1.5))
    fig.add_annotation(text="↗ worse on both", x=1, y=0, xref="paper", yref="paper", showarrow=False,
                       xanchor="right", yanchor="bottom", font=dict(color=INK_MUTED, size=12))
    pad_x = (df[x].max() - df[x].min()) * 0.2 or 0.05
    pad_y = (df[y].max() - df[y].min()) * 0.35 or 5
    fig.update_xaxes(title=x_title, tickformat=x_fmt, range=[df[x].min() - pad_x, df[x].max() + pad_x])
    fig.update_yaxes(title=y_title, range=[df[y].min() - pad_y, df[y].max() + pad_y])
    return _layout(fig, height, showlegend=False, margin=dict(l=8, r=16, t=16, b=8))


def heatmap(z: pd.DataFrame, text_fmt="{:.0%}", hover="%{y} · %{x}<br>%{z}<extra></extra>", height=320,
            colorscale=None, zfmt=None):
    vals = z.values
    text = [[("" if pd.isna(v) else text_fmt.format(v)) for v in row] for row in vals]
    scale = colorscale or [[i / (len(SEQUENTIAL) - 1), c] for i, c in enumerate(SEQUENTIAL)]
    fig = go.Figure(go.Heatmap(
        z=vals, x=list(z.columns), y=list(z.index), text=text, texttemplate="%{text}",
        textfont=dict(size=12.5), colorscale=scale, xgap=3, ygap=3, hovertemplate=hover,
        colorbar=dict(thickness=10, outlinewidth=0, tickformat=zfmt, len=0.9),
    ))
    fig.update_xaxes(showgrid=False, side="top", tickfont=dict(color=INK_2))
    fig.update_yaxes(showgrid=False, autorange="reversed", tickfont=dict(color=INK_2))
    return _layout(fig, height, margin=dict(l=8, r=8, t=30, b=8))


def stacked_share(df: pd.DataFrame, order: list, colors: dict, height=320, hover_label="", legend_below=True):
    """100% stacked horizontal bars. df: index = row labels, columns = segments, values = shares (0-1)."""
    fig = go.Figure()
    for seg in order:
        if seg in df:
            fig.add_bar(y=df.index, x=df[seg], name=str(seg), orientation="h",
                        marker=dict(color=colors[seg], line=dict(color=CARD, width=2)),
                        hovertemplate=f"%{{y}}<br>{hover_label}{seg}: %{{x:.1%}}<extra></extra>")
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK_2))
    legend = dict(orientation="h", y=-0.1, yanchor="top", traceorder="normal") if legend_below \
        else dict(traceorder="normal")
    return _layout(fig, height, barmode="stack", legend=legend, bargap=0.35)


def stacked_hbar(df, y, parts: list[tuple[str, str]], total_col=None, height=300, x_fmt=".0%"):
    """Horizontal stacked bar of absolute parts (e.g. lost rate + delayed rate) with the total labelled at the end.
    parts: [(column, legend name), ...]"""
    fig = go.Figure()
    for i, (col, name) in enumerate(parts):
        fig.add_bar(y=df[y], x=df[col], name=name, orientation="h",
                    marker=dict(color=SERIES[i], line=dict(color=CARD, width=2)),
                    hovertemplate=f"%{{y}}<br>{name}: %{{x:{x_fmt}}}<extra></extra>")
    if total_col:
        fig.add_scatter(y=df[y], x=df[total_col], mode="text", text=[f"{v:{x_fmt}}" for v in df[total_col]],
                        textposition="middle right", textfont=dict(color=INK, size=12.5), showlegend=False,
                        hoverinfo="skip", cliponaxis=False)
        fig.update_xaxes(range=[0, df[total_col].max() * 1.22])
    fig.update_xaxes(tickformat=x_fmt)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=INK_2))
    return _layout(fig, height, barmode="stack", legend=dict(traceorder="normal"),
                   margin=dict(l=8, r=16, t=36, b=8), bargap=0.38)


def likert(df: pd.DataFrame, height=300):
    """Diverging 1-5 rating bars per row. df: index = rows, columns 1..5, values = shares."""
    return stacked_share(df, [1, 2, 3, 4, 5], dict(zip([1, 2, 3, 4, 5], DIVERGING_5)), height=height,
                         hover_label="CSAT ")


def histogram(values, threshold=None, threshold_label="", bin_size=4, height=320, x_title="", y_title=""):
    fig = go.Figure(go.Histogram(x=values, xbins=dict(size=bin_size),
                                 marker=dict(color=SERIES[0], line=dict(color=CARD, width=1.5)),
                                 hovertemplate="%{x} h<br>%{y:,} tickets<extra></extra>"))
    if threshold is not None:
        fig.add_vrect(x0=threshold, x1=max(values.max(), threshold), fillcolor=HIGHLIGHT, opacity=0.06, line_width=0)
        fig.add_vline(x=threshold, line=dict(color=HIGHLIGHT, width=1.5))
        fig.add_annotation(x=threshold, y=1, yref="paper", text=threshold_label, showarrow=False,
                           xanchor="left", xshift=6, font=dict(color=HIGHLIGHT, size=12))
    fig.update_xaxes(title=x_title)
    fig.update_yaxes(title=y_title)
    return _layout(fig, height, showlegend=False, bargap=0.05)


def trend(df: pd.DataFrame, x: str, series: list[str], names: list[str], height=320, y_title=""):
    """Multi-line time series with unified hover and a range slider."""
    fig = go.Figure()
    for i, (col, name) in enumerate(zip(series, names)):
        fig.add_scatter(x=df[x], y=df[col], name=name, mode="lines", line=dict(color=SERIES[i], width=2),
                        hovertemplate=f"{name}: %{{y:,.1f}}<extra></extra>")
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.08, bgcolor="#FAFAFA"), showgrid=False)
    fig.update_yaxes(title=y_title)
    return _layout(fig, height, margin=dict(l=8, r=16, t=36, b=8))


def sankey(df: pd.DataFrame, stages: list[str], stage_colors: list[dict] | None = None, height=440):
    """Flow of records across categorical stages (e.g. delivery status -> issue -> resolution)."""
    labels, index = [], {}
    node_colors = []
    for s_i, stage in enumerate(stages):
        for v in df[stage].dropna().unique():
            key = (stage, v)
            index[key] = len(labels)
            labels.append(str(v))
            cmap = (stage_colors or [{}] * len(stages))[s_i]
            node_colors.append(cmap.get(v, "#B8B8B2"))
    src, tgt, val, link_colors = [], [], [], []
    for a, b in zip(stages[:-1], stages[1:]):
        flows = df.groupby([a, b]).size()
        for (va, vb), n in flows.items():
            src.append(index[(a, va)]); tgt.append(index[(b, vb)]); val.append(n)
            c = node_colors[index[(a, va)]].lstrip("#")
            link_colors.append(f"rgba({int(c[0:2], 16)},{int(c[2:4], 16)},{int(c[4:6], 16)},0.28)")
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, color=node_colors, pad=14, thickness=14, line=dict(color=CARD, width=1),
                  hovertemplate="%{label}<br>%{value:,} tickets<extra></extra>"),
        link=dict(source=src, target=tgt, value=val, color=link_colors,
                  hovertemplate="%{source.label} → %{target.label}<br>%{value:,} tickets<extra></extra>"),
        textfont=dict(color=INK, size=12, family="Inter, system-ui, sans-serif"),
    ))
    return _layout(fig, height, margin=dict(l=8, r=8, t=10, b=10))


def ordinal_columns(x, y, n=None, height=320, y_range=(1, 5), y_title=""):
    """Columns for ordered buckets (light -> dark ordinal ramp)."""
    fig = go.Figure(go.Bar(x=x, y=y, marker=dict(color=ORDINAL[:len(x)], cornerradius=6),
                           text=[f"{v:.2f}" for v in y], textposition="outside", cliponaxis=False,
                           textfont=dict(color=INK, size=13), customdata=n,
                           hovertemplate="%{x}<br>Avg CSAT %{y:.2f}<br>%{customdata:,} ratings<extra></extra>"))
    fig.update_yaxes(range=list(y_range), title=y_title)
    return _layout(fig, height, showlegend=False)
