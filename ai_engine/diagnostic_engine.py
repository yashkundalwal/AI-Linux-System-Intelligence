
import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime

# --------------------------------------------------
# FILE PATHS
# --------------------------------------------------

SYSTEM_FILE = "data/processed/system_anomaly_results.csv"
PROCESS_FILE = "data/processed/process_anomaly_results.csv"
TELEMETRY_FILE = "data/processed/clean_system_telemetry.csv"

PREDICTION_MODEL_FILE = "models/resource_prediction_model.joblib"

REPORT_FILE = "data/processed/diagnostic_report.txt"
FINDINGS_FILE = "data/processed/diagnostic_findings.csv"


def add_finding(findings, severity, category, observation,
                explanation, recommendation):

    findings.append({
        "severity": severity,
        "category": category,
        "observation": observation,
        "explanation": explanation,
        "recommendation": recommendation
    })


def generate_next_forecast():

    if not os.path.exists(PREDICTION_MODEL_FILE):
        return None

    if not os.path.exists(TELEMETRY_FILE):
        return None

    bundle = joblib.load(PREDICTION_MODEL_FILE)

    model = bundle["model"]
    features = bundle["features"]
    base_features = bundle["base_features"]
    lags = bundle["lags"]

    df = pd.read_csv(TELEMETRY_FILE)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], errors="coerce"
    )

    df = (
        df.dropna(subset=["timestamp"])
        .sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="last")
        .reset_index(drop=True)
    )

    if len(df) < lags:
        return None

    latest = df[base_features].tail(lags).copy()

    future_input = {}

    for lag in range(lags, 0, -1):

        row = latest.iloc[lags - lag]

        for col in base_features:
            future_input[f"{col}_lag_{lag}"] = row[col]

    X_future = pd.DataFrame(
        [future_input],
        columns=features
    ).replace([np.inf, -np.inf], np.nan)

    prediction = model.predict(X_future)[0]

    return {
        "cpu": float(np.clip(prediction[0], 0, 100)),
        "memory": float(np.clip(prediction[1], 0, 100))
    }


