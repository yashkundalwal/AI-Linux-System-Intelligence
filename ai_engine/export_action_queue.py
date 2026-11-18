
import os
import re
import csv
import pandas as pd

INPUT_FILE = "data/processed/recommendations.csv"
OUTPUT_FILE = "data/processed/action_queue.tsv"

def clean(value):
    if pd.isna(value):
        return ""
    return str(value).replace("\t", " ").replace("\n", " ").strip()

def main():
    print("=" * 60)
    print(" AI LINUX SYSTEM - ACTION QUEUE EXPORTER")
    print("=" * 60)

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            "Recommendations not found. Run recommendation_engine.py first."
        )

    df = pd.read_csv(INPUT_FILE)

    required = [
        "priority", "category", "target",
        "observation", "recommendation"
    ]

    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    action_queue = []

    for _, row in df.iterrows():
        # This first integration supports process investigations only.
        if clean(row["category"]) != "Process investigation":
            continue

        target = clean(row["target"])
        match = re.match(r"^(.*?) \(PID (\d+)\)$", target)

        if not match:
            print(f"Skipping unrecognized target: {target}")
            continue

        process_name = match.group(1)
        pid = int(match.group(2))

        if pid <= 0:
            continue

        observation = clean(row["observation"])
        recommendation = clean(row["recommendation"])

        cpu_match = re.search(
            r"CPU usage: ([0-9.]+)%", observation
        )
        memory_match = re.search(
            r"Memory usage: ([0-9.]+) MB", observation
        )

        cpu = cpu_match.group(1) if cpu_match else ""
        memory = memory_match.group(1) if memory_match else ""

        action_queue.append({
            "priority": clean(row["priority"]),
            "pid": pid,
            "process_name": process_name,
            "cpu_percent": cpu,
            "memory_mb": memory,
            "recommendation": recommendation
        })

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    columns = [
        "priority", "pid", "process_name",
        "cpu_percent", "memory_mb", "recommendation"
    ]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            delimiter="\t"
        )
        writer.writeheader()
        writer.writerows(action_queue)

    print(f"\nRecommendations exported: {len(action_queue)}")
    print(f"Output: {OUTPUT_FILE}")

    for item in action_queue:
        print(
            f"[{item['priority']}] "
            f"{item['process_name']} PID={item['pid']}"
        )

    print("\nAction queue generated successfully.")

if __name__ == "__main__":
    main()
