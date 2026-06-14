'''
sim_monitor_app/nav.py

Shared sidebar component rendered on every page.
Provides only the sim ID selector - page navigation is handled by Streamlit's native multi-page sidebar list.

Usage:

```
from nav import render_nav
render_nav(current="home")
sim_id = st.session_state["selected_sim_id"]
```
'''

import streamlit as st
from db import list_sim_ids

CATALOG = "hackathon_of_the_century"


def render_nav(current: str) -> None:
    '''
    Render the sim ID selector in the sidebar.
    
    Sets st.session_state["selected_sim_id"] so every page can read it regardless of entry point.

    Parameters
    ----------
    current : str
        Key of the active page (unused here; kept for API consistency).
    '''
    with st.sidebar:
        st.markdown("## ⬡ Sim Monitor")
        st.divider()

        sim_ids = list_sim_ids(CATALOG)
        if not sim_ids:
            st.warning("No simulations found in catalog.")
            st.stop()

        st.selectbox(
            "Simulation ID",
            options = sim_ids,
            index   = 0,
            key     = "selected_sim_id",
        )

        st.divider()
        st.caption(f"Catalog: `{CATALOG}`")