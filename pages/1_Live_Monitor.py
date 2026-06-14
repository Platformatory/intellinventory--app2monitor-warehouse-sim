"""
pages/1_Live_Monitor.py

Live charts: stock levels, demand fulfilment, disruptions, cost breakdown.
All charts are Plotly - interactive hover, zoom, pan.
Tick window slider controls how many ticks are shown.
"""

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.graph_objects as go
import pandas as pd
from nav import render_nav
from db import query, latest_tick

st.set_page_config(page_title="Live Monitor · Sim Monitor", page_icon="📈", layout="wide")

CATALOG = "hackathon_of_the_century"

render_nav(current="monitor")

# ── Sidebar controls ──────────────────────────────────────────────────────────

sim_id = st.session_state["selected_sim_id"]

with st.sidebar:

    max_tick = latest_tick(CATALOG, sim_id) or 0
    window   = st.slider(
        "Tick window", min_value=10, max_value=max(max_tick, 11), # max_value has to be strictly greater than min_value
        value=min(60, max_tick), step=5,
    )
    min_tick = max(0, max_tick - window)

    auto_refresh = st.toggle("Auto-refresh (60s)", value=False)
    if auto_refresh:
        st_autorefresh(interval=60_000, key="monitor_refresh")

# ── Header ────────────────────────────────────────────────────────────────────

st.title("📈 Live Monitor")
st.caption(f"`{sim_id}`  ·  showing ticks {min_tick}–{max_tick}")
st.divider()

# ── Fetch data ────────────────────────────────────────────────────────────────

df_stock = query(f"""
    SELECT tick, item_id, stock_on_hand, stock_in_transit
    FROM {CATALOG}.tables4ops.ops_warehouse_state
    WHERE sim_id = '{sim_id}' AND tick >= {min_tick}
    ORDER BY tick
""")

df_demand = query(f"""
    SELECT tick, item_id, disrupted_demand, fulfilled_demand, unmet_demand
    FROM {CATALOG}.tables4hist.hist_demand_actuals
    WHERE sim_id = '{sim_id}' AND tick >= {min_tick}
    ORDER BY tick
""")

df_orders = query(f"""
    SELECT tick, item_id, order_qty
    FROM {CATALOG}.tables4hist.hist_reorder_decisions
    WHERE sim_id = '{sim_id}' AND decision = 'reorder' AND tick >= {min_tick}
""")

df_dis = query(f"""
    SELECT tick, item_id, disruption_id, disruption_type, effective_magnitude, is_active_this_tick
    FROM {CATALOG}.tables4ops.ops_active_disruptions
    WHERE sim_id = '{sim_id}' AND tick >= {min_tick}
    ORDER BY tick
""")

df_costs = query(f"""
    SELECT tick, item_id, holding_cost, stockout_cost, order_cost, transit_loss_cost
    FROM {CATALOG}.tables4hist.hist_cost_by_tick
    WHERE sim_id = '{sim_id}' AND tick >= {min_tick}
    ORDER BY tick
""")

if df_stock.empty:
    st.info("No data in selected tick window.")
    st.stop()

# Numeric cast
for df in [df_stock, df_demand, df_costs]:
    if not df.empty:
        for col in df.select_dtypes(include="object").columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except Exception:
                pass

item_ids      = sorted(df_stock["item_id"].unique())
ITEM_COLOURS  = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"]
DIS_COLOURS   = ["#FFA15A", "#FF6692", "#B6E880", "#FF97FF"]

# ── Chart 1: Stock on hand ────────────────────────────────────────────────────

st.subheader("Stock levels")
fig1 = go.Figure()
for i, item in enumerate(item_ids):
    colour  = ITEM_COLOURS[i % len(ITEM_COLOURS)]
    df_item = df_stock[df_stock["item_id"] == item].sort_values("tick")

    fig1.add_trace(go.Scatter(
        x=df_item["tick"], y=df_item["stock_on_hand"].astype(float),
        name=f"{item} on hand", line=dict(color=colour, width=2),
    ))
    fig1.add_trace(go.Scatter(
        x=df_item["tick"], y=df_item["stock_in_transit"].astype(float),
        name=f"{item} in transit",
        line=dict(color=colour, width=1, dash="dot"), opacity=0.5,
    ))

    df_ord = df_orders[df_orders["item_id"] == item] if not df_orders.empty else pd.DataFrame()
    if not df_ord.empty:
        df_ord = df_ord.copy()
        df_ord["order_qty"] = pd.to_numeric(df_ord["order_qty"])
        stock_lookup = df_item.set_index("tick")["stock_on_hand"].astype(float)
        fig1.add_trace(go.Scatter(
            x    = df_ord["tick"],
            y    = [stock_lookup.get(t, 0) for t in df_ord["tick"].astype(int)],
            mode = "markers",
            name = f"{item} reorder",
            marker = dict(
                symbol = "triangle-down", color=colour,
                size   = df_ord["order_qty"].apply(lambda q: max(8, min(20, q / 8))),
            ),
        ))

