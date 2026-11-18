
import os
import time
import csv
import io
import joblib
import pandas as pd

from collections import deque
from sklearn.impute import SimpleImputer
from sklearn.ensemble import IsolationForest

# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

INPUT_FILE = "data/processed/clean_process_telemetry.csv"
OUTPUT_FILE = "data/processed/process_anomaly_results.csv"
MODEL_FILE = "models/process_anomaly_detector.joblib"

FEATURES = [
    "cpu_percent",
    "memory_mb",
    "threads"
]

REQUIRED_COLUMNS = [
    "timestamp",
    "pid",
    "process_name",
    "state",
    "cpu_percent",
    "memory_mb",
    "threads"
]

MIN_OBSERVATIONS = 12
CONTAMINATION = 0.10
N_ESTIMATORS = 150
RANDOM_STATE = 42

TRAINING_WINDOW_MINUTES = 60
RETRAIN_INTERVAL_MINUTES = 15

# Version 3 forces a fresh training run.
# The new training process excludes the snapshot being scored.
MODEL_VERSION = 3

# Reverse-read block size for recent telemetry extraction.
READ_BLOCK_SIZE = 1024 * 1024


# --------------------------------------------------
# RECENT TELEMETRY LOADING
# --------------------------------------------------

def load_recent_telemetry():
    """
    Read only the latest 60-minute telemetry window.

    Assumption:
    The unified collector appends records in chronological order,
    and each telemetry record occupies one CSV line.
    """

    print("\n[1] Loading recent process telemetry...")

    if not os.path.exists(INPUT_FILE):
        raise FileNotFoundError(
            f"Dataset not found: {INPUT_FILE}\n"
            "Run data_preprocessing.py first."
        )

    required = set(REQUIRED_COLUMNS)

    with open(INPUT_FILE, "rb") as file:

        header = file.readline()

        if not header:
            raise ValueError("Process telemetry CSV is empty.")

        header_text = header.decode("utf-8").strip()

        actual_columns = next(
            csv.reader([header_text])
        )

        missing = required - set(actual_columns)

        if missing:
            raise ValueError(
                f"Missing columns: {sorted(missing)}"
            )

        file.seek(0, os.SEEK_END)
        file_size = file.tell()

        if file_size <= len(header):
            raise ValueError("No process telemetry records found.")

        # Read the final non-empty record.
        file.seek(max(len(header), file_size - READ_BLOCK_SIZE))
        tail = file.read().splitlines()

        last_line = next(
            (line for line in reversed(tail) if line.strip()),
            None
        )

        if last_line is None:
            raise ValueError("No valid telemetry records found.")

        latest_timestamp_text = (
            last_line.split(b",", 1)[0]
            .decode("utf-8")
            .strip()
            .strip('"')
        )

        latest_timestamp = pd.to_datetime(
            latest_timestamp_text,
            errors="coerce"
        )

        if pd.isna(latest_timestamp):
            raise ValueError(
                "Could not identify the latest telemetry timestamp."
            )

        training_start = (
            latest_timestamp
            - pd.Timedelta(minutes=TRAINING_WINDOW_MINUTES)
        )

        cutoff_text = training_start.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        # Read backward until records older than the cutoff.
        file.seek(0, os.SEEK_END)
        position = file.tell()
        remainder = b""
        recent_lines = []
        found_cutoff = False

        while position > len(header) and not found_cutoff:

            read_size = min(
                READ_BLOCK_SIZE,
                position - len(header)
            )

            position -= read_size
            file.seek(position)

            block = file.read(read_size) + remainder
            lines = block.split(b"\n")

            remainder = lines[0]

            complete_lines = lines[1:]

            for line in reversed(complete_lines):

                if not line.strip():
                    continue

                timestamp_text = (
                    line.split(b",", 1)[0]
                    .decode("utf-8")
                    .strip()
                    .strip('"')
                )

                # Fixed-format timestamps sort chronologically.
                if timestamp_text[:19] < cutoff_text:
                    found_cutoff = True
                    break

                recent_lines.append(line)

        # Include the remaining first line if it belongs to the window.
        if not found_cutoff and remainder.strip():

            timestamp_text = (
                remainder.split(b",", 1)[0]
                .decode("utf-8")
                .strip()
                .strip('"')
            )

            if timestamp_text[:19] >= cutoff_text:
                recent_lines.append(remainder)

        recent_lines.reverse()

        csv_content = (
            header + b"\n" + b"\n".join(recent_lines)
        ).decode("utf-8")

    df = pd.read_csv(io.StringIO(csv_content))

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["timestamp", "process_name"]
    )

    if df.empty:
        raise ValueError("No valid recent telemetry available.")

    print(f"Latest timestamp : {latest_timestamp}")
    print(f"Training cutoff  : {training_start}")
    print(f"Recent records   : {len(df)}")

    return df, latest_timestamp, training_start


