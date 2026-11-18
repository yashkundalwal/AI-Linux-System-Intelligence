
import os
import csv
import subprocess
import sys
import time
from datetime import datetime

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

PERFORMANCE_DIR = os.path.join(
    PROJECT_ROOT, "data", "processed"
)

PERFORMANCE_FILE = os.path.join(
    PERFORMANCE_DIR, "pipeline_performance.csv"
)

PIPELINE = [
    ("Data preprocessing", "ai_engine/data_preprocessing.py"),
    ("System anomaly detection", "ai_engine/anomaly_detection.py"),
    ("Process anomaly detection", "ai_engine/process_anomaly_detection.py"),
    ("Resource prediction", "ai_engine/resource_prediction.py"),
    ("Diagnostic engine", "ai_engine/diagnostic_engine.py"),
    ("Recommendation engine", "ai_engine/recommendation_engine.py"),
    ("Action queue export", "ai_engine/export_action_queue.py")
]

CSV_FIELDS = [
    "run_id",
    "timestamp",
    "stage",
    "script",
    "duration_seconds",
    "status",
    "return_code"
]


def save_performance(records):
    """Append profiling records to the performance CSV."""

    os.makedirs(PERFORMANCE_DIR, exist_ok=True)

    file_exists = (
        os.path.exists(PERFORMANCE_FILE)
        and os.path.getsize(PERFORMANCE_FILE) > 0
    )

    with open(
        PERFORMANCE_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=CSV_FIELDS
        )

        if not file_exists:
            writer.writeheader()

        writer.writerows(records)


def run_stage(name, script, run_id):
    print("\n" + "=" * 65, flush=True)
    print(f"RUNNING: {name}", flush=True)
    print("=" * 65, flush=True)

    start_time = time.perf_counter()
    start_timestamp = datetime.now().isoformat(timespec="seconds")

    try:
        result = subprocess.run(
            [sys.executable, script],
            cwd=PROJECT_ROOT
        )

        return_code = result.returncode

    except Exception as error:
        print(f"\nERROR: Could not execute {name}: {error}", flush=True)
        return_code = -1

    duration = time.perf_counter() - start_time

    status = "SUCCESS" if return_code == 0 else "FAILED"

    print(
        f"\n{status}: {name}",
        flush=True
    )

    print(
        f"Execution time: {duration:.2f} seconds",
        flush=True
    )

    record = {
        "run_id": run_id,
        "timestamp": start_timestamp,
        "stage": name,
        "script": script,
        "duration_seconds": round(duration, 3),
        "status": status,
        "return_code": return_code
    }

    return return_code == 0, record


def main():

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    pipeline_start = time.perf_counter()

    pipeline_timestamp = datetime.now().isoformat(
        timespec="seconds"
    )

    records = []

    print("\n" + "=" * 65, flush=True)
    print("AI LINUX SYSTEM - LIVE AI PIPELINE", flush=True)
    print("Run ID:", run_id, flush=True)
    print("Started:", pipeline_timestamp, flush=True)
    print("=" * 65, flush=True)

    pipeline_success = True

    for name, script in PIPELINE:

        success, record = run_stage(
            name,
            script,
            run_id
        )

        records.append(record)

        if not success:
            pipeline_success = False
            print(
                "\nAI pipeline stopped due to an error.",
                flush=True
            )
            break

    total_duration = time.perf_counter() - pipeline_start

    final_status = (
        "SUCCESS" if pipeline_success else "FAILED"
    )

    records.append({
        "run_id": run_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "stage": "TOTAL PIPELINE",
        "script": "run_live_pipeline.py",
        "duration_seconds": round(total_duration, 3),
        "status": final_status,
        "return_code": 0 if pipeline_success else 1
    })

    save_performance(records)

    print("\n" + "=" * 65, flush=True)
    print("PIPELINE PERFORMANCE SUMMARY", flush=True)
    print("=" * 65, flush=True)

    for record in records:

        print(
            f"{record['stage']:<30} "
            f"{record['duration_seconds']:>10.2f} sec "
            f"{record['status']}",
            flush=True
        )

    print("-" * 65, flush=True)

    print(
        f"TOTAL EXECUTION TIME: {total_duration:.2f} seconds",
        flush=True
    )

    print(
        f"FINAL STATUS: {final_status}",
        flush=True
    )

    print(
        f"\nPerformance saved to: {PERFORMANCE_FILE}",
        flush=True
    )

    print("=" * 65, flush=True)

    return 0 if pipeline_success else 1


if __name__ == "__main__":
    sys.exit(main())
