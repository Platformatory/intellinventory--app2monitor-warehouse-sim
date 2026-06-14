<h1>Devlog</h1>

---

**Relevant files**:

- [`Home.py`](./sim_monitor_app/Home.py)
- [`nav.py`](./sim_monitor_app/nav.py)
- [`db.py`](./sim_monitor_app/db.py)
- [`pages/1_Live_Monitor.py`](./sim_monitor_app/pages/1_Live_Monitor.py)
- [`pages/2_Decision_Log.py`](./sim_monitor_app/pages/2_Decision_Log.py)
- [`pages/3_Event_Log.py`](./sim_monitor_app/pages/3_Event_Log.py)
- [`pages/4_Query.py`](./sim_monitor_app/pages/4_Query.py)
- [`app.yaml`](./sim_monitor_app/app.yaml)
- [`requirements.txt`](./sim_monitor_app/requirements.txt)

---

**Contents**:

- [1. Problem / Need](#1-problem--need)
- [2. Conceptual Solution](#2-conceptual-solution)
- [3. Implementation](#3-implementation)
  - [`db.py` - Shared data layer](#dbpy---shared-data-layer)
  - [`nav.py` - Shared sidebar component](#navpy---shared-sidebar-component)
  - [`Home.py` - Landing page](#homepy---landing-page)
  - [`1_Live_Monitor.py` - Charts](#1_live_monitorpy---charts)
  - [`2_Decision_Log.py` - Agent decisions](#2_decision_logpy---agent-decisions)
  - [`3_Event_Log.py` - Event log](#3_event_logpy---event-log)
  - [`4_Query.py` - Free-form SQL](#4_querypy---free-form-sql)
  - [`app.yaml` and `requirements.txt`](#appyaml-and-requirementstxt)
  - [Unity Catalog grants](#unity-catalog-grants)
- [4. Issues](#4-issues)
  - [Issue 1 - App unavailable despite successful deployment](#issue-1---app-unavailable-despite-successful-deployment)
  - [Issue 2 - Duplicate navigation lists](#issue-2---duplicate-navigation-lists)
  - [Issue 3 - `selected_sim_id` not available on non-Home pages](#issue-3---selected_sim_id-not-available-on-non-home-pages)
  - [Issue 4 - Disruption chart mismatch with notebook dashboard](#issue-4---disruption-chart-mismatch-with-notebook-dashboard)
- [5. Resolutions](#5-resolutions)
  - [Resolution 1 - Port mismatch](#resolution-1---port-mismatch)
  - [Resolution 2 - Remove custom nav list](#resolution-2---remove-custom-nav-list)
  - [Resolution 3 - Sim ID selector moved into `render_nav`](#resolution-3---sim-id-selector-moved-into-render_nav)
  - [Resolution 4 - Disruption chart rewritten as area + line](#resolution-4---disruption-chart-rewritten-as-area--line)
- [Completion Status](#completion-status)

---

# 1. Problem / Need

The continuous simulation (see *Running Simulation as a Job*) accumulates data in Delta tables over time. The existing visibility layer - `continuousSim-liveDashboard.py` - is a Databricks notebook that polls those tables and renders matplotlib plots inline. This works for development but is not suitable for demonstration:

- Notebook interfaces are cluttered with cell chrome, execution counts, and output areas
- matplotlib plots are static - no hover, zoom, or pan
- There is no table log view, no event inspection, and no way to run ad-hoc queries against the data during a demo
- The dashboard is tightly coupled to one notebook session; sharing it requires sharing cluster access

The need is a **standalone, presentable monitoring interface** that can be opened in a browser during a screen-share demo, shows live simulation state with rich interactivity, and allows the operator to answer arbitrary questions about the data on the fly.

---

# 2. Conceptual Solution

**Databricks Apps with Streamlit** was chosen as the delivery mechanism. The key considerations:

**Why Databricks Apps over local Streamlit or Grafana?**

The app runs inside the Databricks workspace. Authentication is handled by the Apps runtime - no personal access tokens, no external credential management, no network configuration. The app has native access to the catalog and SQL warehouses without any connector setup. For a screen-share demo this is the path of least friction.

Grafana was considered and rejected: it offers strong out-of-the-box visual quality but requires a running Grafana instance and a Databricks JDBC/ODBC connector. That is operational overhead that adds no demo value here. Streamlit gives full control over layout and interactivity with no additional infrastructure.

**Why not the notebook dashboard?**

The notebook dashboard is retained as a development tool - it is not replaced. The Streamlit app is the demo layer; the notebook is for development iteration. The data contract (Delta tables) is identical for both.

**Architecture: read-only client over Databricks SQL**

The app is a pure read client. It sends SQL statements to a serverless SQL warehouse via `WorkspaceClient.statement_execution` (Databricks SDK) and renders results. No SparkSession. No direct Delta table access from the app process. The app cluster itself is minimal - the real compute is the SQL warehouse.

**Page structure**

Four pages covering the distinct demo use cases:

```
Home            KPI cards, run status, cost breakdown, recent event feed
Live Monitor    Interactive Plotly charts: stock, demand, disruptions, costs
Decision Log    Filterable agent decision table with LLM reasoning inline
Event Log       Paginated, filterable full event log with payload inspector
Query           Free-form SQL with starter queries and table reference
```

---

# 3. Implementation

## `db.py` - Shared data layer

All pages import from a single module. `WorkspaceClient` is instantiated once per session via `@st.cache_resource`. Query results are cached via `@st.cache_data(ttl=30)` so navigating between pages does not re-fire identical SQL. The free-form query page calls `_execute` directly, bypassing cache so results are always fresh.

The warehouse ID is read from the `DATABRICKS_WAREHOUSE_ID` environment variable - set in `app.yaml` - and never hardcoded.

## `nav.py` - Shared sidebar component

Every page calls `render_nav(current="<key>")` immediately after `st.set_page_config`. This renders:

- The app wordmark
- A sim ID `st.selectbox` that writes to `st.session_state["selected_sim_id"]`
- A divider and catalog caption

**Design decision: sim ID selector lives in `nav.py`, not in `Home.py`.**

`st.session_state` only persists across pages if the key has been set in the current session. Since Databricks Apps pages are independently loadable - a user can deep-link directly to `/Decision_Log` - the selector must be present on every page. Putting it in `nav.py` ensures `selected_sim_id` is always set before any page logic runs.

**Design decision: no custom CSS.**

An initial implementation used extensive custom HTML/CSS for dark-theme styling (custom KPI cards, event feed rows, coloured nav bar). This was removed entirely. Streamlit's default theme renders cleanly in the Databricks Apps environment and custom CSS injection can cause rendering conflicts with the Apps runtime. All UI is native Streamlit primitives only: `st.metric`, `st.dataframe`, `st.expander`, `st.page_link`, `st.subheader`, etc.

**Design decision: Streamlit's native multi-page nav is used as-is.**

`st.page_link` was initially used to build a custom nav list in the sidebar alongside Streamlit's auto-generated multi-page nav. This produced two duplicate nav lists. The custom list was removed; Streamlit's native list handles page switching. `nav.py` adds only the sim ID selector above it.

## `Home.py` - Landing page

Run status (`🟢 Running` / `🔵 Ended`) is determined by querying the event log for a `SIM_ENDED` row. Four `st.metric` cards show current tick, total cost, reorder count, and stockout event count. A per-item cost breakdown table and a 30-row recent event feed complete the page. Auto-refresh is an opt-in toggle (`streamlit-autorefresh`, 60-second interval) rather than always-on - during a demo, unexpected page re-runs mid-conversation are disruptive.

## `1_Live_Monitor.py` - Charts

Four Plotly charts replace the notebook's matplotlib subplots:

**Chart 1 - Stock levels**: stock on hand (solid) and in transit (dotted) per item. Reorder markers are downward triangles sized proportional to `order_qty`, matching the notebook dashboard.

**Chart 2 - Demand fulfilment**: fulfilled (solid) and unmet demand (dashed) per item.

**Chart 3 - Disruptions**: area chart with `fill="tozeroy"` and a line trace on top, matching the notebook's `ax3.fill_between` + `ax3.plot` pattern exactly. Inactive ticks are plotted as zero rather than omitted, making dormant periods visually explicit. The label format `dis_id (disruption_type)` matches the notebook. This chart was initially implemented as `go.Bar` with active ticks only - a mismatch that was corrected.

**Chart 4 - Costs**: stacked bar per tick (holding, stockout, order, transit loss) with a cumulative cost line on a secondary y-axis.

A tick window slider in the sidebar controls the visible range across all four charts simultaneously.

## `2_Decision_Log.py` - Agent decisions

Filterable by item, decision type, and tick range. Summary metrics (total rows, reorders, holds, units ordered) above the table. Agent reasoning is rendered in `st.expander` blocks - one per decision - showing the LLM's full reasoning text. This is the primary demo surface for demonstrating LLM decision-making quality.

## `3_Event_Log.py` - Event log

Paginated (configurable rows per page: 25/50/100/250). Filterable by event type (multiselect from the full `EVENT_TYPES` set), item, and tick range. Payload is summarised inline as `key: value` pairs truncated at 120 characters. A payload inspector below the table shows the full parsed JSON for any selected `event_id` via `st.json`. This is the deepest diagnostic surface - every disruption, stockout, supply arrival, and cost accrual is accessible here.

## `4_Query.py` - Free-form SQL

Four pre-built starter queries cover the most common demo questions:
- Stockout events by item
- Cost breakdown at latest tick
- Reorder summary by item
- Disruption activation rate

A table reference in the sidebar lists all simulation tables as `st.code` blocks for quick copy-paste. Results are displayed via `st.dataframe` and downloadable as CSV. `_execute` is called directly (not via the cached `query`) so results are always current.

## `app.yaml` and `requirements.txt`

`app.yaml` specifies the Streamlit entry point and the `DATABRICKS_WAREHOUSE_ID` environment variable placeholder. The command includes `--server.headless=true` - required in hosted environments where Streamlit would otherwise attempt to open a browser on the server side.

`requirements.txt` pins `streamlit>=1.35.0` (required for `st.page_link`, introduced in 1.31), `databricks-sdk>=0.28.0`, `plotly>=5.22.0`, `pandas>=2.0.0`, and `streamlit-autorefresh>=1.0.1`.

## Unity Catalog grants

The app's auto-provisioned service principal requires explicit grants. A `sim_monitor_grants.sql` file covers all 21 required statements: `USE CATALOG` at catalog level, `USE SCHEMA` + `SELECT` per table across all four schemas (`tables4ops`, `tables4hist`, `tables4eventlog`, `tables4env`). The SQL warehouse also requires a separate `CAN USE` grant, set in the warehouse permissions UI - a distinct permission layer that is easy to miss.

---

# 4. Issues

## Issue 1 - App unavailable despite successful deployment

After initial deployment the app returned *"The Databricks app you are trying to access is currently unavailable"* despite the deployment log showing success. The app process had started cleanly on port 8501.

## Issue 2 - Duplicate navigation lists

After adding `st.page_link` calls to `render_nav`, the sidebar showed two navigation lists: Streamlit's auto-generated multi-page list (without emojis) and the custom `st.page_link` list (with emojis).

## Issue 3 - `selected_sim_id` not available on non-Home pages

When navigating directly to any page other than Home, `st.session_state.get("selected_sim_id", "")` returned an empty string, causing all queries to fail silently or return no data.

## Issue 4 - Disruption chart mismatch with notebook dashboard

The app rendered disruptions as a `go.Bar` chart using active ticks only. The notebook uses `fill_between` with inactive ticks plotted as zero, which makes dormant disruption periods visually distinct from active ones. The bar chart obscured this information.

---

# 5. Resolutions

## Resolution 1 - Port mismatch

Databricks Apps proxies traffic to the app on port **8080**, not Streamlit's default 8501. The fix was to add `--server.port=8080` to the command in `app.yaml` and add a `.streamlit/config.toml` with `enableCORS = false` and `enableXsrfProtection = false`. The Apps runtime sits behind a proxy that blocks these protections by default.

```toml
[server]
port = 8080
address = "0.0.0.0"
headless = true
enableCORS = false
enableXsrfProtection = false
```

## Resolution 2 - Remove custom nav list

The `st.page_link` calls were removed from `render_nav`. Streamlit's auto-generated nav list is sufficient and correct. `nav.py` now renders only the sim ID selector and supporting labels - no page navigation primitives of its own.

## Resolution 3 - Sim ID selector moved into `render_nav`

The `st.selectbox` for sim ID selection was moved from `Home.py` into `render_nav`, which is called on every page. Because the selectbox uses `key="selected_sim_id"`, it writes to session state on every page load regardless of entry point. All pages read `st.session_state["selected_sim_id"]` directly (no `.get()` fallback) since `render_nav` guarantees the key is set - or calls `st.stop()` if no simulations exist in the catalog.

## Resolution 4 - Disruption chart rewritten as area + line

`go.Bar` replaced with `go.Scatter(fill="tozeroy")`. A `plot_mag` column is computed before plotting:

```python
df_dis["plot_mag"] = df_dis.apply(
    lambda r: r["effective_magnitude"] if r["is_active"] else 0.0, axis=1
)
```

This matches the notebook's `fill_between` behaviour exactly - inactive ticks render as flat zero sections rather than gaps. The label format `f"{dis_id} ({dis_type})"` and `opacity=0.55` also match the notebook.

---

# Completion Status

```
✓ db.py                     Shared query layer, WorkspaceClient, caching
✓ nav.py                    Sim ID selector, session state, native Streamlit nav
✓ Home.py                   KPI cards, cost table, event feed, auto-refresh toggle
✓ pages/1_Live_Monitor.py   Stock, demand, disruption (area), cost charts
✓ pages/2_Decision_Log.py   Decision table, reasoning expanders
✓ pages/3_Event_Log.py      Paginated event log, payload inspector
✓ pages/4_Query.py          Free-form SQL, starter queries, CSV download
✓ app.yaml                  Entry point, port 8080, warehouse ID env var
✓ requirements.txt          Pinned dependencies
✓ sim_monitor_grants.sql    UC grants for app service principal
```