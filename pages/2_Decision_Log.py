'''
pages/2_Decision_Log.py

Agent decision log: filterable table of hist_reorder_decisions.
Shows decision type, quantities, and agent reasoning inline.
'''

import streamlit as st
import pandas as pd
from nav import render_nav
from db import query, latest_tick

st.set_page_config(page_title="Decision Log · Sim Monitor", page_icon="🧠", layout="wide")

CATALOG = "hackathon_of_the_century"

render_nav(current="decisions")

sim_id = st.session_state["selected_sim_id"]

# ── Sidebar filters ───────────────────────────────────────────────────────────

with st.sidebar:

    max_tick   = latest_tick(CATALOG, sim_id) or 0
    tick_range = st.slider("Tick range", 0, max(max_tick, 1), (0, max_tick))

    decision_filter = st.multiselect(
        "Decision type", options=["reorder", "hold"], default=["reorder", "hold"],
    )

    item_opts   = query(f'''
        SELECT DISTINCT item_id FROM {CATALOG}.tables4hist.hist_reorder_decisions
        WHERE sim_id = '{sim_id}' ORDER BY item_id
    ''')
    item_filter = st.multiselect(
        "Item", options=item_opts["item_id"].tolist() if not item_opts.empty else [],
        default=item_opts["item_id"].tolist() if not item_opts.empty else [],
    )

    show_reasoning = st.toggle("Show agent reasoning", value=True)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("🧠 Decision Log")
st.caption(f"`{sim_id}`")
st.divider()

if not decision_filter or not item_filter:
    st.info("Select at least one decision type and one item in the sidebar.")
    st.stop()

# ── Query ─────────────────────────────────────────────────────────────────────

dec_in  = ", ".join(f"'{d}'" for d in decision_filter)
item_in = ", ".join(f"'{i}'" for i in item_filter)

df = query(f'''
    SELECT tick, item_id, decision, order_qty,
           stock_on_hand_at_decision, stock_in_transit_at_decision,
           agent_reasoning, agent_version, supplier_id
    FROM {CATALOG}.tables4hist.hist_reorder_decisions
    WHERE sim_id   = '{sim_id}'
      AND decision  IN ({dec_in})
      AND item_id   IN ({item_in})
      AND tick      BETWEEN {tick_range[0]} AND {tick_range[1]}
    ORDER BY tick DESC
''')

if df.empty:
    st.info("No decisions match the current filters.")
    st.stop()

# ── Summary metrics ───────────────────────────────────────────────────────────

reorders  = df[df["decision"] == "reorder"]
total_qty = pd.to_numeric(reorders["order_qty"], errors="coerce").sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total rows",    len(df))
col2.metric("Reorders",      len(reorders))
col3.metric("Holds",         len(df) - len(reorders))
col4.metric("Units ordered", f"{int(total_qty):,}")

st.divider()

# ── Decision table ────────────────────────────────────────────────────────────

st.subheader("Decisions")
display_cols = ["tick", "item_id", "decision", "order_qty",
                "stock_on_hand_at_decision", "stock_in_transit_at_decision",
                "supplier_id", "agent_version"]
df_display = df[display_cols].copy()
df_display.columns = ["Tick", "Item", "Decision", "Qty",
                       "Stock On Hand", "In Transit", "Supplier", "Agent"]
st.dataframe(df_display, use_container_width=True, hide_index=True, height=380)

# ── Agent reasoning ───────────────────────────────────────────────────────────

if show_reasoning:
    st.divider()
    st.subheader("Agent reasoning")
    st.caption("Most recent 20 decisions with reasoning")

    df_reason = df[df["agent_reasoning"].notna()].head(20)
    if df_reason.empty:
        st.info("No reasoning text available for the current selection.")
    else:
        for _, row in df_reason.iterrows():
            qty_str = f"  ·  qty={row['order_qty']}" if row["decision"] == "reorder" else ""
            with st.expander(f"t={row['tick']}  ·  {row['item_id']}  ·  {row['decision'].upper()}{qty_str}"):
                st.write(row["agent_reasoning"])