fig1.update_layout(height=340, margin=dict(l=0, r=0, t=20, b=20))
st.plotly_chart(fig1, use_container_width=True)

# ── Chart 2: Demand fulfilment ────────────────────────────────────────────────

st.subheader("Demand fulfilment")
fig2 = go.Figure()
for i, item in enumerate(item_ids):
    colour  = ITEM_COLOURS[i % len(ITEM_COLOURS)]
    df_item = df_demand[df_demand["item_id"] == item].sort_values("tick") if not df_demand.empty else pd.DataFrame()
    if df_item.empty:
        continue
    fig2.add_trace(go.Scatter(
        x=df_item["tick"], y=df_item["fulfilled_demand"].astype(float),
        name=f"{item} fulfilled", line=dict(color=colour, width=2),
    ))
    fig2.add_trace(go.Scatter(
        x=df_item["tick"], y=df_item["unmet_demand"].astype(float),
        name=f"{item} unmet",
        line=dict(color=colour, width=1.5, dash="dash"),
    ))

fig2.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=20))
st.plotly_chart(fig2, use_container_width=True)

# ── Chart 3: Disruptions ──────────────────────────────────────────────────────
# fill_between area + line on top, inactive ticks plotted as zero so gaps are visually clear rather than omitted entirely.

st.subheader("Disruption activity")
if not df_dis.empty:
    df_dis = df_dis.copy()
    df_dis["effective_magnitude"] = pd.to_numeric(df_dis["effective_magnitude"], errors="coerce").fillna(0)
    df_dis["is_active"]           = df_dis["is_active_this_tick"].astype(str).str.lower() == "true"
    df_dis["plot_mag"]            = df_dis.apply(
        lambda r: r["effective_magnitude"] if r["is_active"] else 0.0, axis=1
    )

    fig3 = go.Figure()
    for j, dis_id in enumerate(sorted(df_dis["disruption_id"].unique())):
        colour   = DIS_COLOURS[j % len(DIS_COLOURS)]
        subset   = df_dis[df_dis["disruption_id"] == dis_id].sort_values("tick")
        dis_type = subset["disruption_type"].iloc[0] if not subset.empty else ""
        label    = f"{dis_id} ({dis_type})"

        # Filled area - matches ax3.fill_between(..., alpha=0.55)
        fig3.add_trace(go.Scatter(
            x          = subset["tick"],
            y          = subset["plot_mag"],
            name       = label,
            fill       = "tozeroy",
            fillcolor  = colour,
            opacity    = 0.55,
            line       = dict(color=colour, width=1.0),
            showlegend = True,
        ))

    fig3.update_layout(
        height = 260,
        margin = dict(l=0, r=0, t=20, b=20),
        yaxis  = dict(title="Effective magnitude"),
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No disruption data in this window.")

# ── Chart 4: Cost stacked bar ─────────────────────────────────────────────────

st.subheader("Cost breakdown per tick")
if not df_costs.empty:
    df_agg = df_costs.groupby("tick")[
        ["holding_cost", "stockout_cost", "order_cost", "transit_loss_cost"]
    ].sum().reset_index()
    for col in ["holding_cost", "stockout_cost", "order_cost", "transit_loss_cost"]:
        df_agg[col] = pd.to_numeric(df_agg[col], errors="coerce").fillna(0)

    fig4 = go.Figure()
    for col, label, colour in [
        ("holding_cost",      "Holding",      "#636EFA"),
        ("stockout_cost",     "Stockout",     "#EF553B"),
        ("order_cost",        "Order",        "#00CC96"),
        ("transit_loss_cost", "Transit Loss", "#AB63FA"),
    ]:
        fig4.add_trace(go.Bar(x=df_agg["tick"], y=df_agg[col], name=label, marker_color=colour))

    df_agg["cumulative"] = df_agg[["holding_cost", "stockout_cost", "order_cost", "transit_loss_cost"]].sum(axis=1).cumsum()
    fig4.add_trace(go.Scatter(
        x=df_agg["tick"], y=df_agg["cumulative"],
        name="Cumulative", line=dict(width=2), yaxis="y2",
    ))
    fig4.update_layout(
        barmode = "stack", height=320,
        margin  = dict(l=0, r=0, t=20, b=20),
        yaxis2  = dict(overlaying="y", side="right", title="Cumulative £"),
    )
    st.plotly_chart(fig4, use_container_width=True)
else:
    st.info("No cost data in this window.")