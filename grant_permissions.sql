-- Grant statements for the Sim Monitor Databricks App service principal.
-- Replace <app-sp-name> with the service principal name from the Apps UI.
-- Run these in a Databricks SQL editor or via the CLI against your warehouse.

-- -- Catalog -------------------------------------------------------------------

GRANT USE CATALOG ON CATALOG hackathon_of_the_century TO `<app-sp-name>`;

-- -- tables4ops ----------------------------------------------------------------

GRANT USE SCHEMA ON SCHEMA hackathon_of_the_century.tables4ops TO `<app-sp-name>`;

GRANT SELECT ON TABLE hackathon_of_the_century.tables4ops.ops_warehouse_state    TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4ops.ops_pending_orders     TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4ops.ops_active_disruptions TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4ops.ops_cost_accumulator   TO `<app-sp-name>`;

-- -- tables4hist ---------------------------------------------------------------

GRANT USE SCHEMA ON SCHEMA hackathon_of_the_century.tables4hist TO `<app-sp-name>`;

GRANT SELECT ON TABLE hackathon_of_the_century.tables4hist.hist_demand_actuals    TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4hist.hist_reorder_decisions TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4hist.hist_cost_by_tick      TO `<app-sp-name>`;

-- -- tables4eventlog -----------------------------------------------------------

GRANT USE SCHEMA ON SCHEMA hackathon_of_the_century.tables4eventlog TO `<app-sp-name>`;

GRANT SELECT ON TABLE hackathon_of_the_century.tables4eventlog.event_log TO `<app-sp-name>`;

-- -- tables4env ----------------------------------------------------------------

GRANT USE SCHEMA ON SCHEMA hackathon_of_the_century.tables4env TO `<app-sp-name>`;

GRANT SELECT ON TABLE hackathon_of_the_century.tables4env.env_sim_config           TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4env.env_item_types           TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4env.env_suppliers            TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4env.env_consumers            TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4env.env_disruption_schedule  TO `<app-sp-name>`;
GRANT SELECT ON TABLE hackathon_of_the_century.tables4env.env_patterns             TO `<app-sp-name>`;