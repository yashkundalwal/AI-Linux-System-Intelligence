
import os
import sys
import time
import signal
import argparse
import subprocess
from datetime import datetime

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

COLLECTOR_BINARY = os.path.join(
    PROJECT_ROOT, "unified_telemetry_collector"
)

PIPELINE_COMMAND = [
    sys.executable,
    "-m",
    "ai_engine.run_live_pipeline"
]

collector_process = None
shutdown_requested = False


def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def handle_shutdown(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    log("Shutdown requested. Stopping live monitoring...")


def start_collector():
    global collector_process

    if not os.path.isfile(COLLECTOR_BINARY):
        raise FileNotFoundError(
            "Unified collector binary not found. Compile it first."
        )

    collector_process = subprocess.Popen(
        [COLLECTOR_BINARY],
        cwd=PROJECT_ROOT
    )

    time.sleep(2)

    if collector_process.poll() is not None:
        raise RuntimeError(
            "Unified telemetry collector exited unexpectedly."
        )

    log("Unified telemetry collector started.")


def run_ai_pipeline():
    log("Starting automated AI pipeline.")

    result = subprocess.run(
        PIPELINE_COMMAND,
        cwd=PROJECT_ROOT
    )

    if result.returncode == 0:
        log("AI pipeline completed successfully.")
    else:
        log(f"AI pipeline failed with exit code {result.returncode}.")

    return result.returncode


def stop_collector():
    global collector_process

    if collector_process is not None:
        if collector_process.poll() is None:
            log("Stopping unified telemetry collector.")
            collector_process.send_signal(signal.SIGINT)

            try:
                collector_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                log("Collector did not stop gracefully. Terminating.")
                collector_process.terminate()
                collector_process.wait(timeout=5)

        log("Collector stopped.")


def main():
    global shutdown_requested

    parser = argparse.ArgumentParser(
        description="AI Linux System live monitoring controller"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=120,
        help="Seconds between AI pipeline runs (default: 120)"
    )

    args = parser.parse_args()

    if args.interval < 30:
        parser.error("AI pipeline interval must be at least 30 seconds.")

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    log("AI Linux System live monitoring starting.")
    log(f"AI pipeline interval: {args.interval} seconds.")

    try:
        start_collector()

        # Allow new telemetry to accumulate before first AI run.
        log("Collecting initial telemetry for 10 seconds.")

        for _ in range(10):
            if shutdown_requested:
                break
            if collector_process.poll() is not None:
                raise RuntimeError("Telemetry collector stopped unexpectedly.")
            time.sleep(1)

        while not shutdown_requested:
            if collector_process.poll() is not None:
                raise RuntimeError("Telemetry collector stopped unexpectedly.")

            run_ai_pipeline()

            next_run = time.monotonic() + args.interval

            log(
                f"Next AI pipeline run in approximately "
                f"{args.interval} seconds."
            )

            while time.monotonic() < next_run:
                if shutdown_requested:
                    break

                if collector_process.poll() is not None:
                    raise RuntimeError(
                        "Telemetry collector stopped unexpectedly."
                    )

                time.sleep(1)

    except KeyboardInterrupt:
        shutdown_requested = True

    except Exception as error:
        log(f"MONITORING ERROR: {error}")

    finally:
        stop_collector()
        log("Live monitoring stopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
