
import os
import pandas as pd
import numpy as np

SYSTEM_FILE = "data/system_telemetry_v2.csv"
PROCESS_FILE = "data/process_telemetry.csv"

OUTPUT_DIR = "data/processed"

# Validate the latest 100 system collection cycles.
SYNC_CHECK_LAST_N = 100

os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_system_data():
    print("\n[1] Loading system telemetry...")

    df = pd.read_csv(SYSTEM_FILE)

    required_columns = [
        "timestamp",
        "cpu_usage",
        "memory_usage",
        "load_1",
        "load_5",
        "load_15",
        "total_processes",
        "running_processes",
        "disk_usage",
        "network_rx_bytes",
        "network_tx_bytes",
        "cpu_temperature",
        "cpu_frequency_mhz",
        "battery_percent"
    ]

    missing = set(required_columns) - set(df.columns)

    if missing:
        raise ValueError(
            f"System telemetry missing columns: {missing}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], errors="coerce"
    )

    df = df.dropna(subset=["timestamp"])

    numeric_columns = [
        col for col in required_columns
        if col != "timestamp"
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Negative values are unavailable sensor readings.
    unavailable_columns = [
        "cpu_usage",
        "memory_usage",
        "load_1",
        "load_5",
        "load_15",
        "disk_usage",
        "cpu_temperature",
        "cpu_frequency_mhz",
        "battery_percent"
    ]

    for col in unavailable_columns:
        df.loc[df[col] < 0, col] = np.nan

    df = df.sort_values("timestamp")

    df = df.drop_duplicates(
        subset=["timestamp"], keep="last"
    )

    # Network counters are cumulative.
    # Calculate traffic rate between consecutive samples.
    elapsed = df["timestamp"].diff().dt.total_seconds()

    rx_diff = df["network_rx_bytes"].diff()
    tx_diff = df["network_tx_bytes"].diff()

    df["network_rx_bytes_per_sec"] = (
        rx_diff.where((rx_diff >= 0) & (elapsed > 0)) / elapsed
    )

    df["network_tx_bytes_per_sec"] = (
        tx_diff.where((tx_diff >= 0) & (elapsed > 0)) / elapsed
    )

    print("System telemetry loaded:", df.shape)

    return df


def load_process_data():
    print("\n[2] Loading process telemetry...")

    df = pd.read_csv(PROCESS_FILE)

    required_columns = [
        "timestamp",
        "pid",
        "process_name",
        "state",
        "cpu_percent",
        "memory_mb",
        "threads"
    ]

    missing = set(required_columns) - set(df.columns)

    if missing:
        raise ValueError(
            f"Process telemetry missing columns: {missing}"
        )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], errors="coerce"
    )

    df = df.dropna(
        subset=["timestamp", "pid", "process_name"]
    )

    numeric_columns = [
        "pid",
        "cpu_percent",
        "memory_mb",
        "threads"
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # -1 means CPU usage was not available
    # for the first observation of a process.
    df.loc[df["cpu_percent"] < 0, "cpu_percent"] = np.nan

    df.loc[df["memory_mb"] < 0, "memory_mb"] = np.nan
    df.loc[df["threads"] < 0, "threads"] = np.nan

    df = df.sort_values(
        ["timestamp", "pid"]
    )

    df = df.drop_duplicates(
        subset=["timestamp", "pid"],
        keep="last"
    )

    print("Process telemetry loaded:", df.shape)

    return df


def validate_synchronization(system_df, process_df):
    print("\n[3] VALIDATING TELEMETRY SYNCHRONIZATION")

    if system_df.empty:
        raise ValueError(
            "Synchronization failed: no system telemetry available."
        )

    if process_df.empty:
        raise ValueError(
            "Synchronization failed: no process telemetry available."
        )

    # Select the latest N system collection timestamps.
    latest_system_times = (
        system_df["timestamp"]
        .drop_duplicates()
        .sort_values()
        .tail(SYNC_CHECK_LAST_N)
    )

    start_time = latest_system_times.min()
    end_time = latest_system_times.max()

    # Get process records belonging to the same time window.
    process_window = process_df[
        (process_df["timestamp"] >= start_time) &
        (process_df["timestamp"] <= end_time)
    ]

    system_times = set(latest_system_times)
    process_times = set(process_window["timestamp"].unique())

    matching_times = system_times & process_times

    unmatched_system = system_times - process_times
    unmatched_process = process_times - system_times

    percentage = (
        len(matching_times) / len(system_times) * 100
        if system_times else 0
    )

    print("System samples checked:", len(system_times))
    print("Process timestamps checked:", len(process_times))
    print("Matching timestamps:", len(matching_times))
    print("Unmatched system timestamps:", len(unmatched_system))
    print("Unmatched process timestamps:", len(unmatched_process))
    print(f"Synchronization: {percentage:.2f}%")

    if unmatched_system or unmatched_process:
        print("\nSynchronization validation FAILED.")

        if unmatched_system:
            print(
                "Missing process timestamps:",
                sorted(unmatched_system)[:5]
            )

        if unmatched_process:
            print(
                "Unexpected process timestamps:",
                sorted(unmatched_process)[:5]
            )

        raise ValueError(
            "System and process telemetry are not synchronized. "
            "Check the unified telemetry collector."
        )

    # Ensure each system sample has at least one process record.
    process_counts = process_window.groupby("timestamp").size()

    if (process_counts == 0).any():
        raise ValueError(
            "Synchronization failed: some samples contain no process records."
        )

    print("Synchronization validation PASSED.")
    print("Latest telemetry window is aligned.")

    return True


def generate_system_summary(df):
    print("\n[4] SYSTEM SUMMARY")

    columns = [
        "cpu_usage",
        "memory_usage",
        "disk_usage",
        "cpu_temperature",
        "cpu_frequency_mhz",
        "battery_percent"
    ]

    summary = df[columns].describe().T

    print(summary)

    return summary


def generate_process_summary(df):
    print("\n[5] TOP RESOURCE-CONSUMING PROCESSES")

    summary = (
        df.groupby("process_name")
        .agg(
            average_cpu=("cpu_percent", "mean"),
            maximum_cpu=("cpu_percent", "max"),
            average_memory=("memory_mb", "mean"),
            maximum_memory=("memory_mb", "max"),
            average_threads=("threads", "mean")
        )
        .sort_values(
            "maximum_cpu", ascending=False
        )
    )

    print(summary.head(15))

    return summary


def save_processed_data(system_df, process_df):
    print("\n[6] Saving processed datasets...")

    system_path = os.path.join(
        OUTPUT_DIR, "clean_system_telemetry.csv"
    )

    process_path = os.path.join(
        OUTPUT_DIR, "clean_process_telemetry.csv"
    )

    system_df.to_csv(system_path, index=False)
    process_df.to_csv(process_path, index=False)

    print("Saved:", system_path)
    print("Saved:", process_path)


def main():
    print("======================================")
    print(" AI LINUX SYSTEM - DATA PREPROCESSING")
    print("======================================")

    system_df = load_system_data()
    process_df = load_process_data()

    # Stop the AI pipeline if synchronization is invalid.
    validate_synchronization(system_df, process_df)

    generate_system_summary(system_df)
    generate_process_summary(process_df)

    save_processed_data(system_df, process_df)

    print("\nPreprocessing completed successfully.")


if __name__ == "__main__":
    main()
