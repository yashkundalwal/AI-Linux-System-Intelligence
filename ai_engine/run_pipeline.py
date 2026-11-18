
import subprocess
import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PIPELINE = [
    ("Data preprocessing", "ai_engine/data_preprocessing.py"),
    ("System anomaly detection", "ai_engine/anomaly_detection.py"),
    ("Process anomaly detection", "ai_engine/process_anomaly_detection.py"),
    ("Resource prediction", "ai_engine/resource_prediction.py"),
    ("Diagnostic engine", "ai_engine/diagnostic_engine.py"),
    ("Recommendation engine", "ai_engine/recommendation_engine.py"),
    ("Action queue export", "ai_engine/export_action_queue.py")
]

def run_stage(name, script):
    print("\n" + "=" * 65)
    print(f"RUNNING: {name}")
    print("=" * 65)

    result = subprocess.run(
        [sys.executable, script],
        cwd=PROJECT_ROOT
    )

    if result.returncode != 0:
        print(f"\nERROR: {name} failed.")
        print("Pipeline stopped. Fix the error before continuing.")
        return False

    print(f"\nSUCCESS: {name}")
    return True

def main():
    print("=" * 65)
    print(" AI LINUX SYSTEM - AUTOMATED PIPELINE")
    print("=" * 65)

    for name, script in PIPELINE:
        if not run_stage(name, script):
            sys.exit(1)

    agent = os.path.join(PROJECT_ROOT, "system_action_agent")

    if not os.path.isfile(agent):
        print("\nC++ action agent not found.")
        print("Compile it using:")
        print("g++ -std=c++17 -Wall -Wextra -pedantic "
              "src/system_action_agent.cpp -o system_action_agent")
        sys.exit(1)

    print("\n" + "=" * 65)
    print(" ALL AI PIPELINE STAGES COMPLETED")
    print(" LAUNCHING C++ ACTION AGENT")
    print("=" * 65)

    result = subprocess.run([agent], cwd=PROJECT_ROOT)

    if result.returncode != 0:
        print("\nAction agent exited with an error.")
        sys.exit(result.returncode)

    print("\nAI Linux System pipeline completed.")

if __name__ == "__main__":
    main()
