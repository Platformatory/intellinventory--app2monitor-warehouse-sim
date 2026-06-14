'''
db.py

Databricks SQL query helper for the simulation monitor app.

NOTE:
- Uses StatementExecuteAPI via the Databricks SDK - no SparkSession, no external SQL connector
- Authentication is handled by the Databricks Apps runtime environment automatically

All pages import `query` and `list_sim_ids` from here.
'''

from __future__ import annotations

import os
import pandas as pd
import streamlit as st
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState


# ── Warehouse ─────────────────────────────────────────────────────────────────
# Set DATABRICKS_WAREHOUSE_ID in the app's environment config in the
# Databricks Apps UI, or in app.yaml. Never hardcode here.

def _warehouse_id() -> str:
    wid = os.environ.get("DATABRICKS_WAREHOUSE_ID", "")
    if not wid:
        st.error(
            "DATABRICKS_WAREHOUSE_ID environment variable is not set. "
            "Add it to your Databricks App configuration."
        )
        st.stop()
    return wid


@st.cache_resource
def _client() -> WorkspaceClient:
    '''Shared WorkspaceClient - instantiated once per app session.'''
    return WorkspaceClient()


# ── Core query function ───────────────────────────────────────────────────────

def query(sql: str, ttl: int = 30) -> pd.DataFrame:
    '''
    Execute a SQL statement against the configured warehouse and return a pandas DataFrame.

    Parameters
    ----------
    sql : str
        SQL statement to execute.
    ttl : int
        Cache TTL in seconds. Pass ttl=0 to bypass cache.

    Returns
    -------
    pd.DataFrame
        Query results. Empty DataFrame on error (error shown via st.error).
    '''
    return _query_cached(sql, ttl)


@st.cache_data(ttl=30, show_spinner=False)
def _query_cached(sql: str, ttl: int) -> pd.DataFrame:
    return _execute(sql)


def _execute(sql: str) -> pd.DataFrame:
    client = _client()
    try:
        response = client.statement_execution.execute_statement(
            warehouse_id = _warehouse_id(),
            statement    = sql,
            wait_timeout = "30s",
        )

        if response.status.state != StatementState.SUCCEEDED:
            st.error(f"Query failed: {response.status.error}")
            return pd.DataFrame()

        result = response.result
        if not result or not result.data_array:
            return pd.DataFrame()

        cols = [c.name for c in response.manifest.schema.columns]
        return pd.DataFrame(result.data_array, columns=cols)

    except Exception as exc:
        st.error(f"Query error: {exc}")
        return pd.DataFrame()


# ── Convenience helpers ───────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def list_sim_ids(catalog: str) -> list[str]:
    '''Return distinct sim_ids from ops_warehouse_state, newest first.'''

    df = _execute(f'''
        SELECT DISTINCT sim_id
        FROM {catalog}.tables4ops.ops_warehouse_state
        ORDER BY sim_id DESC
    ''')
    return df["sim_id"].tolist() if not df.empty else []


def latest_tick(catalog: str, sim_id: str) -> int | None:
    '''Return the maximum completed tick for this sim_id.'''

    df = _execute(f'''
        SELECT MAX(tick) AS max_tick
        FROM {catalog}.tables4ops.ops_warehouse_state
        WHERE sim_id = '{sim_id}'
    ''')
    if df.empty or df["max_tick"].iloc[0] is None:
        return None
    return int(df["max_tick"].iloc[0])


def sim_ended(catalog: str, sim_id: str) -> bool:
    '''Return True if SIM_ENDED has been written for this sim_id.'''
    
    df = _execute(f'''
        SELECT COUNT(*) AS n
        FROM {catalog}.tables4eventlog.event_log
        WHERE sim_id = '{sim_id}'
          AND event_type = 'SIM_ENDED'
    ''')
    return not df.empty and int(df["n"].iloc[0]) > 0
