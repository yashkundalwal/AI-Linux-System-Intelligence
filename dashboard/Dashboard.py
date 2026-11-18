
import os
import pandas as pd
import streamlit as st
import plotly.express as px

from streamlit_autorefresh import st_autorefresh

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="AI Linux System",
    page_icon="🐧",
    layout="wide"
)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data", "processed")

SYSTEM_FILE = os.path.join(DATA, "clean_system_telemetry.csv")
PROCESS_FILE = os.path.join(DATA, "clean_process_telemetry.csv")
SYSTEM_ANOMALY_FILE = os.path.join(DATA, "system_anomaly_results.csv")
PROCESS_ANOMALY_FILE = os.path.join(DATA, "process_anomaly_results.csv")
PREDICTION_FILE = os.path.join(DATA, "resource_prediction_results.csv")
FINDINGS_FILE = os.path.join(DATA, "diagnostic_findings.csv")
RECOMMENDATION_FILE = os.path.join(DATA, "recommendations.csv")

st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stMetric"] {
        background: rgba(128,128,128,0.08);
        padding: 15px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------
# DATA LOADING
# --------------------------------------------------

@st.cache_data(ttl=5)
def load_csv(path):
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame()


# --------------------------------------------------
# SIDEBAR
# --------------------------------------------------

st.sidebar.title("🐧 AI Linux System")
st.sidebar.caption("Intelligent Linux Monitoring Platform")

refresh_seconds = st.sidebar.selectbox(
    "Dashboard refresh interval",
    options=[5, 10, 15, 30],
    index=1
)

st_autorefresh(
    interval=refresh_seconds * 1000,
    key="ai_linux_dashboard_refresh"
)

page = st.sidebar.radio(
    "Navigation",
    [
        "System Overview",
        "Process Explorer",
        "Anomaly Detection",
        "Resource Prediction",
        "Diagnostic Center",
        "Recommendation Center"
    ]
)

st.sidebar.divider()
st.sidebar.caption("AI-Driven Linux System Intelligence")


# --------------------------------------------------
# LOAD LATEST DATA
# --------------------------------------------------

system_df = load_csv(SYSTEM_FILE)
process_df = load_csv(PROCESS_FILE)
system_anomalies = load_csv(SYSTEM_ANOMALY_FILE)
process_anomalies = load_csv(PROCESS_ANOMALY_FILE)
predictions = load_csv(PREDICTION_FILE)
findings = load_csv(FINDINGS_FILE)
recommendations = load_csv(RECOMMENDATION_FILE)

# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.title("🐧 AI Linux System")
st.caption("AI-powered Linux system monitoring, prediction and diagnostics")

# --------------------------------------------------
# SYSTEM OVERVIEW
# --------------------------------------------------

if page == "System Overview":

    st.header("System Health Overview")

    if system_df.empty:
        st.warning("System telemetry unavailable.")
    else:
        latest = system_df.iloc[-1]

        cpu = latest.get("cpu_usage", 0)
        ram = latest.get("memory_usage", 0)
        disk = latest.get("disk_usage", 0)
        temp = latest.get("cpu_temperature", 0)
        battery = latest.get("battery_percent", None)

        c1, c2, c3, c4, c5 = st.columns(5)

        c1.metric("CPU Usage", f"{cpu:.2f}%")
        c2.metric("Memory Usage", f"{ram:.2f}%")
        c3.metric("Disk Usage", f"{disk:.2f}%")
        c4.metric("Temperature", f"{temp:.1f} °C")

        if pd.notna(battery):
            c5.metric("Battery", f"{battery:.1f}%")
        else:
            c5.metric("Battery", "Unavailable")

        st.subheader("Resource Utilization")

        chart_data = system_df.copy()
        chart_data["timestamp"] = pd.to_datetime(
            chart_data["timestamp"], errors="coerce"
        )

        available = [
            col for col in ["cpu_usage", "memory_usage", "disk_usage"]
            if col in chart_data.columns
        ]

        if available:
            melted = chart_data.melt(
                id_vars="timestamp",
                value_vars=available,
                var_name="Resource",
                value_name="Usage"
            )

            fig = px.line(
                melted,
                x="timestamp",
                y="Usage",
                color="Resource",
                title="System Resource Trends"
            )
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Hardware and System Information")

        info_columns = [
            "load_1", "load_5", "load_15",
            "total_processes", "running_processes",
            "cpu_frequency_mhz"
        ]

        available_info = [
            col for col in info_columns if col in system_df.columns
        ]

        if available_info:
            st.dataframe(
                system_df[available_info].tail(10),
                use_container_width=True
            )


# --------------------------------------------------
# PROCESS EXPLORER
# --------------------------------------------------

