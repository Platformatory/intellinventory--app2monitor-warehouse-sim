'''
sim_monitor_app/Home.py

Landing page for the Simulation Monitor.
- KPI cards: current tick, run status, total cost, reorders, stockout ticks
- Per-item cost breakdown table
- Recent event feed
- Auto-refresh toggle

Sim ID selection lives in render_nav() and is available via `st.session_state["selected_sim_id"]` on every page.
'''

import streamlit as st
from streamlit_autorefresh import st_autorefresh
from nav import render_nav
from db import latest_tick, sim_ended, query

st.set_page_config(
    page_title            = "Sim Monitor",
    page_icon             = "⬡",
    layout                = "wide",
    initial_sidebar_state = "expanded",
)

CATALOG = "hackathon_of_the_century"

render_nav(current="home")

sim_id = st.session_state["selected_sim_id"]

# ── Auto-refresh ──────────────────────────────────────────────────────────────

with st.sidebar:
    auto_refresh = st.toggle("Auto-refresh (60s)", value=False)
    if auto_refresh:
        st_autorefresh(interval=60_000, key="home_refresh")

# ── Header ────────────────────────────────────────────────────────────────────

is_ended = sim_ended(CATALOG, sim_id)
max_tick = latest_tick(CATALOG, sim_id)
status   = "🔵 Ended" if is_ended else "🟢 Running"

st.title(f"⬡ {sim_id}")
st.caption(f"{status}  ·  Last tick: {max_tick if max_tick is not None else '—'}")
st.divider()

# ── KPI metrics ───────────────────────────────────────────────────────────────

df_accum = query(f'''
    SELECT ca.*
    FROM {CATALOG}.tables4ops.ops_cost_accumulator ca
    INNER JOIN (
        SELECT item_id, MAX(tick) AS max_tick
        FROM {CATALOG}.tables4ops.ops_cost_accumulator
        WHERE sim_id = '{sim_id}'
        GROUP BY item_id
    ) latest ON ca.item_id = latest.item_id AND ca.tick = latest.max_tick
    WHERE ca.sim_id = '{sim_id}'
''')

total_cost = df_accum["cumulative_total_cost"].astype(float).sum() if not df_accum.empty else 0.0

df_reorders = query(f'''
    SELECT COUNT(*) AS n FROM {CATALOG}.tables4hist.hist_reorder_decisions
    WHERE sim_id = '{sim_id}' AND decision = 'reorder'
''')
n_reorders = int(df_reorders["n"].iloc[0]) if not df_reorders.empty else 0

df_stockouts = query(f'''
    SELECT COUNT(*) AS n FROM {CATALOG}.tables4eventlog.event_log
    WHERE sim_id = '{sim_id}' AND event_type = 'STOCKOUT_OCCURRED'
''')
n_stockouts = int(df_stockouts["n"].iloc[0]) if not df_stockouts.empty else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Current Tick",    max_tick if max_tick is not None else "—")
col2.metric("Total Cost",      f"£{total_cost:,.2f}")
col3.metric("Reorders Placed", f"{n_reorders:,}")
col4.metric("Stockout Events", f"{n_stockouts:,}")

st.divider()

# ── Per-item cost breakdown ───────────────────────────────────────────────────

st.subheader("Cost breakdown by item")
if not df_accum.empty:
    df_display = df_accum[[
        "item_id", "cumulative_holding_cost", "cumulative_stockout_cost",
        "cumulative_order_cost", "cumulative_transit_loss_cost", "cumulative_total_cost"
    ]].copy()
    df_display.columns = ["Item", "Holding", "Stockout", "Order", "Transit Loss", "Total"]
    for col in df_display.columns[1:]:
        df_display[col] = df_display[col].astype(float).map("£{:,.2f}".format)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
else:
    st.info("No cost data yet.")

st.divider()

# ── Recent event feed ─────────────────────────────────────────────────────────

st.subheader("Recent events")
df_events = query(f'''
    SELECT tick, event_type, item_id, payload, logged_at
    FROM {CATALOG}.tables4eventlog.event_log
    WHERE sim_id = '{sim_id}'
    ORDER BY logged_at DESC
    LIMIT 30
''')

if df_events.empty:
    st.info("No events yet.")
else:
    df_events["item_id"] = df_events["item_id"].fillna("—")
    df_events["payload"] = df_events["payload"].astype(str).str[:120]
    df_events.columns    = ["Tick", "Event Type", "Item", "Payload", "Logged At"]
    st.dataframe(df_events, use_container_width=True, hide_index=True)
