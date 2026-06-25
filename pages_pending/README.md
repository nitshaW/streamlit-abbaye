# Inactive pages

Kept out of `../pages/` so Streamlit doesn't load them.

- `Email-Analysis.py` — legacy page; needs an `ABBAYE_EMAIL_ANALYSIS` table that
  doesn't exist. Move back into `../pages/` and point it at the right table to
  re-enable.

## Notes

- Active pages mirror the Looker Studio report, pointed at the `ABBAYE_*` Snowflake
  tables (`ABBAYE_REPORT_ITEMS`, `ABBAYE_UVE_TRANSACTIONS_GROUPED`,
  `ABBAYE_MANDRILL_NOTIFICATIONS`).
- Email Campaigns: `ABBAYE_MANDRILL_NOTIFICATIONS` is multi-property, so the page
  filters to subjects containing "Abbaye des Vaux-de-Cernay". Abbaye's automatic
  email uses tag `days:15` ("Préparez votre séjour …"), plus `days:0` (guest portal)
  — not Rimrock's 30/60/90.
- Guest Portal + Audience pages (Google Analytics) still to come.