elif page == "Process Explorer":

    st.header("Process Explorer")

    if process_df.empty:
        st.warning("Process telemetry unavailable.")
    else:
        df = process_df.copy()

        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(
                df["timestamp"], errors="coerce"
            )
            latest_time = df["timestamp"].max()
            df = df[df["timestamp"] == latest_time]

        search = st.text_input("Search process name")

        if search:
            df = df[
                df["process_name"].astype(str).str.contains(
                    search, case=False, na=False
                )
            ]

        if "cpu_percent" in df.columns:
            df = df.sort_values("cpu_percent", ascending=False)

        st.metric("Processes in selected snapshot", len(df))

        columns = [
            col for col in [
                "pid", "process_name", "state",
                "cpu_percent", "memory_mb", "threads"
            ] if col in df.columns
        ]

        st.dataframe(
            df[columns],
            use_container_width=True,
            hide_index=True
        )

        if not df.empty and "process_name" in df.columns:
            st.subheader("Top Memory-Consuming Processes")

            top = df.nlargest(
                10, "memory_mb"
            ) if "memory_mb" in df.columns else df.head(10)

            fig = px.bar(
                top,
                x="process_name",
                y="memory_mb",
                title="Top Processes by Memory Usage"
            )

            st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------
# ANOMALY DETECTION
# --------------------------------------------------

elif page == "Anomaly Detection":

    st.header("AI Anomaly Detection")

    if not system_anomalies.empty:

        st.subheader("System-Level Anomalies")

        if "anomaly" in system_anomalies.columns:
            counts = system_anomalies["anomaly"].value_counts()

            fig = px.pie(
                values=counts.values,
                names=counts.index,
                title="System Anomaly Distribution"
            )

            st.plotly_chart(fig, use_container_width=True)

        flagged = system_anomalies[
            system_anomalies["anomaly"] == "Anomaly"
        ] if "anomaly" in system_anomalies.columns else pd.DataFrame()

        st.dataframe(flagged, use_container_width=True)

    if not process_anomalies.empty:

        st.subheader("Process-Level Anomalies")

        flagged_processes = process_anomalies[
            process_anomalies["anomaly"] == "Anomaly"
        ]

        st.metric("Flagged Process Observations", len(flagged_processes))

        st.dataframe(
            flagged_processes.sort_values(
                "anomaly_score"
            ) if "anomaly_score" in flagged_processes.columns
            else flagged_processes,
            use_container_width=True,
            hide_index=True
        )


# --------------------------------------------------
# RESOURCE PREDICTION
# --------------------------------------------------

elif page == "Resource Prediction":

    st.header("AI Resource Prediction")

    if predictions.empty:
        st.info(
            "Test prediction results are not available. "
            "Run the resource prediction pipeline."
        )
    else:
        st.subheader("Model Test Predictions")
        st.dataframe(predictions, use_container_width=True)

    st.info(
        "The current Random Forest model uses historical lag features. "
        "Forecast reliability is preliminary because the current dataset "
        "contains only 40 system observations."
    )


# --------------------------------------------------
# DIAGNOSTIC CENTER
# --------------------------------------------------

elif page == "Diagnostic Center":

    st.header("Intelligent Diagnostic Center")

    report_file = os.path.join(DATA, "diagnostic_report.txt")

    if os.path.exists(report_file):
        with open(report_file, "r", encoding="utf-8") as file:
            st.code(file.read(), language="text")
    else:
        st.warning("Diagnostic report not found.")

    if not findings.empty:
        st.subheader("Diagnostic Findings")
        st.dataframe(findings, use_container_width=True)


# --------------------------------------------------
# RECOMMENDATION CENTER
# --------------------------------------------------

elif page == "Recommendation Center":

    st.header("Intelligent Recommendation Center")

    if recommendations.empty:
        st.warning("No recommendations available.")
    else:

        for index, item in recommendations.iterrows():

            priority = str(item.get("priority", "LOW"))

            with st.expander(
                f"{priority} | {item.get('target', 'System')}"
            ):
                st.write("**Observation**")
                st.write(item.get("observation", ""))

                st.write("**Recommendation**")
                st.write(item.get("recommendation", ""))

                st.write("**Reason**")
                st.write(item.get("reason", ""))

                st.write("**Suggested diagnostic commands**")
                st.code(
                    str(item.get("diagnostic_commands", "")),
                    language="bash"
                )

                st.warning(
                    "Recommendations are advisory. "
                    "No system action is performed from this dashboard."
                )


# --------------------------------------------------
# FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "AI Linux System | Intelligent System Monitoring "
    "| Anomaly Detection | Prediction | Diagnostics"
)
