"""Streamlit dashboard for ClinicalTrials.gov data.

Wraps the 10,000-trial CSV with interactive filters and visualizations.
Notebook (analysis.ipynb) is still the source of truth for one-shot exploration;
this app is the always-on, hiring-manager-friendly version.
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA = Path(__file__).parent / "data" / "clinical_trials.csv"

st.set_page_config(
    page_title="Clinical Trial Trends",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner="Loading 10,000 trials...")
def load_data():
    df = pd.read_csv(DATA, dtype={"enrollment": "string"})
    # Parse dates loosely. ClinicalTrials.gov mixes YYYY-MM and YYYY-MM-DD.
    df["start_date"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["completion_date"] = pd.to_datetime(df["completion_date"], errors="coerce")
    df["start_year"] = df["start_date"].dt.year
    # Normalize phase
    df["phase"] = df["phase"].fillna("NA").replace({"": "NA"})
    df["enrollment_n"] = pd.to_numeric(df["enrollment"], errors="coerce")
    # First country only when there are pipe-separated lists, for cleaner grouping
    df["country_primary"] = df["country"].fillna("").str.split("|").str[0].str.strip()
    return df


df = load_data()


# --- Sidebar filters ----------------------------------------------------

with st.sidebar:
    st.title("Clinical Trial Trends")
    st.caption("Exploratory dashboard over 10,000 trials pulled from ClinicalTrials.gov.")

    st.divider()

    phases = sorted(df["phase"].dropna().unique())
    phase_filter = st.multiselect("Phase", phases, default=phases)

    statuses = sorted(df["overall_status"].dropna().unique())
    status_filter = st.multiselect("Status", statuses, default=statuses)

    sponsor_types = sorted(df["sponsor_type"].dropna().unique())
    sponsor_filter = st.multiselect("Sponsor type", sponsor_types, default=sponsor_types)

    study_types = sorted(df["study_type"].dropna().unique())
    study_filter = st.multiselect("Study type", study_types, default=study_types)

    year_range = st.slider(
        "Start year",
        int(df["start_year"].min()) if df["start_year"].notna().any() else 2000,
        int(df["start_year"].max()) if df["start_year"].notna().any() else 2025,
        (2010, 2025),
    )

    condition_search = st.text_input(
        "Condition contains",
        placeholder="e.g. cancer, diabetes, depression",
    )

    st.divider()
    st.caption("Data: ClinicalTrials.gov API v2. No PHI.")


# --- Apply filters ------------------------------------------------------

mask = (
    df["phase"].isin(phase_filter)
    & df["overall_status"].isin(status_filter)
    & df["sponsor_type"].isin(sponsor_filter)
    & df["study_type"].isin(study_filter)
    & df["start_year"].between(year_range[0], year_range[1])
)

if condition_search:
    mask &= df["condition"].fillna("").str.contains(condition_search, case=False, regex=False)

f = df[mask].copy()


# --- Header + KPIs ------------------------------------------------------

st.title("Clinical Trial Trends Explorer")
st.caption(
    "10,000 clinical trials from ClinicalTrials.gov. Filter on the left, charts update live. "
    "For deeper one-shot analysis see the [notebook on GitHub](https://github.com/ksolano220/clinical-trial-trends/blob/main/analysis.ipynb)."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Trials in view", f"{len(f):,}", delta=f"of {len(df):,}")
c2.metric("Unique conditions", f"{f['condition'].nunique():,}")
c3.metric("Countries", f"{f['country_primary'].nunique():,}")
median_enroll = f["enrollment_n"].median()
c4.metric(
    "Median enrollment",
    f"{int(median_enroll):,}" if pd.notna(median_enroll) else "—",
)

if len(f) == 0:
    st.warning("No trials match the current filters. Loosen them in the sidebar.")
    st.stop()


tab_overview, tab_sponsors, tab_phases, tab_geo, tab_trends, tab_browse = st.tabs(
    ["Overview", "Sponsors", "Phases", "Geography", "Trends over time", "Browse"]
)


# --- Overview -----------------------------------------------------------

with tab_overview:
    st.subheader("Top conditions")
    top_conds = (
        f["condition"]
        .replace("", pd.NA)
        .dropna()
        .value_counts()
        .head(20)
        .reset_index()
        .rename(columns={"index": "condition", "count": "trials"})
    )
    fig = px.bar(
        top_conds, x="trials", y="condition", orientation="h",
        labels={"trials": "Number of trials", "condition": ""},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=520)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Trial status mix")
    status_counts = f["overall_status"].value_counts().reset_index()
    status_counts.columns = ["status", "count"]
    fig = px.pie(status_counts, values="count", names="status", hole=0.45)
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)


# --- Sponsors -----------------------------------------------------------

with tab_sponsors:
    st.subheader("Sponsor type mix")
    spon = f["sponsor_type"].value_counts().reset_index()
    spon.columns = ["sponsor_type", "count"]
    fig = px.bar(spon, x="sponsor_type", y="count", labels={"count": "Trials"})
    fig.update_layout(height=380)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Phase mix by sponsor type")
    spon_phase = (
        f.groupby(["sponsor_type", "phase"]).size().reset_index(name="count")
    )
    fig = px.bar(
        spon_phase, x="sponsor_type", y="count", color="phase",
        labels={"count": "Trials"},
    )
    fig.update_layout(height=420)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top 25 lead sponsors")
    top_sponsors = (
        f["lead_sponsor"]
        .replace("", pd.NA)
        .dropna()
        .value_counts()
        .head(25)
        .reset_index()
    )
    top_sponsors.columns = ["lead_sponsor", "trials"]
    st.dataframe(top_sponsors, hide_index=True, use_container_width=True)


# --- Phases -------------------------------------------------------------

with tab_phases:
    st.subheader("Trial counts by phase")
    phase_counts = f["phase"].value_counts().reset_index()
    phase_counts.columns = ["phase", "count"]
    fig = px.bar(phase_counts, x="phase", y="count", labels={"count": "Trials"})
    fig.update_layout(height=380)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Median enrollment by phase")
    enroll_by_phase = (
        f.dropna(subset=["enrollment_n"])
        .groupby("phase")["enrollment_n"]
        .median()
        .reset_index()
        .sort_values("enrollment_n", ascending=False)
    )
    fig = px.bar(
        enroll_by_phase, x="phase", y="enrollment_n",
        labels={"enrollment_n": "Median enrollment"},
    )
    fig.update_layout(height=380)
    st.plotly_chart(fig, use_container_width=True)


# --- Geography ----------------------------------------------------------

with tab_geo:
    st.subheader("Top countries")
    country_counts = (
        f[f["country_primary"].str.len() > 0]["country_primary"]
        .value_counts()
        .head(25)
        .reset_index()
    )
    country_counts.columns = ["country", "trials"]
    fig = px.bar(
        country_counts, x="trials", y="country", orientation="h",
        labels={"trials": "Number of trials", "country": ""},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=620)
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Multi-country trials are attributed here to their first listed country. "
        "Single-country attribution is exact."
    )


# --- Trends over time ---------------------------------------------------

with tab_trends:
    st.subheader("Trials registered per year")
    by_year = (
        f.dropna(subset=["start_year"])
        .groupby("start_year")
        .size()
        .reset_index(name="trials")
    )
    fig = px.line(by_year, x="start_year", y="trials", markers=True)
    fig.update_layout(height=380, xaxis_title="Start year", yaxis_title="Trials")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Top conditions over time")
    top10_conds = (
        f["condition"].replace("", pd.NA).dropna().value_counts().head(8).index.tolist()
    )
    over_time = (
        f[f["condition"].isin(top10_conds)]
        .dropna(subset=["start_year"])
        .groupby(["start_year", "condition"])
        .size()
        .reset_index(name="trials")
    )
    fig = px.line(
        over_time, x="start_year", y="trials", color="condition", markers=False,
    )
    fig.update_layout(height=460, xaxis_title="Start year", yaxis_title="Trials")
    st.plotly_chart(fig, use_container_width=True)


# --- Browse -------------------------------------------------------------

with tab_browse:
    st.subheader("Filtered trial list")
    st.caption(f"Showing first 200 of {len(f):,} matching trials.")

    cols_to_show = [
        "nct_id", "brief_title", "overall_status", "phase",
        "study_type", "start_date", "enrollment_n",
        "condition", "lead_sponsor", "sponsor_type", "country_primary",
    ]
    table = f[cols_to_show].head(200).rename(columns={
        "country_primary": "country",
        "enrollment_n": "enrollment",
    })

    st.dataframe(table, hide_index=True, use_container_width=True)

    st.download_button(
        "Download filtered subset (CSV)",
        f[cols_to_show].to_csv(index=False).encode("utf-8"),
        file_name="clinical_trials_filtered.csv",
        mime="text/csv",
    )
