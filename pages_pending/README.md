# Inactive / legacy pages

Files parked here are **not loaded by the app**. They predate the multi-tenant refactor,
which replaced Streamlit's `pages/` auto-discovery with a router: dashboards are now
functions in [`../views.py`](../views.py), registered per property via
`DASHBOARD_CUSTOMERS.PAGES` (or the in-code fallback) and mounted with `st.navigation` in
[`../Main.py`](../Main.py). There is no `../pages/` directory anymore.

- `Email-Analysis.py` — legacy single-page prototype that needs an `ABBAYE_EMAIL_ANALYSIS`
  table that doesn't exist. To revive it, port the logic into a function in `../views.py`,
  add it to `views.PAGES`, and include its page key in a customer's `PAGES` array.

## Notes

- Active pages mirror the Looker Studio report, scoped per property by `PREFIX`
  (Abbaye reads `ABBAYE_REPORT_ITEMS`, `ABBAYE_UVE_TRANSACTIONS_GROUPED`,
  `ABBAYE_MANDRILL_NOTIFICATIONS`).
- Email Campaigns: `ABBAYE_MANDRILL_NOTIFICATIONS` is multi-property, so the page filters
  to subjects containing "Abbaye des Vaux-de-Cernay". Abbaye's automatic email uses tag
  `days:15` ("Préparez votre séjour …") plus `days:0` (guest portal) — not Rimrock's 30/60/90.
- **Guest Portal + Audience (Google Analytics) are built** — `views.guest_portal` /
  `views.audience`, reading the GA4 connector views via `DASHBOARD_CUSTOMERS.GA4_CONFIG`.
  See [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md#4-data-model).
