
import os
import pandas as pd

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

FINDINGS_FILE = "data/processed/diagnostic_findings.csv"
PROCESS_FILE = "data/processed/process_anomaly_results.csv"

OUTPUT_CSV = "data/processed/recommendations.csv"
OUTPUT_REPORT = "data/processed/recommendation_report.txt"

SEVERITY_ORDER = {
    "CRITICAL": 1,
    "WARNING": 2,
    "INFO": 3
}


def create_recommendation(
    priority,
    category,
    target,
    observation,
    recommendation,
    commands,
    reason
):
    return {
        "priority": priority,
        "category": category,
        "target": target,
        "observation": observation,
        "recommendation": recommendation,
        "diagnostic_commands": commands,
        "reason": reason,
        "requires_user_approval": "Yes"
    }


def get_process_recommendations():

    recommendations = []

    if not os.path.exists(PROCESS_FILE):
        print("Process anomaly results unavailable.")
        return recommendations

    df = pd.read_csv(PROCESS_FILE)

    required = [
        "timestamp",
        "pid",
        "process_name",
        "cpu_percent",
        "memory_mb",
        "anomaly"
    ]

    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(
            f"Missing process columns: {missing}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], errors="coerce"
    )

    df = df.dropna(subset=["timestamp"])

    if df.empty:
        return recommendations

    # Use only the latest process snapshot
    latest_timestamp = df["timestamp"].max()

    latest = df[
        df["timestamp"] == latest_timestamp
    ]

    anomalies = latest[
        latest["anomaly"] == "Anomaly"
    ]

    for _, process in anomalies.iterrows():

        pid = int(process["pid"])
        name = str(process["process_name"])

        cpu = pd.to_numeric(
            process["cpu_percent"], errors="coerce"
        )

        memory = pd.to_numeric(
            process["memory_mb"], errors="coerce"
        )

        target = f"{name} (PID {pid})"

        observation_parts = [
            "Process was flagged by its process-specific anomaly model."
        ]

        commands = [
            f"ps -p {pid} -o pid,ppid,stat,%cpu,%mem,rss,etime,cmd",
            f"top -b -n 1 -p {pid}"
        ]

        if pd.notna(cpu):
            observation_parts.append(
                f"CPU usage: {cpu:.2f}%"
            )

        if pd.notna(memory):
            observation_parts.append(
                f"Memory usage: {memory:.2f} MB"
            )

        # Prioritize unusually high resource consumption
        if pd.notna(cpu) and cpu >= 80:

            priority = "HIGH"

            recommendation = (
                "Inspect the process's CPU activity, identify its "
                "parent process, and determine whether the workload "
                "is expected. Do not terminate it automatically."
            )

            reason = (
                "The process was statistically flagged and its "
                "observed CPU consumption is at least 80% of one "
                "logical CPU core."
            )

        elif pd.notna(memory) and memory >= 500:

            priority = "MEDIUM"

            recommendation = (
                "Inspect the process's memory consumption and "
                "check whether the application workload explains it. "
                "Monitor for continued memory growth."
            )

            reason = (
                "The process was statistically flagged and is "
                "currently consuming at least 500 MB of RAM."
            )

        else:

            priority = "LOW"

            recommendation = (
                "Review the process's recent behavior and compare "
                "its CPU, memory and thread usage with earlier samples."
            )

            reason = (
                "The process differs from its learned baseline, "
                "but no high CPU or memory threshold was reached."
            )

        recommendations.append(
            create_recommendation(
                priority=priority,
                category="Process investigation",
                target=target,
                observation="; ".join(observation_parts),
                recommendation=recommendation,
                commands=commands,
                reason=reason
            )
        )

    return recommendations