# --------------------------------------------------
# FEATURE PREPARATION
# --------------------------------------------------

def prepare_features(df, columns):

    X = df[columns].apply(
        pd.to_numeric,
        errors="coerce"
    )

    X = X.replace(
        [float("inf"), float("-inf")],
        float("nan")
    )

    return X


# --------------------------------------------------
# MODEL REGISTRY
# --------------------------------------------------

def load_model_registry():

    if not os.path.exists(MODEL_FILE):
        return None

    try:

        saved = joblib.load(MODEL_FILE)

        if saved.get("version") != MODEL_VERSION:
            print("Model version mismatch. Retraining required.")
            return None

        if "models" not in saved or "trained_at" not in saved:
            return None

        age_minutes = (
            time.time() - saved["trained_at"]
        ) / 60

        if age_minutes >= RETRAIN_INTERVAL_MINUTES:

            print(
                f"Models are {age_minutes:.1f} minutes old. "
                "Retraining required."
            )

            return None

        print(
            f"Reusing saved models "
            f"({age_minutes:.1f} minutes old)."
        )

        return saved

    except Exception as error:

        print(f"Could not load model registry: {error}")
        return None


# --------------------------------------------------
# MODEL TRAINING
# --------------------------------------------------

def train_models(training_df):

    model_registry = {}

    trained = 0
    skipped = 0

    for process_name, group in training_df.groupby(
        "process_name",
        sort=False,
        dropna=True
    ):

        feature_data = prepare_features(
            group,
            FEATURES
        )

        usable_features = [
            col for col in FEATURES
            if feature_data[col].notna().any()
        ]

        if (
            len(group) < MIN_OBSERVATIONS
            or not usable_features
        ):
            skipped += 1
            continue

        X = feature_data[usable_features]

        imputer = SimpleImputer(strategy="median")
        X_imputed = imputer.fit_transform(X)

        model = IsolationForest(
            n_estimators=N_ESTIMATORS,
            contamination=CONTAMINATION,
            random_state=RANDOM_STATE,
            n_jobs=-1
        )

        model.fit(X_imputed)

        model_registry[str(process_name)] = {
            "model": model,
            "imputer": imputer,
            "features": usable_features
        }

        trained += 1

    print(f"Models trained   : {trained}")
    print(f"Processes skipped: {skipped}")

    return model_registry


# --------------------------------------------------
# LATEST SNAPSHOT SCORING
# --------------------------------------------------

def score_latest_snapshot(latest_df, model_registry):

    results = latest_df.copy()

    results["anomaly"] = "Insufficient data"
    results["anomaly_score"] = float("nan")

    for process_name, group in results.groupby(
        "process_name",
        sort=False,
        dropna=True
    ):

        registry = model_registry.get(
            str(process_name)
        )

        if registry is None:
            continue

        features = registry["features"]

        X = prepare_features(group, features)

        X_imputed = registry["imputer"].transform(X)

        predictions = registry["model"].predict(
            X_imputed
        )

        scores = registry["model"].decision_function(
            X_imputed
        )

        results.loc[group.index, "anomaly"] = [
            "Anomaly" if prediction == -1 else "Normal"
            for prediction in predictions
        ]

        results.loc[group.index, "anomaly_score"] = scores

    return results


# --------------------------------------------------
# MAIN PIPELINE
# --------------------------------------------------

