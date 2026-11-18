
#include <iostream>
#include <string>
#include <vector>
#include <csignal>
#include <cerrno>
#include <cstring>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>

using namespace std;

volatile sig_atomic_t stopRequested = 0;

struct Collector {
    string name;
    string executable;
    pid_t pid = -1;
    bool running = false;
};

void handleSignal(int signalNumber) {
    stopRequested = signalNumber;
}

bool startCollector(Collector &collector) {
    pid_t child = fork();

    if (child < 0) {
        cerr << "Failed to start " << collector.name
             << ": " << strerror(errno) << endl;
        return false;
    }

    if (child == 0) {
        // Restore default signal handling in the child.
        signal(SIGINT, SIG_DFL);
        signal(SIGTERM, SIG_DFL);

        execl(
            collector.executable.c_str(),
            collector.executable.c_str(),
            static_cast<char *>(nullptr)
        );

        cerr << "Could not execute " << collector.executable
             << ": " << strerror(errno) << endl;

        _exit(127);
    }

    collector.pid = child;
    collector.running = true;

    cout << "[STARTED] " << collector.name
         << " | PID: " << collector.pid << endl;

    return true;
}

void stopCollectors(vector<Collector> &collectors) {
    cout << "\nStopping monitoring collectors..." << endl;

    // Request termination of every active collector.
    for (auto &collector : collectors) {
        if (collector.running) {
            if (kill(collector.pid, SIGTERM) == 0) {
                cout << "[STOP REQUESTED] "
                     << collector.name << endl;
            } else if (errno != ESRCH) {
                cerr << "Could not stop " << collector.name
                     << ": " << strerror(errno) << endl;
            }
        }
    }

    // Reap child processes.
    for (auto &collector : collectors) {
        if (collector.running) {
            int status;
            pid_t result;

            do {
                result = waitpid(collector.pid, &status, 0);
            } while (result < 0 && errno == EINTR);

            if (result == collector.pid) {
                cout << "[STOPPED] " << collector.name << endl;
            }

            collector.running = false;
        }
    }
}

int main() {
    cout << "==================================================\n";
    cout << "       AI LINUX SYSTEM - MONITORING SUPERVISOR\n";
    cout << "==================================================\n";

    struct sigaction action {};
    action.sa_handler = handleSignal;
    sigemptyset(&action.sa_mask);
    action.sa_flags = 0;

    if (sigaction(SIGINT, &action, nullptr) < 0 ||
        sigaction(SIGTERM, &action, nullptr) < 0) {
        cerr << "Failed to configure signal handlers." << endl;
        return 1;
    }

    vector<Collector> collectors = {
        {"System Telemetry Collector", "./system_agent"},
        {"Process Telemetry Collector", "./process_collector"}
    };

    cout << "\nStarting monitoring services...\n\n";

    for (auto &collector : collectors) {
        if (!startCollector(collector)) {
            stopCollectors(collectors);
            return 1;
        }
    }

    cout << "\n==================================================\n";
    cout << " CONTINUOUS MONITORING ACTIVE\n";
    cout << " System and process telemetry are being collected.\n";
    cout << " Press Ctrl+C to stop all collectors.\n";
    cout << "==================================================\n";

    bool unexpectedExit = false;

    while (!stopRequested) {
        for (auto &collector : collectors) {
            if (!collector.running) {
                continue;
            }

            int status;
            pid_t result = waitpid(
                collector.pid,
                &status,
                WNOHANG
            );

            if (result == collector.pid) {
                collector.running = false;

                cerr << "\n[ERROR] " << collector.name
                     << " exited unexpectedly." << endl;

                unexpectedExit = true;
                stopRequested = SIGTERM;
                break;
            }

            if (result < 0 && errno != EINTR) {
                cerr << "\n[ERROR] Could not monitor "
                     << collector.name << ": "
                     << strerror(errno) << endl;

                unexpectedExit = true;
                stopRequested = SIGTERM;
                break;
            }
        }

        if (!stopRequested) {
            sleep(1);
        }
    }

    cout << "\nShutdown signal received." << endl;

    stopCollectors(collectors);

    cout << "\n==================================================\n";

    if (unexpectedExit) {
        cout << " MONITORING STOPPED DUE TO COLLECTOR FAILURE\n";
    } else {
        cout << " MONITORING STOPPED SUCCESSFULLY\n";
    }

    cout << "==================================================\n";

    return unexpectedExit ? 1 : 0;
}
