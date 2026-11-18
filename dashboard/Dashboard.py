
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
    st.caption("Live hardware telemetry, resource utilization and network activity")

    if system_df.empty:
        st.warning("System telemetry unavailable.")
    else:
        chart_data = system_df.copy()

        if "timestamp" in chart_data.columns:
            chart_data["timestamp"] = pd.to_datetime(
                chart_data["timestamp"], errors="coerce"
            )
            chart_data = chart_data.dropna(subset=["timestamp"])
            chart_data = chart_data.sort_values("timestamp")

        numeric_columns = [
            "cpu_usage", "memory_usage", "disk_usage",
            "cpu_temperature", "cpu_frequency_mhz", "battery_percent",
            "load_1", "load_5", "load_15",
            "total_processes", "running_processes",
            "network_rx_bytes", "network_tx_bytes"
        ]
        for column in numeric_columns:
            if column in chart_data.columns:
                chart_data[column] = pd.to_numeric(
                    chart_data[column], errors="coerce"
                )

        if not chart_data.empty and "timestamp" in chart_data.columns:
            window_label = st.selectbox(
                "Chart time window",
                ["Last 15 minutes", "Last 1 hour", "Last 6 hours", "All available data"],
                index=2
            )
            window_minutes = {
                "Last 15 minutes": 15,
                "Last 1 hour": 60,
                "Last 6 hours": 360
            }
            if window_label in window_minutes:
                cutoff = chart_data["timestamp"].max() - pd.Timedelta(
                    minutes=window_minutes[window_label]
                )
                chart_data = chart_data[chart_data["timestamp"] >= cutoff].copy()

        if chart_data.empty:
            st.warning("No valid timestamped system telemetry is available.")
        else:
            latest = chart_data.iloc[-1]

            def metric_value(column):
                value = latest.get(column, None)
                if value is None or pd.isna(value):
                    return None
                return float(value)

            def display_metric(container, label, column, suffix="", precision=1):
                value = metric_value(column)
                if value is None:
                    container.metric(label, "Unavailable")
                else:
                    container.metric(label, f"{value:.{precision}f}{suffix}")

            st.subheader("Hardware Health")
            cards = st.columns(6)
            display_metric(cards[0], "CPU Usage", "cpu_usage", "%", 2)
            display_metric(cards[1], "Memory Usage", "memory_usage", "%", 2)
            display_metric(cards[2], "Disk Usage", "disk_usage", "%", 2)
            display_metric(cards[3], "CPU Temperature", "cpu_temperature", " °C", 1)
            display_metric(cards[4], "CPU Frequency", "cpu_frequency_mhz", " MHz", 0)
            display_metric(cards[5], "Battery", "battery_percent", "%", 1)

            st.subheader("System Health Status")
            st.caption(
                "Advisory indicators only. Thresholds are generic dashboard defaults, "
                "not manufacturer-specific hardware safety limits."
            )

            def health_state(column, warning_at, critical_at=None, lower_is_bad=False):
                value = metric_value(column)
                if value is None:
                    return "Unavailable"
                if lower_is_bad:
                    if value <= warning_at:
                        return "Critical" if critical_at is None or value <= critical_at else "Warning"
                    return "Normal"
                if critical_at is not None and value >= critical_at:
                    return "Critical"
                if value >= warning_at:
                    return "Warning"
                return "Normal"

            health_checks = [
                ("CPU utilization", "cpu_usage", 80, 95, False),
                ("Memory utilization", "memory_usage", 85, 95, False),
                ("Disk utilization", "disk_usage", 85, 95, False),
                ("CPU temperature", "cpu_temperature", 75, 90, False),
                ("Battery level", "battery_percent", 20, 10, True),
            ]

            health_rows = []
            for label, column, warning_at, critical_at, lower_is_bad in health_checks:
                state = health_state(
                    column, warning_at, critical_at, lower_is_bad
                )
                value = metric_value(column)
                if value is None:
                    reading = "Unavailable"
                elif column == "cpu_temperature":
                    reading = f"{value:.1f} °C"
                else:
                    reading = f"{value:.1f}%"
                health_rows.append({
                    "Component": label,
                    "Current reading": reading,
                    "Status": state
                })

            health_df = pd.DataFrame(health_rows)
            st.dataframe(
                health_df,
                use_container_width=True,
                hide_index=True
            )

            st.divider()
            st.subheader("Resource Utilization Trends")

            resource_columns = [
                column for column in ["cpu_usage", "memory_usage", "disk_usage"]
                if column in chart_data.columns
            ]
            if resource_columns and "timestamp" in chart_data.columns:
                resource_layout = st.columns(2)
                resource_titles = {
                    "cpu_usage": ("CPU Utilization", "CPU (%)"),
                    "memory_usage": ("Memory Utilization", "Memory (%)"),
                    "disk_usage": ("Disk Utilization", "Disk (%)")
                }
                for index, column in enumerate(resource_columns):
                    plot_data = chart_data[
                        ["timestamp", column]
                    ].dropna().copy()
                    if plot_data.empty:
                        continue
                    title, y_label = resource_titles.get(
                        column, (column.replace("_", " ").title(), "Usage (%)")
                    )
                    fig = px.line(
                        plot_data,
                        x="timestamp",
                        y=column,
                        title=title,
                        labels={column: y_label}
                    )
                    fig.update_layout(hovermode="x unified")
                    resource_layout[index % 2].plotly_chart(
                        fig, use_container_width=True
                    )
            else:
                st.info("Resource utilization trend data is unavailable.")

            st.subheader("Hardware Performance Trends")

            summary_columns = st.columns(2)
            for container, column, label, unit in [
                (summary_columns[0], "cpu_temperature", "Temperature", "°C"),
                (summary_columns[1], "cpu_frequency_mhz", "CPU frequency", "MHz")
            ]:
                if column in chart_data.columns:
                    values = chart_data[column].dropna()
                    if not values.empty:
                        container.caption(
                            f"{label} · Latest {values.iloc[-1]:.1f} {unit}  |  "
                            f"Min {values.min():.1f} {unit}  |  "
                            f"Max {values.max():.1f} {unit}"
                        )
                    else:
                        container.caption(f"{label}: no valid readings in this window")

            left, right = st.columns(2)

            if "cpu_temperature" in chart_data.columns:
                temp_data = chart_data[["timestamp", "cpu_temperature"]].dropna()
                if not temp_data.empty:
                    temp_fig = px.line(
                        temp_data, x="timestamp", y="cpu_temperature",
                        title="CPU Temperature",
                        labels={"cpu_temperature": "Temperature (°C)"}
                    )
                    left.plotly_chart(temp_fig, use_container_width=True)
                else:
                    left.info("CPU temperature readings are unavailable.")
            else:
                left.info("CPU temperature telemetry is unavailable.")

            if "cpu_frequency_mhz" in chart_data.columns:
                frequency_data = chart_data[
                    ["timestamp", "cpu_frequency_mhz"]
                ].dropna()
                if not frequency_data.empty:
                    frequency_fig = px.line(
                        frequency_data, x="timestamp", y="cpu_frequency_mhz",
                        title="CPU Frequency",
                        labels={"cpu_frequency_mhz": "Frequency (MHz)"}
                    )
                    right.plotly_chart(frequency_fig, use_container_width=True)
                else:
                    right.info("CPU frequency readings are unavailable.")
            else:
                right.info("CPU frequency telemetry is unavailable.")

            st.subheader("Network Activity")
            rx_col, tx_col = st.columns(2)
            network_available = all(
                column in chart_data.columns
                for column in ["timestamp", "network_rx_bytes", "network_tx_bytes"]
            )

            if network_available:
                network_data = chart_data[
                    ["timestamp", "network_rx_bytes", "network_tx_bytes"]
                ].dropna().copy()

                if len(network_data) >= 2:
                    elapsed = network_data["timestamp"].diff().dt.total_seconds()
                    rx_delta = network_data["network_rx_bytes"].diff()
                    tx_delta = network_data["network_tx_bytes"].diff()
                    valid = elapsed.gt(0) & rx_delta.ge(0) & tx_delta.ge(0)

                    network_data["Download (MB/s)"] = (
                        rx_delta / elapsed / (1024 ** 2)
                    ).where(valid)
                    network_data["Upload (MB/s)"] = (
                        tx_delta / elapsed / (1024 ** 2)
                    ).where(valid)

                    network_data["Download 3-sample avg (MB/s)"] = (
                        network_data["Download (MB/s)"].rolling(
                            window=3, min_periods=1
                        ).mean()
                    )
                    network_data["Upload 3-sample avg (MB/s)"] = (
                        network_data["Upload (MB/s)"].rolling(
                            window=3, min_periods=1
                        ).mean()
                    )

                    latest_network = network_data.iloc[-1]
                    download = latest_network["Download (MB/s)"]
                    upload = latest_network["Upload (MB/s)"]

                    rx_col.metric(
                        "Download Speed",
                        f"{download:.3f} MB/s" if pd.notna(download)
                        else "Waiting for next sample"
                    )
                    tx_col.metric(
                        "Upload Speed",
                        f"{upload:.3f} MB/s" if pd.notna(upload)
                        else "Waiting for next sample"
                    )

                    network_plot = network_data.melt(
                        id_vars="timestamp",
                        value_vars=[
                            "Download (MB/s)", "Upload (MB/s)",
                            "Download 3-sample avg (MB/s)",
                            "Upload 3-sample avg (MB/s)"
                        ],
                        var_name="Direction",
                        value_name="Throughput (MB/s)"
                    ).dropna(subset=["Throughput (MB/s)"])

                    if not network_plot.empty:
                        network_fig = px.line(
                            network_plot, x="timestamp",
                            y="Throughput (MB/s)", color="Direction",
                            title="Network Throughput Over Time"
                        )
                        network_fig.update_layout(hovermode="x unified")
                        st.plotly_chart(network_fig, use_container_width=True)
                    else:
                        st.info(
                            "No valid network intervals yet. Throughput appears "
                            "after consecutive telemetry samples."
                        )
                else:
                    rx_col.metric("Download Speed", "Waiting for samples")
                    tx_col.metric("Upload Speed", "Waiting for samples")
                    st.info("At least two telemetry samples are needed to calculate throughput.")
            else:
                rx_col.metric("Download Speed", "Unavailable")
                tx_col.metric("Upload Speed", "Unavailable")
                st.info("Network RX/TX counters are not present in the telemetry file.")

            st.subheader("System Load and Process Information")
            info_columns = [
                "load_1", "load_5", "load_15",
                "total_processes", "running_processes"
            ]
            available_info = [
                column for column in info_columns if column in chart_data.columns
            ]

            if available_info:
                info_cards = st.columns(len(available_info))
                labels = {
                    "load_1": "Load Average (1 min)",
                    "load_5": "Load Average (5 min)",
                    "load_15": "Load Average (15 min)",
                    "total_processes": "Total Processes",
                    "running_processes": "Running Processes"
                }
                for card, column in zip(info_cards, available_info):
                    value = latest.get(column)
                    if pd.isna(value):
                        card.metric(labels[column], "Unavailable")
                    elif column in ["total_processes", "running_processes"]:
                        card.metric(labels[column], f"{value:.0f}")
                    else:
                        card.metric(labels[column], f"{value:.2f}")
            else:
                st.info("System load and process statistics are unavailable.")

            with st.expander("View recent raw hardware telemetry"):
                raw_columns = [
                    "timestamp", "cpu_temperature", "cpu_frequency_mhz",
                    "battery_percent", "disk_usage",
                    "network_rx_bytes", "network_tx_bytes"
                ]
                available_raw = [
                    column for column in raw_columns if column in chart_data.columns
                ]
                if available_raw:
                    st.dataframe(
                        chart_data[available_raw].tail(20),
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.info("No hardware telemetry columns are available.")


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
    "| Hardware Health | Network Analytics | Anomaly Detection | Prediction | Diagnostics"
)
