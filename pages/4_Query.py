'''
pages/4_Query.py

Free-form SQL query interface against the full catalog.
Includes starter queries and a table reference in the sidebar.
'''

import streamlit as st
from nav import render_nav
from db import _execute

st.set_page_config(page_title="Query · Sim Monitor", page_icon="🔍", layout="wide")

CATALOG = "hackathon_of_the_century"

render_nav(current="query")

sim_id = st.session_state["selected_sim_id"]

TABLES = {
    "tables4ops":      ["ops_warehouse_state", "ops_pending_orders",
                        "ops_active_disruptions", "ops_cost_accumulator"],
    "tables4hist":     ["hist_demand_actuals", "hist_reorder_decisions", "hist_cost_by_tick"],
    "tables4eventlog": ["event_log"],
    "tables4env":      ["env_sim_config", "env_item_types", "env_suppliers",
                        "env_consumers", "env_disruption_schedules", "env_demand_patterns"],
}

STARTER_QUERIES = {
    "Stockout events by item": f'''
SELECT item_id, COUNT(*) AS stockout_events
FROM {CATALOG}.tables4eventlog.event_log
WHERE sim_id = '{sim_id}'
  AND event_type = 'STOCKOUT_OCCURRED'
GROUP BY item_id
ORDER BY stockout_events DESC
'''.strip(),

    "Cost breakdown (latest tick)": f'''
SELECT item_id,
       cumulative_holding_cost,
       cumulative_stockout_cost,
       cumulative_order_cost,
       cumulative_transit_loss_cost,
       cumulative_total_cost
FROM {CATALOG}.tables4ops.ops_cost_accumulator
WHERE sim_id = '{sim_id}'
  AND tick = (
    SELECT MAX(tick) FROM {CATALOG}.tables4ops.ops_cost_accumulator
    WHERE sim_id = '{sim_id}'
  )
'''.strip(),

    "Reorder summary by item": f'''
SELECT item_id,
       COUNT(*)        AS reorders,
       SUM(order_qty)  AS total_units,
       AVG(order_qty)  AS avg_qty
FROM {CATALOG}.tables4hist.hist_reorder_decisions
WHERE sim_id = '{sim_id}' AND decision = 'reorder'
GROUP BY item_id
'''.strip(),

    "Disruption activation rate": f'''
SELECT disruption_id, item_id,
       COUNT(*) AS total_ticks,
       SUM(CASE WHEN is_active_this_tick THEN 1 ELSE 0 END) AS active_ticks,
       ROUND(SUM(CASE WHEN is_active_this_tick THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS activation_pct
FROM {CATALOG}.tables4ops.ops_active_disruptions
WHERE sim_id = '{sim_id}'
GROUP BY disruption_id, item_id
'''.strip(),
}

# ── Sidebar: starter queries + table reference ────────────────────────────────

with st.sidebar:
    st.subheader("Starter queries")
    chosen = st.selectbox(
        "Load a query", ["— select —"] + list(STARTER_QUERIES.keys()),
        label_visibility="collapsed",
    )

    st.divider()
    st.subheader("Table reference")
    for schema, tables in TABLES.items():
        st.caption(schema)
        for t in tables:
            st.code(f"{CATALOG}.{schema}.{t}", language=None)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("🔍 Query")
st.caption(f"Full catalog access  ·  `{CATALOG}`")
st.divider()

# ── SQL editor ───────────────────────────────────────────────────────────────

default_sql = (
    STARTER_QUERIES[chosen] if chosen != "— select —"
    else f"SELECT *\nFROM {CATALOG}.tables4ops.ops_warehouse_state\nWHERE sim_id = '{sim_id}'\nLIMIT 20"
)

sql_input = st.text_area("SQL", value=default_sql, height=180, label_visibility="collapsed")

col_run, col_dl, _ = st.columns([1, 1, 6])
run_clicked = col_run.button("▶ Run", type="primary", use_container_width=True)

if run_clicked and sql_input.strip():
    with st.spinner("Running…"):
        df_result = _execute(sql_input.strip())

    if df_result is not None and not df_result.empty:
        st.caption(f"{len(df_result):,} rows  ·  {len(df_result.columns)} columns")
        st.dataframe(df_result, use_container_width=True, hide_index=True, height=480)

        col_dl.download_button(
            "⬇ CSV",
            data      = df_result.to_csv(index=False).encode("utf-8"),
            file_name = "query_result.csv",
            mime      = "text/csv",
            use_container_width = True,
        )
    elif df_result is not None and df_result.empty:
        st.info("Query returned no rows.")
