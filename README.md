# AI-Driven Linux System Health and Intelligence Platform

An intelligent Linux system monitoring and analysis platform that combines **C++ system-level programming** with **Python-based Artificial Intelligence and Machine Learning** to monitor system resources, detect abnormal behaviour, predict resource utilization, generate diagnostic insights, and recommend safe investigation actions.

## 1. Project Overview

The AI-Driven Linux System Health and Intelligence Platform is designed to provide an intelligent view of Linux system health by integrating low-level operating system monitoring with machine learning and automated diagnostics.

The platform uses a C++ telemetry collector to obtain system and process-level information from Linux interfaces such as `/proc`, `/sys`, and filesystem statistics. The collected telemetry is stored in CSV files and processed by a Python-based AI/ML pipeline.

Machine learning models analyse resource usage patterns, identify statistical anomalies, and forecast CPU and memory utilization. A diagnostic engine interprets the detected conditions, while a recommendation engine generates actionable suggestions.

A C++ action agent presents selected recommendations to the user and, after explicit approval, performs a read-only process inspection.

The platform also provides a Streamlit dashboard for visualizing system health, process information, anomalies, predictions, diagnostics, and recommendations.

## 2. Objectives

- Monitor Linux system resources and process-level activity.
- Collect system telemetry using C++ and Linux system interfaces.
- Store and process telemetry for downstream analysis.
- Detect unusual system and process behaviour using machine learning.
- Predict future CPU and memory utilization.
- Generate diagnostic explanations from detected conditions.
- Recommend appropriate system investigation steps.
- Provide user-approved interaction through a C++ action agent.
- Visualize system information through an interactive dashboard.
- Integrate monitoring and AI analysis into a continuous workflow.

## 3. Technology Stack

| Component | Technologies |
|---|---|
| Systems programming | C++17 |
| Operating system | Linux |
| AI/ML | Python, Scikit-learn |
| Data processing | Pandas, NumPy |
| Model persistence | Joblib |
| Dashboard | Streamlit |
| System interfaces | `/proc`, `/sys`, `statvfs` |
| Process inspection | `fork`, `execvp`, `ps` |
| Data storage | CSV and TSV |
| Development tools | GCC/G++, Git |

## 4. System Architecture

The platform follows a modular architecture:

1. **Linux operating system:** Provides process, CPU, memory, disk, network, and hardware information.
2. **C++ telemetry collector:** Collects system and process-level information.
3. **Telemetry storage:** Stores collected information in CSV files.
4. **Python preprocessing:** Cleans, transforms, and validates telemetry.
5. **AI/ML analysis:** Performs anomaly detection and resource prediction.
6. **Diagnostic engine:** Interprets the analysis results.
7. **Recommendation engine:** Generates investigation recommendations.
8. **Action queue:** Exports recommendations for the C++ action agent.
9. **C++ action agent:** Presents recommendations and performs approved read-only inspection.
10. **Streamlit dashboard:** Displays monitoring and analysis results.

## 5. C++ System Monitoring

The monitoring layer is implemented in C++17 and uses Linux system interfaces to collect telemetry.

### Unified telemetry collector

The integrated collector produces two primary datasets:

- `data/system_telemetry_v2.csv`
- `data/process_telemetry.csv`

The system telemetry includes system-level measurements, while process telemetry records information about individual processes.

The integrated collector uses shared timestamps to improve synchronization between system and process observations.

### Linux interfaces

| Interface | Purpose |
|---|---|
| `/proc/stat` | CPU statistics |
| `/proc/meminfo` | Memory and swap information |
| `/proc/[PID]/stat` | Process information |
| `/proc/net/dev` | Network interface statistics |
| `/proc/diskstats` | Disk activity |
| `/proc/uptime` | System uptime |
| `/sys` | Hardware and sensor information |
| `statvfs` | Filesystem capacity information |

### Process monitoring

Process telemetry supports analysis of:

- Process ID (PID)
- Process name
- Process state
- CPU utilization
- Memory utilization
- Thread count

## 6. Python AI/ML Engine

The AI engine is divided into independent modules.

### Data preprocessing

`ai_engine/data_preprocessing.py`

- Loads collected telemetry.
- Cleans and transforms datasets.
- Handles timestamps and missing values.
- Normalizes sensor and resource information.
- Derives network throughput.
- Validates telemetry synchronization.

