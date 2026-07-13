"""Tenant-parameterized dashboard views.

Each function renders one dashboard for a given tenant config (see tenants.py).
All data access is scoped by ``cfg["prefix"]`` (or ``cfg["email"]["table"]``) —
the customer is resolved server-side in Main.py and is never taken from user
input. Cache loaders are keyed by the fully-qualified table name, so
``@st.cache_data`` entries are naturally per-tenant (no cross-tenant leakage).

No st.set_page_config here — that's called once by the Main.py entrypoint that
drives st.navigation.
"""
import pandas as pd
import streamlit as st

from sf_session import get_session

SCHEMA = "SALES_ANALYTICS.PUBLIC"


def _csv(df):
    return df.to_csv(index=False).encode("utf-8")


def _dl(df, fname, key, label="⬇ Download data (CSV)"):
    """Compact CSV download button (unique key required when several on one page)."""
    st.download_button(label, data=_csv(df), file_name=fname, mime="text/csv", key=key)


# ---------------------------------------------------------------- Product Performance
@st.cache_data
def _load_report_items(table):
    df = get_session().sql(f"SELECT * FROM {SCHEMA}.{table}").to_pandas()
    df = df.drop_duplicates()
    df["ITEM_NAME"] = df["ITEM_NAME"].fillna("Unknown")
    df["PRODUCT_CATEGORY"] = df["PRODUCT_CATEGORY"].fillna("Unknown")
    df["BOOKED_MONTH"] = pd.to_datetime(df["BOOKED_MONTH"].astype(str) + "01", format="%Y%m%d")
    df["VALUE"] = df.apply(
        lambda r: r["VALUE_ADDED"] if pd.isna(r["VALUE"]) or r["VALUE"] == 0 else r["VALUE"], axis=1
    )
    df = df.rename(columns={
        "BOOKED_MONTH": "Booked Year Month", "ITEM_NAME": "Item Name",
        "PRODUCT_CATEGORY": "Department", "VIEWED": "View", "ITEMSPURCHASED": "Gross Quantity",
        "CONVERSION": "Conversion", "TRANSACTIONS": "Gross Booked", "ATTENDANCE": "Net Attendance",
        "VALUE": "Net Value", "CANCELLED": "Cancelled",
    })
    df["Booked Year Month"] = df["Booked Year Month"].dt.strftime("%Y-%m")
    return df


