
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <iomanip>
#include <filesystem>
#include <map>
#include <chrono>
#include <thread>
#include <unistd.h>
#include <cctype>

using namespace std;
namespace fs = std::filesystem;

struct ProcessData {
    int pid = 0;
    string name;
    char state = '?';

    unsigned long long userTime = 0;
    unsigned long long systemTime = 0;
    unsigned long long startTime = 0;

    double memoryMB = 0;
    int threads = 0;
};

bool isNumeric(const string& value) {
    if (value.empty()) return false;

    for (char c : value) {
        if (!isdigit(static_cast<unsigned char>(c))) {
            return false;
        }
    }

    return true;
}

bool readProcess(int pid, ProcessData& process) {
    fs::path processPath = "/proc/" + to_string(pid);

    ifstream statFile(processPath / "stat");

    if (!statFile.is_open()) return false;

    string statLine;
    getline(statFile, statLine);

    size_t openBracket = statLine.find('(');
    size_t closeBracket = statLine.rfind(')');

    if (openBracket == string::npos ||
        closeBracket == string::npos ||
        closeBracket <= openBracket) {
        return false;
    }

    process.pid = pid;
    process.name = statLine.substr(
        openBracket + 1,
        closeBracket - openBracket - 1
    );

    istringstream values(statLine.substr(closeBracket + 2));

    string state;
    if (!(values >> state)) return false;

    process.state = state.empty() ? '?' : state[0];

    // Fields after the process name begin at field 3.
    // utime = field 14, stime = field 15,
    // starttime = field 22.
    string token;

    for (int field = 4; field <= 22; field++) {
        if (!(values >> token)) return false;

        try {
            if (field == 14) {
                process.userTime = stoull(token);
            }
            else if (field == 15) {
                process.systemTime = stoull(token);
            }
            else if (field == 22) {
                process.startTime = stoull(token);
            }
        }
        catch (...) {
            return false;
        }
    }

    ifstream statusFile(processPath / "status");

    if (statusFile.is_open()) {
        string line;

        while (getline(statusFile, line)) {
            istringstream row(line);

            string key;
            row >> key;

            if (key == "VmRSS:") {
                double value;
                string unit;

                if (row >> value >> unit) {
                    process.memoryMB = value / 1024.0;
                }
            }
            else if (key == "Threads:") {
                row >> process.threads;
            }
        }
    }

    return true;
}

string getTimestamp() {
    time_t now = time(nullptr);
    tm* local = localtime(&now);

    if (!local) return "Unavailable";

    stringstream stream;
    stream << put_time(local, "%Y-%m-%d %H:%M:%S");

    return stream.str();
}

string makeKey(const ProcessData& process) {
    return to_string(process.pid) + ":" +
           to_string(process.startTime);
}

int main() {
    const string filename = "data/process_telemetry.csv";

    ofstream file(filename, ios::app);

    if (!file.is_open()) {
        cerr << "Unable to open process telemetry CSV.\n";
        return 1;
    }

    if (file.tellp() == 0) {
        file << "timestamp,pid,process_name,state,"
             << "cpu_percent,memory_mb,threads\n";
    }

    const long ticksPerSecond = sysconf(_SC_CLK_TCK);

    if (ticksPerSecond <= 0) {
        cerr << "Unable to determine system clock ticks.\n";
        return 1;
    }

    map<string, ProcessData> previousProcesses;

    auto previousSample = chrono::steady_clock::now();

    cout << "Per-Process Telemetry Collector Started\n";
    cout << "Output: " << filename << endl;
    cout << "Sampling interval: 2 seconds\n";
    cout << "Press Ctrl+C to stop.\n\n";

    while (true) {
        auto currentSample = chrono::steady_clock::now();

        double elapsed = chrono::duration<double>(
            currentSample - previousSample
        ).count();

        if (elapsed <= 0) elapsed = 2.0;

        previousSample = currentSample;

        map<string, ProcessData> currentProcesses;

        error_code ec;

        for (const auto& entry :
             fs::directory_iterator("/proc", ec)) {

            if (ec) break;

            string directoryName =
                entry.path().filename().string();

            if (!isNumeric(directoryName)) continue;

            int pid = 0;

            try {
                pid = stoi(directoryName);
            }
            catch (...) {
                continue;
            }

            ProcessData process;

            if (!readProcess(pid, process)) continue;

            currentProcesses[makeKey(process)] = process;
        }

        string timestamp = getTimestamp();

        int recorded = 0;

        for (const auto& item : currentProcesses) {
            const ProcessData& process = item.second;

            double cpuPercent = -1.0;

            auto previous = previousProcesses.find(item.first);

            if (previous != previousProcesses.end()) {
                unsigned long long currentTicks =
                    process.userTime + process.systemTime;

                unsigned long long previousTicks =
                    previous->second.userTime +
                    previous->second.systemTime;

                if (currentTicks >= previousTicks) {
                    cpuPercent =
                        (currentTicks - previousTicks) *
                        100.0 / (ticksPerSecond * elapsed);
                }
            }

            string safeName = process.name;

            for (char& c : safeName) {
                if (c == '"' || c == '\n' || c == '\r') {
                    c = '_';
                }
            }

            file << timestamp << ","
                 << process.pid << ","
                 << "\"" << safeName << "\","
                 << process.state << ","
                 << fixed << setprecision(2)
                 << cpuPercent << ","
                 << process.memoryMB << ","
                 << process.threads << "\n";

            recorded++;
        }

        file.flush();

        cout << "Processes recorded: " << recorded
             << " | Timestamp: " << timestamp << endl;

        previousProcesses = move(currentProcesses);

        this_thread::sleep_for(chrono::seconds(2));
    }

    return 0;
}