### System anomaly detection

`ai_engine/anomaly_detection.py`

Uses an Isolation Forest model to identify unusual system-level resource usage patterns.

### Process anomaly detection

`ai_engine/process_anomaly_detection.py`

Performs process-specific anomaly detection using Isolation Forest models. The implementation maintains model state and uses recent telemetry windows to reduce unnecessary processing.

### Resource prediction

`ai_engine/resource_prediction.py`

Uses Random Forest regression to estimate future CPU and memory utilization using historical resource measurements and lag-based features.

### Diagnostic engine

`ai_engine/diagnostic_engine.py`

Interprets monitoring and model outputs to generate diagnostic findings.

### Recommendation engine

`ai_engine/recommendation_engine.py`

Generates advisory recommendations based on the diagnostic findings and process-level observations.

### Action queue export

`ai_engine/export_action_queue.py`

Exports selected recommendations into:

`data/processed/action_queue.tsv`

The TSV file is used as input by the C++ action agent.

## 7. C++ System Action Agent

Source file: `src/system_action_agent.cpp`

The action agent connects Python-generated recommendations with Linux process inspection.

Its workflow includes:

1. Loads recommendations from the action queue.
2. Displays recommendation priority and process information.
3. Reads the current process information from `/proc`.
4. Checks the process name against the recommendation.
5. Records the process start time to help identify PID reuse.
6. Requests explicit user confirmation.
7. Revalidates process identity before execution.
8. Executes a read-only `ps` inspection.

**Safety design:** The current implementation performs read-only process inspection. It does not terminate processes, modify system configuration, or automatically execute destructive actions.

## 8. Continuous Monitoring

The live monitoring controller is:

`ai_engine/live_monitor.py`

It coordinates the unified C++ collector and automated AI pipeline.

The controller:

- Starts the telemetry collector.
- Allows an initial telemetry collection period.
- Executes the AI pipeline.
- Waits for the configured interval.
- Repeats the analysis.
- Handles shutdown signals and stops the collector.

The default interval between AI pipeline runs is 120 seconds. The minimum accepted interval is 30 seconds.

The seven AI pipeline stages are:

1. Data preprocessing
2. System anomaly detection
3. Process anomaly detection
4. Resource prediction
5. Diagnostic engine
6. Recommendation engine
7. Action queue export

Execution timings and stage statuses are recorded in:

`data/processed/pipeline_performance.csv`

## 9. Streamlit Dashboard

Dashboard source:

`dashboard/Dashboard.py`

The dashboard provides six main sections:

1. **System Overview** – displays overall system health and resource information.
2. **Process Explorer** – provides process-level information.
3. **Anomaly Detection** – displays detected system and process anomalies.
4. **Resource Prediction** – presents CPU and memory forecasts.
5. **Diagnostic Center** – displays diagnostic findings.
6. **Recommendation Center** – presents AI-generated recommendations.

The dashboard is intended to provide a convenient interface for understanding the output of the monitoring and analysis pipeline.

## 10. Project Directory Structure

```text
AI_Linux_System/
│
├── ai_engine/
│   ├── anomaly_detection.py
│   ├── data_preprocessing.py
│   ├── diagnostic_engine.py
│   ├── export_action_queue.py
│   ├── live_monitor.py
│   ├── process_anomaly_detection.py
│   ├── recommendation_engine.py
│   ├── resource_prediction.py
│   ├── run_live_pipeline.py
│   └── run_pipeline.py
│
├── dashboard/
│   └── Dashboard.py
│
├── data/
│   ├── processed/
│   ├── process_telemetry.csv
│   ├── system_telemetry.csv
│   └── system_telemetry_v2.csv
│
├── models/
│   ├── process_anomaly_detector.joblib
│   ├── resource_prediction_model.joblib
│   └── system_anomaly_detector.joblib
│
├── src/
│   ├── main.cpp
│   ├── monitoring_supervisor.cpp
│   ├── process_collector.cpp
│   ├── system_action_agent.cpp
│   ├── system_action_agent_v1.cpp
│   └── unified_telemetry_collector.cpp
│
├── .gitignore
└── requirements.txt
```

Generated datasets, processed outputs, trained model files, logs, and compiled binaries are runtime artifacts and are excluded from version control through `.gitignore`.

