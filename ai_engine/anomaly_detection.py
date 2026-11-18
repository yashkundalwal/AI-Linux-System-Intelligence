
import os
import joblib
import pandas as pd

from sklearn.impute import SimpleImputer
from sklearn.ensemble import IsolationForest

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INPUT_FILE = "data/processed/clean_system_telemetry.csv"
OUTPUT_FILE = "data/processed/system_anomaly_results.csv"
MODEL_FILE = "models/system_anomaly_detector.joblib"

FEATURES = [
    "cpu_usage",
    "memory_usage",
    "load_1",
    "running_processes",
    "cpu_temperature",
    "cpu_frequency_mhz",
    "network_rx_bytes_per_sec",
    "network_tx_bytes_per_sec"
]

CONTAMINATION = 0.05
RANDOM_STATE = 42


def main():
    print("=" * 55)
    print(" AI LINUX SYSTEM - ANOMALY DETECTION")
    print("=" * 55)

    # 1. Load processed telemetry
    print("\n[1] Loading processed system telemetry...")

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Dataset not found: {INPUT_FILE}\n"
            "Run data_preprocessing.py first."
        )

    df = pd.read_csv(INPUT_FILE)

    if len(df) < 20:
        raise ValueError(
            "At least 20 telemetry records are required "
            "for this initial experiment."
        )

    missing_columns = [
        col for col in FEATURES if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    print(f"Loaded {len(df)} telemetry records.")

    # 2. Prepare features
    print("\n[2] Preparing model features...")

    X = df[FEATURES].apply(
        pd.to_numeric, errors="coerce"
    )

    # Replace infinite values with missing values
    X = X.replace([float("inf"), float("-inf")], pd.NA)

    # Remove columns that contain no usable values
    usable_features = [
        col for col in X.columns if X[col].notna().any()
    ]

    X = X[usable_features]

    if X.empty:
        raise ValueError("No usable numerical features found.")

    # Fill missing values using each feature's median
    imputer = SimpleImputer(strategy="median")
    X_imputed = imputer.fit_transform(X)

    print(f"Features used: {usable_features}")
    print(f"Feature matrix shape: {X_imputed.shape}")

    # 3. Train Isolation Forest
    print("\n[3] Training Isolation Forest...")

    model = IsolationForest(
        n_estimators=200,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE
    )

    model.fit(X_imputed)

    print("Model training completed.")

    # 4. Detect anomalies
    print("\n[4] Detecting unusual system behavior...")

    predictions = model.predict(X_imputed)
    scores = model.decision_function(X_imputed)

    results = df.copy()

    # Isolation Forest: -1 = anomaly, 1 = normal
    results["anomaly"] = [
        "Anomaly" if prediction == -1 else "Normal"
        for prediction in predictions
    ]

    results["anomaly_score"] = scores

    # 5. Display results
    anomaly_count = int((predictions == -1).sum())
    normal_count = int((predictions == 1).sum())

    print("\n[5] DETECTION SUMMARY")
    print("-" * 40)
    print(f"Total records : {len(results)}")
    print(f"Normal records: {normal_count}")
    print(f"Anomalies     : {anomaly_count}")
    print(
        f"Anomaly rate  : "
        f"{(anomaly_count / len(results)) * 100:.2f}%"
    )

    anomalies = results[results["anomaly"] == "Anomaly"]

    if not anomalies.empty:
        print("\n[6] FLAGGED TELEMETRY RECORDS")

        display_columns = [
            "timestamp",
            "cpu_usage",
            "memory_usage",
            "load_1",
            "running_processes",
            "cpu_temperature",
            "anomaly_score"
        ]

        print(
            anomalies[display_columns].to_string(index=False)
        )
    else:
        print("\nNo anomalies were flagged.")

    # 6. Save detection results
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    results.to_csv(OUTPUT_FILE, index=False)

    print(f"\nResults saved: {OUTPUT_FILE}")

    # 7. Save trained model and preprocessing information
    os.makedirs(os.path.dirname(MODEL_FILE), exist_ok=True)

    joblib.dump(
        {
            "imputer": imputer,
            "model": model,
            "features": usable_features
        },
        MODEL_FILE
    )

    print(f"Model saved: {MODEL_FILE}")

    print("\nAnomaly detection completed successfully.")


if __name__ == "__main__":
    main()