def main():

    pipeline_start = time.perf_counter()

    print("=" * 60)
    print(" AI LINUX SYSTEM - INCREMENTAL PROCESS ANOMALY DETECTION")
    print("=" * 60)

    # 1. Load recent telemetry.

    start = time.perf_counter()

    recent_df, latest_timestamp, training_start = (
        load_recent_telemetry()
    )

    print(
        f"Loading time: {time.perf_counter() - start:.2f} seconds"
    )

    # 2. Separate training window and latest snapshot.

    print("\n[2] Preparing training and scoring datasets...")

    latest_df = recent_df[
        recent_df["timestamp"] == latest_timestamp
    ].copy()

    # Strictly exclude the latest timestamp from training.
    training_df = recent_df[
        (recent_df["timestamp"] >= training_start)
        & (recent_df["timestamp"] < latest_timestamp)
    ].copy()

    print(f"Training window start: {training_start}")
    print(f"Training window end  : {latest_timestamp}")
    print(f"Training records     : {len(training_df)}")
    print(f"Latest snapshot      : {len(latest_df)}")

    if training_df.empty:
        raise ValueError(
            "Insufficient historical records for model training."
        )

    if latest_df.empty:
        raise ValueError("Latest process snapshot is empty.")

    # 3. Load or train models.

    print("\n[3] Preparing process-specific models...")

    model_start = time.perf_counter()

    saved_registry = load_model_registry()

    if saved_registry is not None:

        model_registry = saved_registry["models"]

        print(
            f"Existing models loaded: {len(model_registry)}"
        )

    else:

        print("Training models using recent historical data...")

        model_registry = train_models(training_df)

        os.makedirs("models", exist_ok=True)

        joblib.dump(
            {
                "version": MODEL_VERSION,
                "models": model_registry,
                "features": FEATURES,
                "trained_at": time.time(),
                "training_window_minutes": TRAINING_WINDOW_MINUTES,
                "minimum_observations": MIN_OBSERVATIONS,
                "excludes_scored_snapshot": True
            },
            MODEL_FILE
        )

        print(f"Models saved: {MODEL_FILE}")

    print(
        f"Model preparation time: "
        f"{time.perf_counter() - model_start:.2f} seconds"
    )

    # 4. Score latest snapshot.

    print("\n[4] Detecting latest process anomalies...")

    scoring_start = time.perf_counter()

    results = score_latest_snapshot(
        latest_df,
        model_registry
    )

    print(
        f"Scoring time: "
        f"{time.perf_counter() - scoring_start:.2f} seconds"
    )

    # 5. Calculate results.

    modeled_rows = results[
        results["anomaly"].isin(["Normal", "Anomaly"])
    ]

    anomaly_rows = modeled_rows[
        modeled_rows["anomaly"] == "Anomaly"
    ]

    normal_count = int(
        (modeled_rows["anomaly"] == "Normal").sum()
    )

    anomaly_count = len(anomaly_rows)

    # 6. Display summary.

    print("\n[5] PROCESS DETECTION SUMMARY")
    print("-" * 45)

    print(f"Recent records     : {len(recent_df)}")
    print(f"Training records   : {len(training_df)}")
    print(f"Latest snapshot    : {len(latest_df)}")
    print(f"Modeled processes  : {len(modeled_rows)}")
    print(f"Normal processes   : {normal_count}")
    print(f"Anomalous processes: {anomaly_count}")
    print(f"Unmodeled processes: {len(results) - len(modeled_rows)}")

    print("\n[6] FLAGGED PROCESS OBSERVATIONS")

    if not anomaly_rows.empty:

        display_columns = [
            "timestamp",
            "pid",
            "process_name",
            "cpu_percent",
            "memory_mb",
            "threads",
            "anomaly_score"
        ]

        print(
            anomaly_rows
            .sort_values("anomaly_score")
            [display_columns]
            .head(20)
            .to_string(index=False)
        )

    else:
        print("No process anomalies detected.")

    # 7. Save output using the existing schema.

    os.makedirs("data/processed", exist_ok=True)

    results.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print(f"\nResults saved: {OUTPUT_FILE}")

    print(
        f"\nTotal execution time: "
        f"{time.perf_counter() - pipeline_start:.2f} seconds"
    )

    print("\nProcess anomaly detection completed successfully.")


if __name__ == "__main__":
    main()
