"""Co-living performance dashboard.

Country -> City -> Building navigation with monthly performance KPIs.
Run with:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import plotly.graph_objects as go
import streamlit as st

import config as cfg
import data

st.set_page_config(
    page_title="Performance Dashboard",
    page_icon="▦",
    layout="wide",
    initial_sidebar_state="expanded",
)

PALETTE = ["#7c5cff", "#2dd4bf", "#fbbf24", "#fb7185", "#60a5fa",
           "#a78bfa", "#34d399", "#f472b6", "#38bdf8", "#c084fc"]


def load_css() -> None:
    css = (Path(__file__).parent / "style.css").read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def money(symbol: str, value: float, decimals: int = 0) -> str:
    return f"{symbol} {value:,.{decimals}f}"


def style_fig(fig: go.Figure, height: int = 320) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#cdd5e8", family="Inter", size=12),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.12, x=0),
        xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zeroline=False),
        yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zeroline=False),
        hoverlabel=dict(bgcolor="#0d1424", bordercolor="#7c5cff",
                        font=dict(color="#e8edf7")),
    )
    return fig


# --------------------------------------------------------------------------- UI
load_css()

with st.sidebar:
    st.markdown(
        '<div class="brand"><span class="dot"></span>Lobby<span '
        'style="color:#7c5cff">Metrics</span></div>'
        '<div class="brand-sub">Co-living performance intelligence</div>',
        unsafe_allow_html=True,
    )

    country = st.selectbox(
        "Country",
        cfg.countries(),
        format_func=lambda c: f"{cfg.flag(c)}  {c}",
    )

    city_opts = ["All cities"] + cfg.cities(country)
    # Default to the first city (not "All cities") so a cold start loads one sheet
    # instead of every city at once.
    city_sel = st.selectbox("City", city_opts, index=1 if len(city_opts) > 1 else 0)

    include_closed = st.checkbox(
        "Include closed / empty buildings", value=False,
        help="Buildings with zero occupied rooms are hidden by default so they "
             "don't inflate vacancy loss.")

    building_sel = "All buildings"
    if city_sel != "All cities":
        _cdf = data.load_city(country, city_sel)
        if not include_closed and not _cdf.empty:
            _cdf = _cdf[_cdf["building"].isin(data.active_buildings(_cdf))]
        b_names = sorted(_cdf["building"].unique())
        building_sel = st.selectbox("Building", ["All buildings"] + b_names)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    if st.button("↻  Refresh data", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    st.markdown(
        "<div class='note' style='margin-top:1.2rem'>Monthly figures. Weekly "
        "rates converted at <b>×4.34524</b>. A room counts as occupied when its "
        "<b>Amount &gt; 0</b>.</div>",
        unsafe_allow_html=True,
    )

sym = cfg.currency(country)

# Resolve scope + dataframe
if city_sel == "All cities":
    scope = "country"
    here = country
    df = data.load_country(country)
elif building_sel == "All buildings":
    scope = "city"
    here = city_sel
    df = data.load_city(country, city_sel)
else:
    scope = "building"
    here = building_sel
    full = data.load_city(country, city_sel)
    df = full[full["building"] == building_sel].reset_index(drop=True)

# Hide closed / empty buildings from aggregates unless explicitly included
if not include_closed and scope in ("country", "city") and not df.empty:
    df = df[df["building"].isin(data.active_buildings(df))].reset_index(drop=True)

# Breadcrumb
crumbs = [country]
if city_sel != "All cities":
    crumbs.append(city_sel)
if scope == "building":
    crumbs.append(building_sel)
crumb_html = '<div class="breadcrumb">'
for i, c in enumerate(crumbs):
    cls = "here" if i == len(crumbs) - 1 else ""
    sep = '<span class="sep">/</span>' if i else ""
    crumb_html += f'{sep}<span class="{cls}">{c}</span>'
crumb_html += "</div>"

scope_label = {"country": "Country view", "city": "City view", "building": "Building view"}[scope]
st.markdown(
    f'<div class="hero">{crumb_html}'
    f'<h1>{here}<span class="scope-pill">{scope_label}</span></h1>'
    f'<p>Monthly performance snapshot · figures in {sym}</p></div>',
    unsafe_allow_html=True,
)

# Empty state
if df is None or df.empty:
    msg = ("Every building here currently has zero occupied rooms. "
           "Turn on <b>Include closed / empty buildings</b> in the sidebar to view them."
           if not include_closed else
           "No Lobby Board data is connected for this selection yet.")
    st.markdown(
        f'<div class="coming"><h2>Nothing to show</h2><p>{msg}</p></div>',
        unsafe_allow_html=True,
    )
    st.stop()

m = data.metrics(df)

# ----------------------------------------------------------------- KPI cards
occ_pct = f"{m['occupancy'] * 100:.1f}%"
cap_pct = f"{m['capture'] * 100:.1f}%"
kpis = [
    ("accent", "Total Market Rent", money(sym, m["market_rent"]), "monthly potential"),
    ("teal", "Collected Rent", money(sym, m["collected"]), "monthly actual"),
    ("accent", "Occupancy", occ_pct, f"{m['occupied']} / {m['rooms']} rooms"),
    ("rose", "Price Optimization Loss", money(sym, m["price_loss"]), "occupied below market"),
    ("amber", "Vacancy Loss", money(sym, m["vacancy_loss"]),
     f"{m['vacant']} vacant · {m['booked']} booked"),
    ("teal", "Revenue Capture", cap_pct, "collected / market"),
]
cards = "".join(
    f'<div class="kpi {c}"><div class="bar"></div>'
    f'<div class="label">{label}</div><div class="value">{val}</div>'
    f'<div class="sub">{sub}</div></div>'
    for c, label, val, sub in kpis
)
st.markdown(f'<div class="kpi-grid">{cards}</div>', unsafe_allow_html=True)


def donut_room_types(scope_df):
    rt = data.by_room_type(scope_df)
    rt = rt[rt["collected"] > 0]
    fig = go.Figure(go.Pie(
        labels=rt["room_type"], values=rt["collected"], hole=0.62,
        marker=dict(colors=PALETTE, line=dict(color="#0d1424", width=2)),
        textinfo="percent", hovertemplate="%{label}<br>%{value:,.0f}<extra></extra>",
    ))
    fig.update_layout(annotations=[dict(
        text="Collected<br>by room type", showarrow=False,
        font=dict(size=12, color="#8b97b3"))])
    return style_fig(fig, 330)


def revenue_bridge(mm, symbol):
    """Waterfall: Market Rent steps down through each loss line to Collected."""
    x = ["Market Rent", "Price opt. loss", "Vacancy (booked)",
         "Vacancy (vacant)", "Collected"]
    y = [mm["market_rent"], -mm["price_loss"], -mm["booked_loss"],
         -mm["vacant_loss"], 0]
    measure = ["absolute", "relative", "relative", "relative", "total"]
    labels = [mm["market_rent"], mm["price_loss"], mm["booked_loss"],
              mm["vacant_loss"], mm["collected"]]
    fig = go.Figure(go.Waterfall(
        orientation="v", x=x, y=y, measure=measure,
        text=[money(symbol, v) for v in labels], textposition="outside",
        textfont=dict(color="#cdd5e8"),
        connector={"line": {"color": "rgba(255,255,255,0.18)"}},
        decreasing={"marker": {"color": "#fb7185"}},
        increasing={"marker": {"color": "#fbbf24"}},
        totals={"marker": {"color": "#2dd4bf"}},
        hovertemplate="%{x}: %{text}<extra></extra>",
    ))
    fig.update_yaxes(tickprefix=f"{symbol} ")
    fig.update_layout(showlegend=False)
    return style_fig(fig, 320)


# ----------------------------------------------------------------- revenue bridge
st.markdown(
    '<div class="section-title">Revenue bridge '
    '<span class="muted">· market rent = collected + price optimization loss + vacancy loss</span></div>',
    unsafe_allow_html=True)
st.plotly_chart(revenue_bridge(m, sym), width="stretch",
                config={"displayModeBar": False})


# ----------------------------------------------------------------- charts
if scope in ("country", "city"):
    group_col = "city" if scope == "country" else "building"
    g = data.group_kpis(df, group_col).sort_values("collected", ascending=False)

    left, right = st.columns([1.5, 1])
    with left:
        st.markdown(
            f'<div class="section-title">Market vs Collected '
            f'<span class="muted">· per {group_col}</span></div>',
            unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_bar(x=g[group_col], y=g["market_rent"], name="Market Rent",
                    marker_color="rgba(124,92,255,0.55)")
        fig.add_bar(x=g[group_col], y=g["collected"], name="Collected",
                    marker_color="#2dd4bf")
        fig.update_layout(barmode="group")
        st.plotly_chart(style_fig(fig, 340), width="stretch",
                        config={"displayModeBar": False})
    with right:
        st.markdown('<div class="section-title">Revenue mix</div>',
                    unsafe_allow_html=True)
        st.plotly_chart(donut_room_types(df), width="stretch",
                        config={"displayModeBar": False})

    st.markdown(
        f'<div class="section-title">Occupancy & capture '
        f'<span class="muted">· per {group_col}</span></div>',
        unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        go_g = g.sort_values("occupancy")
        fig = go.Figure(go.Bar(
            x=go_g["occupancy"] * 100, y=go_g[group_col], orientation="h",
            marker=dict(color=go_g["occupancy"] * 100, colorscale="Tealgrn",
                        cmin=0, cmax=100),
            text=[f"{v*100:.0f}%" for v in go_g["occupancy"]],
            textposition="auto", hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
        fig.update_layout(xaxis_title="Occupancy %")
        st.plotly_chart(style_fig(fig, 300), width="stretch",
                        config={"displayModeBar": False})
    with c2:
        go_g = g.sort_values("capture")
        fig = go.Figure(go.Bar(
            x=go_g["capture"] * 100, y=go_g[group_col], orientation="h",
            marker=dict(color=go_g["capture"] * 100, colorscale="Purp",
                        cmin=0, cmax=120),
            text=[f"{v*100:.0f}%" for v in go_g["capture"]],
            textposition="auto", hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
        fig.update_layout(xaxis_title="Revenue capture %")
        st.plotly_chart(style_fig(fig, 300), width="stretch",
                        config={"displayModeBar": False})

    # comparison table
    st.markdown(
        f'<div class="section-title">Breakdown <span class="muted">· '
        f'every {group_col}</span></div>', unsafe_allow_html=True)
    tbl = g[[group_col, "rooms", "occupied", "vacant", "market_rent",
             "collected", "price_loss", "vacancy_loss", "occupancy", "capture"]].copy()
    st.dataframe(
        tbl, width="stretch", hide_index=True,
        column_config={
            group_col: st.column_config.TextColumn(group_col.title()),
            "rooms": "Rooms", "occupied": "Occ.", "vacant": "Vac.",
            "market_rent": st.column_config.NumberColumn("Market Rent", format=f"{sym} %.0f"),
            "collected": st.column_config.NumberColumn("Collected", format=f"{sym} %.0f"),
            "price_loss": st.column_config.NumberColumn("Price Opt. Loss", format=f"{sym} %.0f"),
            "vacancy_loss": st.column_config.NumberColumn("Vacancy Loss", format=f"{sym} %.0f"),
            "occupancy": st.column_config.ProgressColumn("Occupancy", format="%.0f%%", min_value=0, max_value=1),
            "capture": st.column_config.ProgressColumn("Capture", format="%.0f%%", min_value=0, max_value=1.2),
        })

else:  # building scope
    note = cfg.building_note(city_sel, here)
    if note:
        st.markdown(
            f'<div class="callout"><span class="ico">⚠</span>'
            f'<span><b>Note</b> · {note}</span></div>',
            unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1.2])
    with c1:
        st.markdown('<div class="section-title">Occupancy</div>', unsafe_allow_html=True)
        fig = go.Figure(go.Pie(
            labels=["Occupied", "Vacant"], values=[m["occupied"], m["vacant"]],
            hole=0.66, marker=dict(colors=["#2dd4bf", "rgba(251,113,133,0.85)"],
                                   line=dict(color="#0d1424", width=2)),
            textinfo="value", hovertemplate="%{label}: %{value}<extra></extra>"))
        fig.update_layout(annotations=[dict(text=f"<b>{occ_pct}</b>", showarrow=False,
                          font=dict(size=20, color="#e8edf7"))])
        st.plotly_chart(style_fig(fig, 300), width="stretch",
                        config={"displayModeBar": False})
    with c2:
        st.markdown('<div class="section-title">Revenue capture</div>', unsafe_allow_html=True)
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=m["capture"] * 100,
            number={"suffix": "%", "font": {"color": "#e8edf7", "size": 30}},
            gauge={"axis": {"range": [0, 120], "tickcolor": "#8b97b3"},
                   "bar": {"color": "#7c5cff"},
                   "bgcolor": "rgba(255,255,255,0.04)",
                   "borderwidth": 0,
                   "steps": [{"range": [0, 70], "color": "rgba(251,113,133,0.18)"},
                             {"range": [70, 100], "color": "rgba(251,191,36,0.16)"},
                             {"range": [100, 120], "color": "rgba(45,212,191,0.18)"}]}))
        st.plotly_chart(style_fig(fig, 300), width="stretch",
                        config={"displayModeBar": False})
    with c3:
        st.markdown('<div class="section-title">Collected by room type</div>', unsafe_allow_html=True)
        rt = data.by_room_type(df)
        fig = go.Figure(go.Bar(
            x=rt["collected"], y=rt["room_type"], orientation="h",
            marker=dict(color=PALETTE[: len(rt)]),
            text=[money(sym, v) for v in rt["collected"]], textposition="auto",
            hovertemplate="%{y}: %{x:,.0f}<extra></extra>"))
        st.plotly_chart(style_fig(fig, 300), width="stretch",
                        config={"displayModeBar": False})

    # room-level table
    st.markdown(
        '<div class="section-title">Rooms <span class="muted">· room-level detail</span></div>',
        unsafe_allow_html=True)
    show = df[["no", "apartment", "room_type", "plan", "resident",
               "market_rent_monthly", "amount_monthly", "occupied"]].copy()
    st.dataframe(
        show, width="stretch", hide_index=True, height=430,
        column_config={
            "no": "No.", "apartment": "Apt", "room_type": "Room Type",
            "plan": "Plan", "resident": "Resident",
            "market_rent_monthly": st.column_config.NumberColumn("Market Rent /mo", format=f"{sym} %.0f"),
            "amount_monthly": st.column_config.NumberColumn("Collected /mo", format=f"{sym} %.0f"),
            "occupied": st.column_config.CheckboxColumn("Occupied"),
        })

st.markdown(
    "<div class='note'>Source: Vancouver Lobby Board (live). "
    "Market Rent is a weekly price converted to monthly (×4.34524). "
    "Four-weekly amounts are converted to monthly the same way; monthly amounts "
    "are used as-is. Occupied = Amount &gt; 0.</div>",
    unsafe_allow_html=True)