def product_performance(cfg):
    st.title("Product Performance")
    try:
        df = _load_report_items(f"{cfg['prefix']}_REPORT_ITEMS")
    except Exception:
        st.error("Unable to load data right now. Please try again later.")
        return

    st.sidebar.header("Filters")
    for label in ["Booked Year Month", "Item Name", "Department"]:
        picked = st.sidebar.multiselect(f"Select {label}", sorted(df[label].dropna().unique()))
        if picked:
            df = df[df[label].isin(picked)]

    cols = ["Booked Year Month", "Item Name", "Department", "View", "Gross Booked",
            "Conversion", "Net Attendance", "Net Value", "Cancelled", "Gross Quantity"]
    table = df[cols].sort_values("View", ascending=False)

    grand = table.select_dtypes(include=["number"]).sum().to_frame().T
    grand.index = ["Grand Total"]
    grand["Conversion"] = (grand["Gross Booked"] / grand["View"] * 100) if grand["View"].iloc[0] else 0
    grand = grand.reindex(columns=["View", "Gross Booked", "Conversion", "Net Attendance",
                                   "Net Value", "Cancelled", "Gross Quantity"]) \
                 .rename(columns={"Conversion": "Overall Conversion"}).round(2)

    st.dataframe(table, height=600, use_container_width=True)
    st.write("Grand Total")
    st.write(grand.map(lambda x: f"{x:,.2f}").to_html(), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button("Download Product Performance as CSV", data=_csv(pd.concat([table, grand])),
                       file_name="product_performance.csv", mime="text/csv")


# ---------------------------------------------------------------- Book Date / Event Date
_ATT_NUMERIC = ["TB_GUESTS", "TB_SUBTOTALAGREE", "ADDED_PRICE"]
_ATT_RENAME = {
    "TI_ITEMNAME": "Item", "PRODUCT_CATEGORY": "Department", "TB_GUESTS": "Net Attendance",
    "TB_SUBTOTALAGREE": "Net Value", "ADDED_PRICE": "ValueAdded", "SOURCE": "Source",
    "NETWORK": "Network", "VP_VENUENAME": "Venue", "P_CURRENTSTATUS": "Booking Status",
}


@st.cache_data
def _load_transactions(table):
    df = get_session().sql(f"SELECT * FROM {SCHEMA}.{table}").to_pandas()
    for c in _ATT_NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    ti, act = df["TI_STATUS"].astype(str), df["TB_ACTION"].astype(str)
    df["Transaction Status"] = "Charged"
    df.loc[(ti == "9") | (act == "refund"), "Transaction Status"] = "Refunded"
    df = df.rename(columns=_ATT_RENAME)
    df["Net Value"] = df.apply(
        lambda r: r["ValueAdded"] if pd.isna(r["Net Value"]) or r["Net Value"] == 0 else r["Net Value"], axis=1
    )
    for c in ["Item", "Department", "Venue", "Source", "Network", "Booking Status"]:
        df[c] = df[c].fillna("Unknown")
    return df


def attendance(cfg, date_col, title):
    st.title(title)
    try:
        df = _load_transactions(f"{cfg['prefix']}_UVE_TRANSACTIONS_GROUPED").copy()
    except Exception:
        st.error("Unable to load data right now. Please try again later.")
        return
    df["Date"] = pd.to_datetime(df[date_col], errors="coerce")

    st.sidebar.header("Filters")
    dr = st.sidebar.date_input("Select date range", [])
    if len(dr) == 2:
        df = df[(df["Date"] >= pd.to_datetime(dr[0])) & (df["Date"] <= pd.to_datetime(dr[1]))]
    for label in ["Source", "Network", "Department", "Venue", "Item", "Booking Status", "Transaction Status"]:
        picked = st.sidebar.multiselect(f"Select {label}", sorted(df[label].dropna().unique()))
        if picked:
            df = df[df[label].isin(picked)]

    st.caption("***Use only reserved status when using Booking Status filter***")
    agg = (df.groupby(["Item", "Department"], as_index=False)[["Net Attendance", "Net Value"]]
             .sum().sort_values("Net Attendance", ascending=False))
    grand = agg[["Net Attendance", "Net Value"]].sum().to_frame().T.round(2)
    grand.index = ["Grand Total"]

    st.dataframe(agg, height=600, use_container_width=True)
    st.write("Grand Total")
    st.write(grand.map(lambda x: f"{x:,.2f}").to_html(), unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button("Download as CSV", data=_csv(pd.concat([agg, grand])),
                       file_name=f"{title.lower().replace(' ', '_')}.csv", mime="text/csv")


# ---------------------------------------------------------------- Email Campaigns
_EMAIL_NUMERIC = ["SENT", "OPEN", "CLICKS", "DATA_CLICKS", "DATA_OPENS"]


@st.cache_data
def _load_email(table):
    df = get_session().sql(f"SELECT * FROM {SCHEMA}.{table}").to_pandas()
    df = df.drop_duplicates(subset=["DATA_ID"])           # no-op on pre-deduped views
    for c in _EMAIL_NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    df["DATA_TS_DATE"] = pd.to_datetime(df["DATA_TS_DATE"]).dt.tz_localize(None)
    return df


def _email_section(title, d):
    st.markdown(f"## 📅 {title}")
    if d.empty:
        st.caption("No data")
        return
    record = d["DATA_ID"].count()
    sent, opened = d["SENT"].sum(), d["OPEN"].sum()
    data_clicks, clicks = d["DATA_CLICKS"].sum(), d["CLICKS"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Email Sent", int(record))
    c2.metric("Emails Delivered", int(sent))
    c3.metric("Emails Opened", int(opened))
    c4.metric("AVG Delivery Rate", f"{(sent/record if record else 0):.2%}")
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Data Clicks", int(data_clicks))
    c6.metric("Email With at Least 1 Click", int(clicks))
    c7.metric("Click Rate (CTR)", f"{(clicks/sent if sent else 0):.2%}")
    c8.metric("AVG Open Rate", f"{(opened/sent if sent else 0):.2%}")


def email_campaigns(cfg):
    st.title("📧 Email Campaigns")
    ec = cfg["email"]
    try:
        df = _load_email(ec["table"]).copy()
    except Exception:
        st.error("Unable to load data right now. Please try again later.")
        return

    # Scope to this customer's emails (source table may be multi-property).
    subj = df[ec["subject_field"]].fillna("")
    df = df[subj.str.contains(ec["subject_match"], case=False, na=False)]

    if df.empty:
        st.info("No email data for this customer yet.")
        return

    from datetime import timedelta
    start, end = df["DATA_TS_DATE"].min().date(), df["DATA_TS_DATE"].max().date()
    dr = st.sidebar.date_input("Select date range", [start, end])
    if len(dr) == 2:
        df = df[(df["DATA_TS_DATE"] >= pd.Timestamp(dr[0]))
                & (df["DATA_TS_DATE"] < pd.Timestamp(dr[1]) + timedelta(days=1))]

    tag = df[ec["tag_field"]].fillna("")
    for tag_value, label in ec["buckets"]:
        _email_section(label, df[tag == tag_value])
    _email_section("Total Emails", df)

    # Downloadable metrics summary: one row per bucket + total.
    def _sum_row(name, d):
        rec, sent, opened = int(d["DATA_ID"].count()), int(d["SENT"].sum()), int(d["OPEN"].sum())
        clicks, data_clicks = int(d["CLICKS"].sum()), int(d["DATA_CLICKS"].sum())
        return {"Segment": name, "Emails Sent": rec, "Delivered": sent, "Opened": opened,
                "Data Clicks": data_clicks, "Emails w/ >=1 Click": clicks,
                "Delivery Rate": f"{(sent / rec if rec else 0):.2%}",
                "Open Rate": f"{(opened / sent if sent else 0):.2%}",
                "CTR": f"{(clicks / sent if sent else 0):.2%}"}
    summary = pd.DataFrame([_sum_row(label, df[tag == tag_value]) for tag_value, label in ec["buckets"]]
                           + [_sum_row("Total", df)])
    _dl(summary, "email_campaigns_summary.csv", "email_summary_dl",
        label="⬇ Download metrics summary (CSV)")

    st.markdown("## 📊 General Data")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📧 Emails Sent")
        sent_tbl = df.groupby("DATA_STATE").size().reset_index(name="Total")
        st.dataframe(sent_tbl, use_container_width=True)
        _dl(sent_tbl, "email_sent_by_state.csv", "email_state_dl")
    with col2:
        st.markdown("### 🔄 Open Frequency")
        freq_tbl = df.groupby("DATA_OPENS").size().reset_index(name="Total")
        st.dataframe(freq_tbl, use_container_width=True)
        _dl(freq_tbl, "email_open_frequency.csv", "email_freq_dl")


# ---------------------------------------------------------------- GA4: Guest Portal + Audience
# These two pages come from GA4 via the Snowflake Connector for Google Analytics
# (aggregate), which writes one view per grain into its own database/schema.
# cfg["ga4"] points at that location + the per-client report base, e.g.
# ABBAYE_PARIS -> ABBAYE_PARIS_GA4_DAILY / _EVENTS / _ITEMS / _DEVICE / _LOCATION / _SLIDES.
# Unlike the other pages these render with charts, to match the Data Studio report.

# Some connector "metrics" arrive as VARCHAR (keyEvents, userEngagementDuration) — coerce.
_GA4_NUMERIC = ("SESSIONS", "ACTIVEUSERS", "TOTALUSERS", "NEWUSERS", "SCREENPAGEVIEWS",
                "ENGAGEDSESSIONS", "USERENGAGEMENTDURATION", "KEYEVENTS", "EVENTCOUNT",
                "ITEMSVIEWED", "ITEMSPURCHASED")

# sessionSource fragments excluded from every GA4 widget (QA / internal traffic),
# per the Data Studio report's filters.
_GA4_SOURCE_EXCLUDE = ("tagassistant", "uat", "localhost", "staging", "atlassian", "office.net")

# Guest Portal conversion funnel (ordered); labels shown on the chart.
_GA4_FUNNEL = [
    ("guest_portal_loaded", "Guest Portal Loaded"), ("view_item", "Viewed Item"),
    ("select_item", "Selected Item"), ("add_to_cart", "Add to Cart"),
    ("init_checkoutpay", "Checkout"), ("purchase", "Purchase"),
]


@st.cache_data(ttl=3600)
def _load_ga4(fq):
    return get_session().sql(f"SELECT * FROM {fq}").to_pandas()


def _ga4_grain(cfg, grain):
    g = cfg["ga4"]
    df = _load_ga4(f'{g["database"]}.{g["schema"]}.{g["report"]}_GA4_{grain}').copy()
    if "DATE" in df.columns:
        df["DATE"] = pd.to_datetime(df["DATE"], errors="coerce")
    for c in _GA4_NUMERIC:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


def _ga4_clean(df):
    """Apply the shared Data Studio traffic filters (host allow, source excludes)."""
    if "HOSTNAME" in df.columns:
        df = df[df["HOSTNAME"].fillna("").str.contains("booketing", case=False)]
    if "SESSIONSOURCE" in df.columns:
        src = df["SESSIONSOURCE"].fillna("").str.lower()
        df = df[~src.str.contains("|".join(_GA4_SOURCE_EXCLUDE))]
    return df


def _ga4_date_range(df):
    dmin, dmax = df["DATE"].min().date(), df["DATE"].max().date()
    dr = st.sidebar.date_input("Select date range", [dmin, dmax])
    return dr if len(dr) == 2 else (dmin, dmax)


def _ga4_apply_range(df, dr):
    return df[(df["DATE"] >= pd.to_datetime(dr[0])) & (df["DATE"] <= pd.to_datetime(dr[1]))]


def guest_portal(cfg):
    st.title("🏨 Guest Portal")
    if not cfg.get("ga4"):
        st.info("GA4 data isn't configured for this customer yet.")
        return
    try:
        daily = _ga4_clean(_ga4_grain(cfg, "DAILY"))
        events = _ga4_clean(_ga4_grain(cfg, "EVENTS"))
        items = _ga4_grain(cfg, "ITEMS")
    except Exception:
        st.error("Unable to load data right now. Please try again later.")
        return
    if daily.empty:
        st.info("No GA4 data for this customer yet.")
        return

    dr = _ga4_date_range(daily)
    daily, events = _ga4_apply_range(daily, dr), _ga4_apply_range(events, dr)
    items = _ga4_apply_range(items, dr)

    sessions = daily["SESSIONS"].sum()
    key_events = daily["KEYEVENTS"].sum()
    engaged = daily["ENGAGEDSESSIONS"].sum()
    eng_dur = daily["USERENGAGEMENTDURATION"].sum()
    c = st.columns(5)
    c[0].metric("Sessions", f"{int(sessions):,}")
    c[1].metric("Key Events", f"{int(key_events):,}")
    c[2].metric("Conversion Rate", f"{(key_events / sessions if sessions else 0):.2%}")
    c[3].metric("Engaged Sessions", f"{int(engaged):,}")
    c[4].metric("Avg Engagement", f"{(eng_dur / sessions if sessions else 0):.0f}s")

    st.subheader("Sessions over time")
    ts = daily.groupby(daily["DATE"].dt.date)["SESSIONS"].sum().rename("Sessions")
    st.line_chart(ts)
    _dl(ts.reset_index(), "guest_portal_sessions.csv", "gp_sessions_dl")

    st.subheader("Conversion funnel")
    totals = events.groupby("EVENTNAME")["EVENTCOUNT"].sum()
    funnel = pd.DataFrame({"Step": [lbl for _, lbl in _GA4_FUNNEL],
                           "Events": [int(totals.get(k, 0)) for k, _ in _GA4_FUNNEL]})
    st.bar_chart(funnel.set_index("Step"))
    _dl(funnel, "guest_portal_funnel.csv", "gp_funnel_dl")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Items — viewed vs purchased")
        top = (items.groupby("ITEMNAME")[["ITEMSVIEWED", "ITEMSPURCHASED"]].sum()
                    .sort_values("ITEMSVIEWED", ascending=False).head(15))
        top.columns = ["Viewed", "Purchased"]
        st.bar_chart(top)
        _dl(top.reset_index().rename(columns={"ITEMNAME": "Item"}),
            "guest_portal_items.csv", "gp_items_dl")
    with col2:
        # "Most visited" substitute for the (unavailable) venue slide dimension:
        # itemName ranked by itemsViewed, with per-item conversion.
        st.subheader("Most Visited Experiences")
        mv = (items.groupby("ITEMNAME")[["ITEMSVIEWED", "ITEMSPURCHASED"]].sum()
                   .sort_values("ITEMSVIEWED", ascending=False).head(20).reset_index())
        conv = (mv["ITEMSPURCHASED"] / mv["ITEMSVIEWED"].replace(0, pd.NA)).fillna(0)
        mv = mv.rename(columns={"ITEMNAME": "Experience", "ITEMSVIEWED": "Views",
                                "ITEMSPURCHASED": "Purchased"})
        mv["Conversion"] = (conv * 100).round(1).astype(str) + "%"
        st.dataframe(mv, use_container_width=True, hide_index=True)
        _dl(mv, "most_visited_experiences.csv", "gp_mv_dl", label="⬇ Download most-visited (CSV)")


def audience(cfg):
    st.title("👥 Audience")
    if not cfg.get("ga4"):
        st.info("GA4 data isn't configured for this customer yet.")
        return
    try:
        daily = _ga4_clean(_ga4_grain(cfg, "DAILY"))
        device = _ga4_clean(_ga4_grain(cfg, "DEVICE"))
        location = _ga4_clean(_ga4_grain(cfg, "LOCATION"))
    except Exception:
        st.error("Unable to load data right now. Please try again later.")
        return
    if daily.empty:
        st.info("No GA4 data for this customer yet.")
        return

    dr = _ga4_date_range(daily)
    daily = _ga4_apply_range(daily, dr)
    device = _ga4_apply_range(device, dr)
    location = _ga4_apply_range(location, dr)

    total_users = daily["TOTALUSERS"].sum()
    new_users = daily["NEWUSERS"].sum()
    sessions = daily["SESSIONS"].sum()
    engaged = daily["ENGAGEDSESSIONS"].sum()
    c = st.columns(5)
    c[0].metric("Total Users", f"{int(total_users):,}")
    c[1].metric("New Users", f"{int(new_users):,}")
    c[2].metric("% New Users", f"{(new_users / total_users if total_users else 0):.1%}")
    c[3].metric("Sessions / User", f"{(sessions / total_users if total_users else 0):.2f}")
    c[4].metric("Bounce Rate", f"{((sessions - engaged) / sessions if sessions else 0):.1%}")

    st.subheader("Users over time")
    users_ts = (daily.groupby(daily["DATE"].dt.date)[["TOTALUSERS", "NEWUSERS"]].sum()
                     .rename(columns={"TOTALUSERS": "Total Users", "NEWUSERS": "New Users"}))
    st.line_chart(users_ts)
    _dl(users_ts.reset_index(), "audience_users.csv", "aud_users_dl")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Device category")
        dev = (device.groupby("DEVICECATEGORY")["SESSIONS"].sum()
                     .sort_values(ascending=False).rename("Sessions"))
        st.bar_chart(dev)
        _dl(dev.reset_index(), "audience_device.csv", "aud_device_dl")
    with col2:
        st.subheader("Acquisition — session source")
        acq = (daily.groupby("SESSIONSOURCE")["SESSIONS"].sum()
                    .sort_values(ascending=False).head(10).rename("Sessions"))
        st.bar_chart(acq)
        _dl(acq.reset_index(), "audience_acquisition.csv", "aud_acq_dl")

    st.subheader("Top locations")
    loc = location[location["CITY"].fillna("") != "Morelia"]
    top_loc = (loc.groupby(["CITY", "COUNTRY"])["SESSIONS"].sum().reset_index()
                  .sort_values("SESSIONS", ascending=False).head(20)
                  .rename(columns={"CITY": "City", "COUNTRY": "Country", "SESSIONS": "Sessions"}))
    st.dataframe(top_loc, use_container_width=True, hide_index=True)
    _dl(top_loc, "ga4_locations.csv", "aud_loc_dl", label="⬇ Download locations (CSV)")


# Page-key -> render(cfg). Referenced by tenants.py page sets + Main.py router.
PAGES = {
    "product_performance": product_performance,
    "book_date": lambda cfg: attendance(cfg, "T_TRANSDATE", "Book Date"),
    "event_date": lambda cfg: attendance(cfg, "TI_CALDATE", "Event Date"),
    "email_campaigns": email_campaigns,
    "guest_portal": guest_portal,
    "audience": audience,
}