## 11. Installation and Setup

### Prerequisites

- A Linux distribution
- Python 3
- GCC/G++ with C++17 support
- pip
- Required Python packages

### Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd AI_Linux_System
```

### Install Python dependencies

```bash
python3 -m pip install -r requirements.txt
```

### Compile the unified telemetry collector

```bash
g++ -std=c++17 -Wall -Wextra -pedantic \
src/unified_telemetry_collector.cpp \
-o unified_telemetry_collector
```

### Compile the C++ action agent

```bash
g++ -std=c++17 -Wall -Wextra -pedantic \
src/system_action_agent.cpp \
-o system_action_agent
```

## 12. Running the Platform

Open a terminal in the project root.

### Start continuous monitoring

```bash
python3 -m ai_engine.live_monitor --interval 120
```

The controller starts the unified collector and repeatedly executes the AI pipeline.

Press `Ctrl+C` to stop continuous monitoring gracefully.

### Start the dashboard

Open another terminal:

```bash
cd AI_Linux_System
streamlit run dashboard/Dashboard.py --server.port 8503
```

Open:

```text
http://localhost:8503
```

The dashboard reads the generated monitoring and analysis outputs.

### Run the AI pipeline independently

```bash
python3 ai_engine/run_live_pipeline.py
```

This executes the seven pipeline stages and records performance information. The action queue is generated for subsequent inspection by the C++ action agent.

### Run the action agent

After the recommendation queue has been generated:

```bash
./system_action_agent
```

Review the recommendations and confirm an inspection only when appropriate.

## 13. Experimental Results and Performance

The implementation has been tested with live Linux telemetry and repeated AI pipeline executions.

Observed results include:

- System and process telemetry timestamps were aligned across 170 verified samples.
- The system anomaly detector identified statistical deviations in resource measurements.
- The process anomaly detector generated process-specific anomaly flags.
- The resource prediction models generated CPU and memory forecasts.
- The diagnostic and recommendation stages completed successfully in observed pipeline runs.
- The action agent successfully verified a live process and performed a user-approved read-only inspection.

One observed pipeline execution completed all seven stages in approximately 29 seconds. Other runs took longer depending on the amount of telemetry and model workload. Execution time is therefore workload-dependent and is not a fixed performance guarantee.

### Preliminary prediction metrics

An earlier chronological evaluation produced:

| Metric | CPU prediction | Memory prediction |
|---|---:|---:|
| MAE | 9.38 percentage points | 2.14 percentage points |
| RMSE | 13.15 | 2.71 |

These are preliminary evaluation results. More diverse workloads and additional test data are required before making broader accuracy claims.

## 14. Limitations and Future Scope

### Current limitations

- Anomaly detection identifies statistical deviations, not confirmed system faults or malware.
- Prediction quality depends on the available historical telemetry and workload diversity.
- Diagnostic rules use heuristic thresholds.
- Hardware sensor availability and naming vary across Linux systems.
- The action agent currently supports read-only process inspection rather than automatic resource management.
- The platform is designed around Linux-specific interfaces and is not directly portable to Windows.

### Future enhancements

- Add more advanced time-series forecasting models.
- Introduce adaptive anomaly thresholds.
- Improve hardware-specific sensor identification.
- Add long-term telemetry storage and historical trend analysis.
- Introduce notification and alerting mechanisms.
- Add configurable user-approved remediation actions.
- Improve model evaluation using diverse workloads.
- Add automated test coverage and continuous integration.
- Expand dashboard filtering and visualization.

## 15. Conclusion

The AI-Driven Linux System Health and Intelligence Platform demonstrates the integration of systems programming and artificial intelligence for intelligent operating system monitoring.

By combining a C++ telemetry collection layer with Python-based machine learning, diagnostic analysis, and a Streamlit dashboard, the project provides a modular approach to understanding Linux system behaviour.

The approval-gated C++ action agent further demonstrates how AI-generated recommendations can be connected to operating system inspection while retaining user control.

The project establishes a foundation for future work in intelligent system monitoring, predictive resource analysis, and safe AI-assisted system administration.

---

**Project category:** Final Year Engineering Project
**Domain:** Artificial Intelligence, Machine Learning, Linux System Programming
**Primary languages:** C++ and Python
**Platform:** Linux
**Dashboard:** Streamlit