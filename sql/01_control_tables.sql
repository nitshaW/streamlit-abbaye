-- Multi-tenant dashboard control tables. Run once in SALES_ANALYTICS.PUBLIC.
-- DASHBOARD_USERS  = who logs in (bcrypt password) + which customer
-- DASHBOARD_CUSTOMERS = each customer's data source (PREFIX) + template (PAGES, EMAIL_CONFIG)

CREATE TABLE IF NOT EXISTS SALES_ANALYTICS.PUBLIC.DASHBOARD_USERS (
    EMAIL         VARCHAR NOT NULL,
    NAME          VARCHAR,
    PASSWORD_HASH VARCHAR,            -- bcrypt; NULL until the user sets it on first login
    CUSTOMER      VARCHAR NOT NULL,   -- must match DASHBOARD_CUSTOMERS.CUSTOMER
    INVITE_CODE   VARCHAR,            -- optional shared secret for first-time set-password
    ACTIVE        BOOLEAN DEFAULT TRUE,
    CREATED_AT    TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS SALES_ANALYTICS.PUBLIC.DASHBOARD_CUSTOMERS (
    CUSTOMER     VARCHAR NOT NULL,
    LABEL        VARCHAR,
    PREFIX       VARCHAR NOT NULL,    -- -> PREFIX_REPORT_ITEMS, PREFIX_UVE_TRANSACTIONS_GROUPED, PREFIX_GA4
    PAGES        ARRAY,               -- dashboards this customer sees
    EMAIL_CONFIG VARIANT,             -- per-customer Email Campaigns template
    ACTIVE       BOOLEAN DEFAULT TRUE
);

-- ---- Seed customers -------------------------------------------------------
INSERT INTO SALES_ANALYTICS.PUBLIC.DASHBOARD_CUSTOMERS (CUSTOMER, LABEL, PREFIX, PAGES, EMAIL_CONFIG, ACTIVE)
SELECT 'abbaye', 'Abbaye des Vaux-de-Cernay', 'ABBAYE',
       ARRAY_CONSTRUCT('product_performance','book_date','event_date','email_campaigns'),
       PARSE_JSON('{"table":"ABBAYE_MANDRILL_NOTIFICATIONS","tag_field":"NOTIFICATION_TAG","subject_field":"DATA_SUBJECT","subject_match":"Abbaye des Vaux-de-Cernay","buckets":[["days:15","Automatic Emails 15 days"],["days:0","Guest Portal (0 days)"]]}'),
       TRUE
UNION ALL
SELECT 'rimrock', 'Rimrock Banff', 'RIMROCK',
       ARRAY_CONSTRUCT('product_performance','book_date','event_date','email_campaigns'),
       PARSE_JSON('{"table":"RIMROCK_MANDRILL_NOTIFICATION_VIEW","tag_field":"EXTRA","subject_field":"SUBJECT","subject_match":"Get the most out of your time at Rimrock Banff","buckets":[["days:30","30 days"],["days:60","60 days"],["days:90","90 days"]]}'),
       TRUE;

-- ---- Add a user (invite flow: no password; user sets it on first login) ---
-- INSERT INTO SALES_ANALYTICS.PUBLIC.DASHBOARD_USERS (EMAIL, NAME, CUSTOMER, INVITE_CODE)
-- VALUES ('jane@client.com', 'Jane Doe', 'abbaye', 'welcome-abbaye-2026');