def get_system_recommendations(findings):

    recommendations = []

    for _, finding in findings.iterrows():

        severity = str(finding["severity"]).upper()
        category = str(finding["category"])
        observation = str(finding["observation"])

        explanation = str(finding["explanation"])

        # Avoid duplicate process recommendations:
        # process-specific recommendations are generated separately.
        if category == "Process anomaly":
            continue

        commands = []
        recommendation = str(finding["recommendation"])

        if category in ["CPU utilization", "CPU forecast"]:

            priority = (
                "HIGH" if severity == "CRITICAL" else "MEDIUM"
            )

            commands = [
                "top -o %CPU",
                "ps aux --sort=-%cpu | head -n 15",
                "uptime"
            ]

        elif category in ["Memory utilization", "Memory forecast"]:

            priority = (
                "HIGH" if severity == "CRITICAL" else "MEDIUM"
            )

            commands = [
                "free -h",
                "ps aux --sort=-%mem | head -n 15",
                "cat /proc/meminfo"
            ]

        elif category == "Temperature":

            priority = (
                "HIGH" if severity == "CRITICAL" else "MEDIUM"
            )

            commands = [
                "find /sys/class/thermal -name 'temp' -type f",
                "cat /sys/class/thermal/thermal_zone0/temp"
            ]

            recommendation = (
                "Verify which hardware sensor produced the reading. "
                "Inspect cooling and workload before changing anything."
            )

        elif category == "System behavior":

            priority = "MEDIUM"

            commands = [
                "uptime",
                "free -h",
                "df -h",
                "ps aux --sort=-%cpu | head -n 15"
            ]

        else:
            priority = "LOW"

        recommendations.append(
            create_recommendation(
                priority=priority,
                category=category,
                target="System",
                observation=observation,
                recommendation=recommendation,
                commands=commands,
                reason=explanation
            )
        )

    return recommendations


def main():

    print("=" * 65)
    print(" AI LINUX SYSTEM - INTELLIGENT RECOMMENDATION ENGINE")
    print("=" * 65)

    # 1. Load diagnostic findings
    print("\n[1] Loading diagnostic findings...")

    if not os.path.exists(FINDINGS_FILE):
        raise FileNotFoundError(
            "Diagnostic findings not found. "
            "Run diagnostic_engine.py first."
        )

    findings = pd.read_csv(FINDINGS_FILE)

    print(f"Loaded {len(findings)} diagnostic findings.")

    # 2. Generate recommendations
    print("\n[2] Generating system recommendations...")

    system_recommendations = get_system_recommendations(
        findings
    )

    process_recommendations = get_process_recommendations()

    recommendations = (
        system_recommendations + process_recommendations
    )

    # 3. Sort recommendations by priority
    priority_order = {
        "HIGH": 1,
        "MEDIUM": 2,
        "LOW": 3
    }

    recommendations.sort(
        key=lambda item: priority_order.get(
            item["priority"], 4
        )
    )

    print(
        f"Generated {len(recommendations)} recommendations."
    )

    # 4. Save recommendations
    os.makedirs("data/processed", exist_ok=True)

    result_df = pd.DataFrame(recommendations)

    result_df.to_csv(
        OUTPUT_CSV,
        index=False
    )

    # 5. Generate readable report
    report = []

    report.append("=" * 65)
    report.append("AI LINUX SYSTEM - RECOMMENDATION REPORT")
    report.append("=" * 65)

    report.append(
        f"Total recommendations: {len(recommendations)}"
    )

    report.append(
        "Recommendations are advisory and require user approval."
    )

    for index, item in enumerate(recommendations, start=1):

        report.append("\n" + "-" * 65)

        report.append(
            f"{index}. [{item['priority']}] {item['category']}"
        )

        report.append(f"Target: {item['target']}")
        report.append(f"Observation: {item['observation']}")
        report.append(f"Reason: {item['reason']}")

        report.append(
            f"Recommendation: {item['recommendation']}"
        )

        report.append("\nSuggested read-only diagnostic commands:")

        if item["diagnostic_commands"]:

            for command in item["diagnostic_commands"]:
                report.append(f"  $ {command}")

        else:
            report.append("  No additional command suggested.")

        report.append("Approval required before any system action: YES")

    if not recommendations:
        report.append(
            "\nNo recommendations generated from current findings."
        )

    report.append("\n" + "=" * 65)
    report.append("End of recommendation report")
    report.append("=" * 65)

    report_text = "\n".join(report)

    with open(
        OUTPUT_REPORT,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(report_text)

    # 6. Display report
    print("\n" + report_text)

    print(f"\nCSV saved: {OUTPUT_CSV}")
    print(f"Report saved: {OUTPUT_REPORT}")

    print("\nRecommendation engine completed successfully.")


if __name__ == "__main__":
    main()
