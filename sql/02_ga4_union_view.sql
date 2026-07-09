-- GA4 union view for one client (example: Abbaye).
--
-- The Snowflake Connector for Google Analytics writes ONE table per report/grain.
-- This view UNIONs them into the single {PREFIX}_GA4 the Guest Portal + Audience
-- pages read, tagging each row with REPORT and mapping every field into one wide,
-- nullable column set.
--
-- ⚠️ TEMPLATE — before running:
--   1. Create the connector reports first: ABBAYE_PARIS_GA4_ITEMS / _EVENTS / _DAILY /
--      _DEVICE / _LOCATION (+ _SLIDES once the slide dimension is resolved).
--   2. Adjust the source table names AND the source column names below to match what
--      the connector actually produced (its column naming may differ from these).
--   3. Name the view to match the tenant PREFIX the app expects -> ABBAYE_GA4.

CREATE OR REPLACE VIEW SALES_ANALYTICS.PUBLIC.ABBAYE_GA4 AS
-- items ----------------------------------------------------------------------
SELECT 'items'   AS REPORT, DATE,
       ITEM_NAME AS ITEM_NAME, NULL AS EVENT_NAME, NULL AS DEVICE_CATEGORY,
       NULL AS CITY, NULL AS COUNTRY, NULL AS REGION, NULL AS LINK_URL, NULL AS LINK_TEXT,
       NULL AS SESSION_SOURCE, NULL AS HOST_NAME,
       NULL AS SESSIONS, NULL AS KEY_EVENTS, ITEMS_VIEWED AS ITEMS_VIEWED, ITEMS_PURCHASED AS ITEMS_PURCHASED,
       NULL AS EVENT_COUNT, NULL AS ACTIVE_USERS, NULL AS TOTAL_USERS, NULL AS NEW_USERS,
       NULL AS SCREEN_PAGE_VIEWS, NULL AS ENGAGED_SESSIONS, NULL AS USER_ENGAGEMENT_DURATION
FROM SALES_ANALYTICS.PUBLIC.ABBAYE_PARIS_GA4_ITEMS
UNION ALL
-- events (funnel, transactions, conversion rate) -----------------------------
SELECT 'events', DATE,
       NULL, EVENT_NAME, NULL, NULL, NULL, NULL, NULL, NULL,
       SESSION_SOURCE, HOST_NAME,
       SESSIONS, KEY_EVENTS, NULL, NULL,
       EVENT_COUNT, NULL, NULL, NULL, NULL, NULL, NULL
FROM SALES_ANALYTICS.PUBLIC.ABBAYE_PARIS_GA4_EVENTS
UNION ALL
-- daily (acquisition, behavior, sessions graph) ------------------------------
SELECT 'daily', DATE,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
       SESSION_SOURCE, HOST_NAME,
       SESSIONS, KEY_EVENTS, NULL, NULL,
       NULL, ACTIVE_USERS, TOTAL_USERS, NEW_USERS,
       SCREEN_PAGE_VIEWS, ENGAGED_SESSIONS, USER_ENGAGEMENT_DURATION
FROM SALES_ANALYTICS.PUBLIC.ABBAYE_PARIS_GA4_DAILY
UNION ALL
-- device ---------------------------------------------------------------------
SELECT 'device', DATE,
       NULL, NULL, DEVICE_CATEGORY, NULL, NULL, NULL, NULL, NULL,
       NULL, HOST_NAME,
       SESSIONS, NULL, NULL, NULL,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM SALES_ANALYTICS.PUBLIC.ABBAYE_PARIS_GA4_DEVICE
UNION ALL
-- location -------------------------------------------------------------------
SELECT 'location', DATE,
       NULL, NULL, NULL, CITY, COUNTRY, REGION, NULL, NULL,
       SESSION_SOURCE, HOST_NAME,
       SESSIONS, KEY_EVENTS, NULL, NULL,
       NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM SALES_ANALYTICS.PUBLIC.ABBAYE_PARIS_GA4_LOCATION;

-- Add a 'slides' UNION branch once the dimension is resolved:
--   SELECT 'slides', DATE, NULL, EVENT_NAME, NULL, NULL, NULL, NULL, LINK_URL, LINK_TEXT,
--          NULL, NULL, NULL, NULL, NULL, NULL, EVENT_COUNT, NULL, NULL, NULL, NULL, NULL, NULL
--   FROM SALES_ANALYTICS.PUBLIC.ABBAYE_PARIS_GA4_SLIDES
