'''
pages/3_Event_Log.py

Full event log viewer: filterable, paginated table of event_log.
Payload shown inline; full JSON expandable per row.
'''

import json
import streamlit as st
from nav import render_nav
from db import query, latest_tick

st.set_page_config(page_title="Event Log · Sim Monitor", page_icon="📋", layout="wide")

CATALOG = "hackathon_of_the_century"

render_nav(current="events")

sim_id = st.session_state["selected_sim_id"]

ALL_EVENT_TYPES = [
    "AGENT_ERROR", "BUDGET_EXHAUSTED", "BUDGET_WARNING", "COST_ACCRUED",
    "DEMAND_DRAWN", "DISRUPTION_ACTIVATED", "DISRUPTION_DEACTIVATED",
    "LEAD_TIME_EXTENDED", "REORDER_HELD", "REORDER_PLACED",
    "SIM_ENDED", "SIM_RESUMED", "SIM_STARTED",
    "STOCKOUT_OCCURRED", "SUPPLY_ARRIVED", "TICK_ENDED", "TICK_STARTED",
    "TRANSIT_LOSS_APPLIED",
]

# ── Sidebar filters ───────────────────────────────────────────────────────────

with st.sidebar:

    max_tick     = latest_tick(CATALOG, sim_id) or 0
    tick_range   = st.slider("Tick range", 0, max(max_tick, 1), (0, max_tick))
    event_filter = st.multiselect("Event types", options=ALL_EVENT_TYPES, default=ALL_EVENT_TYPES)

    item_opts   = query(f'''
        SELECT DISTINCT item_id FROM {CATALOG}.tables4eventlog.event_log
        WHERE sim_id = '{sim_id}' AND item_id IS NOT NULL ORDER BY item_id
    ''')
    item_filter = st.multiselect(
        "Item (blank = all)",
        options = item_opts["item_id"].tolist() if not item_opts.empty else [],
        default = [],
    )

    page_size = st.selectbox("Rows per page", [25, 50, 100, 250], index=1)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("📋 Event Log")
st.caption(f"`{sim_id}`")
st.divider()

if not event_filter:
    st.info("Select at least one event type in the sidebar.")
    st.stop()

# ── Query ─────────────────────────────────────────────────────────────────────

type_in     = ", ".join(f"'{e}'" for e in event_filter)
item_clause = (
    f"AND item_id IN ({', '.join(f'{chr(39)}{i}{chr(39)}' for i in item_filter)})"
    if item_filter else ""
)

df = query(f'''
    SELECT event_id, tick, event_type, item_id, entity_id, payload, logged_at
    FROM {CATALOG}.tables4eventlog.event_log
    WHERE sim_id     = '{sim_id}'
      AND event_type IN ({type_in})
      AND tick       BETWEEN {tick_range[0]} AND {tick_range[1]}
      {item_clause}
    ORDER BY tick DESC, logged_at DESC
''', ttl=15)

if df.empty:
    st.info("No events match the current filters.")
    st.stop()

# ── Pagination ────────────────────────────────────────────────────────────────

total_rows  = len(df)
total_pages = max(1, (total_rows - 1) // page_size + 1)

col_info, col_page = st.columns([4, 1])
col_info.caption(f"{total_rows:,} events  ·  {total_pages} pages")
page = col_page.number_input("Page", min_value=1, max_value=total_pages, value=1, label_visibility="collapsed")

df_page = df.iloc[(page - 1) * page_size : page * page_size].copy()

# ── Parse payload for display ─────────────────────────────────────────────────

def _summarise_payload(raw: str) -> str:
    try:
        d = json.loads(raw)
        return "  ·  ".join(f"{k}: {v}" for k, v in d.items() if v is not None)[:120]
    except Exception:
        return str(raw)[:120]

df_page["payload_summary"] = df_page["payload"].apply(_summarise_payload)
df_page["item_id"]         = df_page["item_id"].fillna("—")
df_page["entity_id"]       = df_page["entity_id"].fillna("—")

display = df_page[["tick", "event_type", "item_id", "entity_id", "payload_summary", "logged_at"]].copy()
display.columns = ["Tick", "Event Type", "Item", "Entity", "Payload", "Logged At"]
st.dataframe(display, use_container_width=True, hide_index=True, height=500)

# ── Full payload inspector ────────────────────────────────────────────────────

st.divider()
st.subheader("Payload inspector")
st.caption("Select an event ID to inspect its full payload.")

selected_id = st.selectbox("Event ID", options=df_page["event_id"].tolist(), label_visibility="collapsed")
if selected_id:
    row = df_page[df_page["event_id"] == selected_id].iloc[0]
    st.caption(f"t={row['tick']}  ·  {row['event_type']}  ·  {row['item_id']}")
    try:
        st.json(json.loads(row["payload"]))
    except Exception:
        st.code(row["payload"])
