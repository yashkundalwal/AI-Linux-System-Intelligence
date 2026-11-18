
import os
import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INPUT_FILE = "data/processed/clean_system_telemetry.csv"
OUTPUT_FILE = "data/processed/resource_prediction_results.csv"
MODEL_FILE = "models/resource_prediction_model.joblib"

LAGS = 3
TARGETS = ["cpu_usage", "memory_usage"]

BASE_FEATURES = [
    "cpu_usage",
    "memory_usage",
    "load_1",
    "load_5",
    "load_15",
    "running_processes",
    "disk_usage",
    "cpu_temperature",
    "cpu_frequency_mhz",
    "network_rx_bytes_per_sec",
    "network_tx_bytes_per_sec"
]


def create_lagged_dataset(df):

    data = df.copy()

    # Convert all model features to numeric
    for col in BASE_FEATURES:
        data[col] = pd.to_numeric(
            data[col], errors="coerce"
        )

    feature_columns = []

    # Create features from the previous 3 observations
    for lag in range(LAGS, 0, -1):
        for col in BASE_FEATURES:
            feature_name = f"{col}_lag_{lag}"
            data[feature_name] = data[col].shift(lag)
            feature_columns.append(feature_name)

    # Predict the next observation
    data["target_cpu"] = data["cpu_usage"].shift(-1)
    data["target_memory"] = data["memory_usage"].shift(-1)

    # Store the timestamp of the observation being predicted
    data["target_timestamp"] = data["timestamp"].shift(-1)

    dataset = data.dropna(
        subset=["target_cpu", "target_memory"]
    ).copy()

    dataset = dataset.dropna(
        subset=feature_columns, how="all"
    )

    return dataset, feature_columns


def main():

    print("=" * 60)
    print(" AI LINUX SYSTEM - RESOURCE USAGE PREDICTION")
    print("=" * 60)

    # 1. Load telemetry
    print("\n[1] Loading system telemetry...")

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Dataset not found: {INPUT_FILE}"
        )

    df = pd.read_csv(INPUT_FILE)

    df["timestamp"] = pd.to_datetime(
        df["timestamp"], errors="coerce"
    )

    df = (
        df.dropna(subset=["timestamp"])
        .sort_values("timestamp")
        .drop_duplicates(subset=["timestamp"], keep="last")
        .reset_index(drop=True)
    )

    print(f"Loaded {len(df)} records.")

    required = BASE_FEATURES + ["timestamp"]

    missing = [
        col for col in required if col not in df.columns
    ]

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # 2. Create time-series features
    print("\n[2] Creating lagged features...")

    dataset, feature_columns = create_lagged_dataset(df)

    if len(dataset) < 20:
        raise ValueError(
            f"Only {len(dataset)} usable training examples. "
            "Collect more telemetry before training."
        )

    X = dataset[feature_columns].replace(
        [np.inf, -np.inf], np.nan
    )

    y = dataset[["target_cpu", "target_memory"]]

    print(f"Training examples: {len(dataset)}")
    print(f"Lagged features: {len(feature_columns)}")

    # 3. Chronological train/test split
    print("\n[3] Splitting time-series data...")

    split_index = int(len(dataset) * 0.80)

    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]

    y_train = y.iloc[:split_index]
    y_test = y.iloc[split_index:]

    print(f"Training samples: {len(X_train)}")
    print(f"Testing samples : {len(X_test)}")

    # 4. Build model pipeline
    print("\n[4] Training Random Forest model...")

    model = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median")
        ),
        (
            "regressor",
            RandomForestRegressor(
                n_estimators=200,
                max_depth=6,
                min_samples_leaf=2,
                random_state=42
            )
        )
    ])

    model.fit(X_train, y_train)

    print("Training completed.")

    # 5. Evaluate predictions on held-out future records
    print("\n[5] Evaluating model...")

    predictions = model.predict(X_test)

    cpu_mae = mean_absolute_error(
        y_test["target_cpu"],
        predictions[:, 0]
    )

    memory_mae = mean_absolute_error(
        y_test["target_memory"],
        predictions[:, 1]
    )

    cpu_rmse = np.sqrt(
        mean_squared_error(
            y_test["target_cpu"],
            predictions[:, 0]
        )
    )

    memory_rmse = np.sqrt(
        mean_squared_error(
            y_test["target_memory"],
            predictions[:, 1]
        )
    )

    print("\nMODEL PERFORMANCE")
    print("-" * 40)
    print(f"CPU MAE     : {cpu_mae:.2f} percentage points")
    print(f"CPU RMSE    : {cpu_rmse:.2f}")
    print(f"Memory MAE  : {memory_mae:.2f} percentage points")
    print(f"Memory RMSE : {memory_rmse:.2f}")

    # 6. Save test predictions
    print("\n[6] Saving test predictions...")

    result_df = pd.DataFrame({
        "timestamp": dataset["target_timestamp"].iloc[split_index:].values,
        "actual_cpu": y_test["target_cpu"].values,
        "predicted_cpu": predictions[:, 0],
        "actual_memory": y_test["target_memory"].values,
        "predicted_memory": predictions[:, 1]
    })

    os.makedirs("data/processed", exist_ok=True)
    result_df.to_csv(OUTPUT_FILE, index=False)

    print(f"Predictions saved: {OUTPUT_FILE}")

    # 7. Predict the next observation
    print("\n[7] Predicting next system reading...")

    latest_features = (
        df[BASE_FEATURES]
        .tail(LAGS)
        .copy()
    )

    future_input = {}

    for lag in range(LAGS, 0, -1):
        row = latest_features.iloc[LAGS - lag]

        for col in BASE_FEATURES:
            future_input[f"{col}_lag_{lag}"] = row[col]

    future_X = pd.DataFrame(
        [future_input],
        columns=feature_columns
    ).replace([np.inf, -np.inf], np.nan)

    future_prediction = model.predict(future_X)[0]

    cpu_prediction = float(
        np.clip(future_prediction[0], 0, 100)
    )

    memory_prediction = float(
        np.clip(future_prediction[1], 0, 100)
    )

    print("\nNEXT OBSERVATION FORECAST")
    print("-" * 40)
    print(f"Predicted CPU usage    : {cpu_prediction:.2f}%")
    print(f"Predicted memory usage : {memory_prediction:.2f}%")

    # 8. Save model and metadata
    os.makedirs("models", exist_ok=True)

    joblib.dump(
        {
            "model": model,
            "features": feature_columns,
            "base_features": BASE_FEATURES,
            "lags": LAGS,
            "targets": TARGETS
        },
        MODEL_FILE
    )

    print(f"\nModel saved: {MODEL_FILE}")

    print("\nResource prediction completed successfully.")


if __name__ == "__main__":
    main()