def main():

    print("=" * 65)
    print(" AI LINUX SYSTEM - INTELLIGENT DIAGNOSTIC ENGINE")
    print("=" * 65)

    findings = []

    # --------------------------------------------------
    # 1. LOAD SYSTEM ANOMALY RESULTS
    # --------------------------------------------------

    print("\n[1] Reading system anomaly results...")

    if not os.path.exists(SYSTEM_FILE):
        raise FileNotFoundError(
            "Run anomaly_detection.py first."
        )

    system_df = pd.read_csv(SYSTEM_FILE)

    system_df["timestamp"] = pd.to_datetime(
        system_df["timestamp"], errors="coerce"
    )

    system_df = system_df.dropna(
        subset=["timestamp"]
    ).sort_values("timestamp")

    if system_df.empty:
        raise ValueError("No valid system telemetry found.")

    latest_system = system_df.iloc[-1]

    cpu = float(latest_system["cpu_usage"])
    memory = float(latest_system["memory_usage"])
    temperature = float(latest_system["cpu_temperature"])
    load = float(latest_system["load_1"])
    running = int(latest_system["running_processes"])

    system_status = str(latest_system["anomaly"])

    print(f"Latest system sample: {latest_system['timestamp']}")
    print(f"CPU usage: {cpu:.2f}%")
    print(f"Memory usage: {memory:.2f}%")
    print(f"Temperature: {temperature:.2f} C")
    print(f"System anomaly status: {system_status}")

    # --------------------------------------------------
    # 2. SYSTEM DIAGNOSTICS
    # --------------------------------------------------

    print("\n[2] Analyzing system health...")

    if system_status == "Anomaly":
        add_finding(
            findings,
            "WARNING",
            "System behavior",
            "Latest system observation was flagged by Isolation Forest.",
            "The combination of system metrics differs from the patterns "
            "learned by the anomaly detection model.",
            "Inspect CPU, memory, load, temperature and active processes."
        )

    if cpu >= 85:
        add_finding(
            findings,
            "CRITICAL",
            "CPU utilization",
            f"CPU utilization is {cpu:.2f}%.",
            "CPU usage is above the configured high-utilization threshold.",
            "Identify CPU-intensive processes before taking action."
        )

    elif cpu >= 70:
        add_finding(
            findings,
            "WARNING",
            "CPU utilization",
            f"CPU utilization is {cpu:.2f}%.",
            "CPU usage is elevated.",
            "Monitor processes with high CPU consumption."
        )

    if memory >= 90:
        add_finding(
            findings,
            "CRITICAL",
            "Memory utilization",
            f"Memory utilization is {memory:.2f}%.",
            "Available memory may be limited.",
            "Inspect memory-heavy processes and memory pressure."
        )

    elif memory >= 80:
        add_finding(
            findings,
            "WARNING",
            "Memory utilization",
            f"Memory utilization is {memory:.2f}%.",
            "Memory utilization is elevated.",
            "Monitor memory consumption and swap activity."
        )

    if pd.notna(temperature) and temperature >= 85:
        add_finding(
            findings,
            "CRITICAL",
            "Temperature",
            f"Reported sensor temperature is {temperature:.2f} C.",
            "The reported temperature is above the configured threshold.",
            "Check thermal conditions, cooling and sensor identity."
        )

    elif pd.notna(temperature) and temperature >= 75:
        add_finding(
            findings,
            "WARNING",
            "Temperature",
            f"Reported sensor temperature is {temperature:.2f} C.",
            "The reported temperature is elevated.",
            "Continue monitoring temperature and system workload."
        )

    # --------------------------------------------------
    # 3. PROCESS DIAGNOSTICS
    # --------------------------------------------------

    print("\n[3] Analyzing process behavior...")

    if not os.path.exists(PROCESS_FILE):
        raise FileNotFoundError(
            "Run process_anomaly_detection.py first."
        )

    process_df = pd.read_csv(PROCESS_FILE)

    process_df["timestamp"] = pd.to_datetime(
        process_df["timestamp"], errors="coerce"
    )

    process_df = process_df.dropna(
        subset=["timestamp"]
    )

    if not process_df.empty:

        latest_process_time = process_df["timestamp"].max()

        latest_processes = process_df[
            process_df["timestamp"] == latest_process_time
        ]

        anomalous_processes = latest_processes[
            latest_processes["anomaly"] == "Anomaly"
        ]

        print(f"Latest process sample: {latest_process_time}")
        print(f"Processes sampled: {len(latest_processes)}")
        print(f"Flagged processes: {len(anomalous_processes)}")

        for _, process in anomalous_processes.iterrows():

            name = str(process["process_name"])
            pid = process["pid"]
            process_cpu = pd.to_numeric(
                process["cpu_percent"], errors="coerce"
            )
            process_memory = pd.to_numeric(
                process["memory_mb"], errors="coerce"
            )

            observation = (
                f"{name} (PID {pid}) was flagged as unusual."
            )

            explanation = (
                "Its CPU, memory or thread behavior differs "
                "from the learned behavior of this process name."
            )

            recommendation = (
                "Inspect this process and compare its behavior "
                "with earlier observations before taking action."
            )

            if pd.notna(process_cpu) and process_cpu >= 80:
                observation += (
                    f" CPU usage: {process_cpu:.2f}%."
                )

            if pd.notna(process_memory) and process_memory >= 500:
                observation += (
                    f" Memory usage: {process_memory:.2f} MB."
                )

            add_finding(
                findings,
                "WARNING",
                "Process anomaly",
                observation,
                explanation,
                recommendation
            )

    # --------------------------------------------------
    # 4. RESOURCE PREDICTION
    # --------------------------------------------------

    print("\n[4] Analyzing predicted resource usage...")

    forecast = generate_next_forecast()

    if forecast is not None:

        predicted_cpu = forecast["cpu"]
        predicted_memory = forecast["memory"]

        print(f"Predicted CPU: {predicted_cpu:.2f}%")
        print(f"Predicted memory: {predicted_memory:.2f}%")

        if predicted_cpu >= 85:
            add_finding(
                findings,
                "WARNING",
                "CPU forecast",
                f"Predicted CPU usage is {predicted_cpu:.2f}%.",
                "The prediction model forecasts high CPU utilization "
                "in the next observation.",
                "Monitor CPU-intensive processes and verify the forecast "
                "with subsequent measurements."
            )

        if predicted_memory >= 90:
            add_finding(
                findings,
                "WARNING",
                "Memory forecast",
                f"Predicted memory usage is {predicted_memory:.2f}%.",
                "The prediction model forecasts high memory utilization.",
                "Monitor memory consumption and verify the forecast "
                "with subsequent measurements."
            )

    else:
        predicted_cpu = None
        predicted_memory = None
        print("Prediction unavailable.")

    # --------------------------------------------------
    # 5. OVERALL HEALTH STATUS
    # --------------------------------------------------

    print("\n[5] Generating overall diagnosis...")

    critical_count = sum(
        1 for item in findings
        if item["severity"] == "CRITICAL"
    )

    warning_count = sum(
        1 for item in findings
        if item["severity"] == "WARNING"
    )

    if critical_count > 0:
        health_status = "CRITICAL"
    elif warning_count > 0:
        health_status = "WARNING"
    else:
        health_status = "NORMAL"

    # --------------------------------------------------
    # 6. SAVE REPORT
    # --------------------------------------------------

    os.makedirs("data/processed", exist_ok=True)

    report = []

    report.append("=" * 65)
    report.append("AI LINUX SYSTEM - DIAGNOSTIC REPORT")
    report.append("=" * 65)

    report.append(
        f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

    report.append(f"Overall health status: {health_status}")

    report.append("\nSYSTEM SNAPSHOT")
    report.append("-" * 40)
    report.append(f"CPU utilization: {cpu:.2f}%")
    report.append(f"Memory utilization: {memory:.2f}%")
    report.append(f"Load average (1 min): {load:.2f}")
    report.append(f"Running processes: {running}")
    report.append(f"Reported temperature: {temperature:.2f} C")
    report.append(f"System anomaly model: {system_status}")

    report.append("\nRESOURCE FORECAST")
    report.append("-" * 40)

    if forecast is not None:
        report.append(f"Predicted CPU: {predicted_cpu:.2f}%")
        report.append(f"Predicted memory: {predicted_memory:.2f}%")
    else:
        report.append("Forecast unavailable.")

    report.append("\nDIAGNOSTIC FINDINGS")
    report.append("-" * 40)

    if not findings:
        report.append("No rule-based warnings or anomalies found.")
    else:
        for index, item in enumerate(findings, start=1):
            report.append(f"\n{index}. [{item['severity']}] {item['category']}")
            report.append(f"Observation: {item['observation']}")
            report.append(f"Explanation: {item['explanation']}")
            report.append(f"Recommendation: {item['recommendation']}")

    report.append("\n" + "=" * 65)
    report.append("End of diagnostic report")
    report.append("=" * 65)

    report_text = "\n".join(report)

    with open(REPORT_FILE, "w", encoding="utf-8") as file:
        file.write(report_text)

    pd.DataFrame(findings).to_csv(
        FINDINGS_FILE,
        index=False
    )

    # --------------------------------------------------
    # 7. DISPLAY REPORT
    # --------------------------------------------------

    print("\n" + report_text)

    print(f"\nReport saved: {REPORT_FILE}")
    print(f"Findings saved: {FINDINGS_FILE}")

    print("\nDiagnostic engine completed successfully.")


if __name__ == "__main__":
    main()
