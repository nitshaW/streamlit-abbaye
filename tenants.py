"""Per-customer (tenant) configuration registry.

Two config layers keep the multi-tenant app clean:
  - email -> customer  : operational, changes often -> Snowflake DASHBOARD_ACCESS
                         table (see auth.resolve_tenant)
  - customer -> template : ships with releases -> this registry

Each tenant defines its data prefix, its page set, and per-page parameters.
This is where "different template per customer" lives — same page code, driven
by config. For a genuinely bespoke customer, point a page key at a custom
render function in views.py.

Available page keys (see views.PAGES): product_performance, book_date,
event_date, email_campaigns.
"""

TENANTS = {
    "abbaye": {
        "label": "Abbaye des Vaux-de-Cernay",
        "prefix": "ABBAYE",
        "pages": ["product_performance", "book_date", "event_date", "email_campaigns"],
        "email": {
            # Raw multi-property table -> must filter by subject + de-dup in-app.
            "table": "ABBAYE_MANDRILL_NOTIFICATIONS",
            "prededuped": False,
            "tag_field": "NOTIFICATION_TAG",
            "subject_field": "DATA_SUBJECT",
            "subject_match": "Abbaye des Vaux-de-Cernay",   # ILIKE scope
            "buckets": [("days:15", "Automatic Emails 15 days"),
                        ("days:0", "Guest Portal (0 days)")],
        },
    },
    "rimrock": {
        "label": "Rimrock Banff",
        "prefix": "RIMROCK",
        "pages": ["product_performance", "book_date", "event_date", "email_campaigns"],
        "email": {
            # Pre-deduped view -> exact subject, EXTRA/SUBJECT fields, no in-app de-dup.
            "table": "RIMROCK_MANDRILL_NOTIFICATION_VIEW",
            "prededuped": True,
            "tag_field": "EXTRA",
            "subject_field": "SUBJECT",
            "subject_match": "Get the most out of your time at Rimrock Banff",
            "buckets": [("days:30", "Automatic Emails 30 days"),
                        ("days:60", "Automatic Emails 60 days"),
                        ("days:90", "Automatic Emails 90 days")],
        },
    },
    # fairmont / cll / whistler / jasper: add config here once their access is set up.
}

PAGE_TITLES = {
    "product_performance": "Product Performance",
    "book_date": "Book Date",
    "event_date": "Event Date",
    "email_campaigns": "Email Campaigns",
}
