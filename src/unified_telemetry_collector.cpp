#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <iomanip>
#include <thread>
#include <chrono>
#include <ctime>
#include <filesystem>
#include <cctype>
#include <map>
#include <utility>
#include <unistd.h>
#include <sys/statvfs.h>

using namespace std;
namespace fs = std::filesystem;
using SteadyClock = chrono::steady_clock;

struct SystemTelemetry {
    double cpu = -1;
    double memory = -1;
    double load1 = -1;
    double load5 = -1;
    double load15 = -1;
    int totalProcesses = 0;
    int runningProcesses = 0;
    double diskUsage = -1;
    unsigned long long networkRX = 0;
    unsigned long long networkTX = 0;
    double cpuTemperature = -1;
    double cpuFrequency = -1;
    int battery = -1;
};

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
        if (!isdigit(static_cast<unsigned char>(c))) return false;
    }
    return true;
}

string getTimestamp() {
    time_t now = time(nullptr);
    tm local{};
    if (localtime_r(&now, &local) == nullptr) return "Unavailable";
    stringstream stream;
    stream << put_time(&local, "%Y-%m-%d %H:%M:%S");
    return stream.str();
}

double getCPUUsage() {
    static unsigned long long previousIdle = 0;
    static unsigned long long previousTotal = 0;
    static bool initialized = false;

    ifstream file("/proc/stat");
    string cpu;
    unsigned long long user = 0, nice = 0, system = 0, idle = 0;
    unsigned long long iowait = 0, irq = 0, softirq = 0, steal = 0;
    if (!(file >> cpu >> user >> nice >> system >> idle >> iowait >> irq >> softirq >> steal)) return -1;

    unsigned long long idleAll = idle + iowait;
    unsigned long long total = user + nice + system + idle + iowait + irq + softirq + steal;
    if (!initialized) {
        previousIdle = idleAll;
        previousTotal = total;
        initialized = true;
        return -1;
    }

    unsigned long long totalDiff = total - previousTotal;
    unsigned long long idleDiff = idleAll - previousIdle;
    previousIdle = idleAll;
    previousTotal = total;
    if (totalDiff == 0) return -1;
    return 100.0 * (totalDiff - idleDiff) / totalDiff;
}

double getMemoryUsage() {
    ifstream file("/proc/meminfo");
    string key, unit;
    unsigned long long total = 0, available = 0, value = 0;
    while (file >> key >> value >> unit) {
        if (key == "MemTotal:") total = value;
        if (key == "MemAvailable:") available = value;
    }
    if (total == 0) return -1;
    return 100.0 * (total - available) / total;
}

void getLoadAverage(SystemTelemetry& t) {
    ifstream file("/proc/loadavg");
    if (file) file >> t.load1 >> t.load5 >> t.load15;
}

void getProcessCounts(SystemTelemetry& t) {
    error_code ec;
    for (const auto& entry : fs::directory_iterator("/proc", ec)) {
        if (ec) break;
        string name = entry.path().filename().string();
        if (!isNumeric(name)) continue;
        ifstream status(entry.path() / "status");
        string line;
        while (getline(status, line)) {
            if (line.rfind("State:", 0) == 0) {
                ++t.totalProcesses;
                istringstream stateLine(line.substr(6));
                char state = '?';
                stateLine >> state;
                if (state == 'R') ++t.runningProcesses;
                break;
            }
        }
    }
}

double getDiskUsage() {
    struct statvfs info{};
    if (statvfs("/", &info) != 0) return -1;
    unsigned long long total = static_cast<unsigned long long>(info.f_blocks) * info.f_frsize;
    unsigned long long available = static_cast<unsigned long long>(info.f_bavail) * info.f_frsize;
    if (total == 0) return -1;
    return 100.0 * (total - available) / total;
}

void getNetworkTraffic(SystemTelemetry& t) {
    ifstream file("/proc/net/dev");
    if (!file) return;
    string line;
    getline(file, line);
    getline(file, line);
    while (getline(file, line)) {
        size_t colon = line.find(':');
        if (colon == string::npos) continue;
        string interfaceName = line.substr(0, colon);
        size_t first = interfaceName.find_first_not_of(" \t");
        if (first == string::npos) continue;
        interfaceName.erase(0, first);
        bool physical = interfaceName.rfind("en", 0) == 0 ||
                        interfaceName.rfind("eth", 0) == 0 ||
                        interfaceName.rfind("wl", 0) == 0;
        if (!physical) continue;
        istringstream values(line.substr(colon + 1));
        unsigned long long rx = 0, tx = 0, ignored = 0;
        if (!(values >> rx)) continue;
        for (int i = 0; i < 7; ++i) if (!(values >> ignored)) break;
        if (!(values >> tx)) continue;
        t.networkRX += rx;
        t.networkTX += tx;
    }
}

double getCPUTemperature() {
    error_code ec;
    fs::path hwmon("/sys/class/hwmon");
    if (!fs::exists(hwmon, ec)) return -1;
    for (const auto& device : fs::directory_iterator(hwmon, ec)) {
        if (ec) break;
        for (const auto& sensor : fs::directory_iterator(device.path(), ec)) {
            if (ec) break;
            string name = sensor.path().filename().string();
            if (name.rfind("temp", 0) != 0 || name.find("_input") == string::npos) continue;
            ifstream file(sensor.path());
            long long value = 0;
            if (file >> value) return value / 1000.0;
        }
    }
    return -1;
}

double getCPUFrequency() {
    error_code ec;
    fs::path cpuPath("/sys/devices/system/cpu");
    if (!fs::exists(cpuPath, ec)) return -1;
    double total = 0;
    int count = 0;
    for (const auto& cpu : fs::directory_iterator(cpuPath, ec)) {
        if (ec) break;
        string name = cpu.path().filename().string();
        if (name.rfind("cpu", 0) != 0 || name.size() <= 3 || !isNumeric(name.substr(3))) continue;
        long long frequency = 0;
        ifstream file(cpu.path() / "cpufreq/scaling_cur_freq");
        if (file >> frequency) {
            total += frequency / 1000.0;
            ++count;
        }
    }
    return count == 0 ? -1 : total / count;
}

int getBatteryPercentage() {
    error_code ec;
    fs::path powerPath("/sys/class/power_supply");
    if (!fs::exists(powerPath, ec)) return -1;
    for (const auto& device : fs::directory_iterator(powerPath, ec)) {
        if (ec) break;
        ifstream typeFile(device.path() / "type");
        string type;
        if (!(typeFile >> type) || type != "Battery") continue;
        ifstream capacityFile(device.path() / "capacity");
        int capacity = -1;
        if (capacityFile >> capacity) return capacity;
    }
    return -1;
}

SystemTelemetry collectSystemTelemetry() {
    SystemTelemetry t;
    t.cpu = getCPUUsage();
    t.memory = getMemoryUsage();
    getLoadAverage(t);
    getProcessCounts(t);
    t.diskUsage = getDiskUsage();
    getNetworkTraffic(t);
    t.cpuTemperature = getCPUTemperature();
    t.cpuFrequency = getCPUFrequency();
    t.battery = getBatteryPercentage();
    return t;
}

bool readProcess(int pid, ProcessData& process) {
    fs::path processPath = "/proc/" + to_string(pid);
    ifstream statFile(processPath / "stat");
    if (!statFile) return false;
    string statLine;
    getline(statFile, statLine);
    size_t openBracket = statLine.find('(');
    size_t closeBracket = statLine.rfind(')');
    if (openBracket == string::npos || closeBracket == string::npos || closeBracket <= openBracket) return false;

    process.pid = pid;
    process.name = statLine.substr(openBracket + 1, closeBracket - openBracket - 1);
    istringstream values(statLine.substr(closeBracket + 2));
    string state;
    if (!(values >> state)) return false;
    process.state = state.empty() ? '?' : state[0];

    // Remaining tokens start at field 3; utime=14, stime=15, starttime=22.
    string token;
    for (int field = 4; field <= 22; ++field) {
        if (!(values >> token)) return false;
        try {
            if (field == 14) process.userTime = stoull(token);
            else if (field == 15) process.systemTime = stoull(token);
            else if (field == 22) process.startTime = stoull(token);
        } catch (...) {
            return false;
        }
    }

    ifstream statusFile(processPath / "status");
    if (statusFile) {
        string line;
        while (getline(statusFile, line)) {
            istringstream row(line);
            string key;
            row >> key;
            if (key == "VmRSS:") {
                double value = 0;
                string unit;
                if (row >> value >> unit) process.memoryMB = value / 1024.0;
            } else if (key == "Threads:") {
                row >> process.threads;
            }
        }
    }
    return true;
}

string makeProcessKey(const ProcessData& process) {
    return to_string(process.pid) + ":" + to_string(process.startTime);
}

map<string, ProcessData> collectProcesses() {
    map<string, ProcessData> processes;
    error_code ec;
    for (const auto& entry : fs::directory_iterator("/proc", ec)) {
        if (ec) break;
        string directoryName = entry.path().filename().string();
        if (!isNumeric(directoryName)) continue;
        int pid = 0;
        try {
            pid = stoi(directoryName);
        } catch (...) {
            continue;
        }
        ProcessData process;
        if (readProcess(pid, process)) processes[makeProcessKey(process)] = move(process);
    }
    return processes;
}

bool initializeCSV(ofstream& systemFile, ofstream& processFile) {
    systemFile.open("data/system_telemetry_v2.csv", ios::app);
    processFile.open("data/process_telemetry.csv", ios::app);
    if (!systemFile || !processFile) {
        cerr << "Unable to open telemetry CSV files. Ensure data/ exists.\n";
        return false;
    }
    if (systemFile.tellp() == 0) {
        systemFile << "timestamp,cpu_usage,memory_usage,load_1,load_5,load_15,"
                      "total_processes,running_processes,disk_usage,network_rx_bytes,"
                      "network_tx_bytes,cpu_temperature,cpu_frequency_mhz,battery_percent\n";
    }
    if (processFile.tellp() == 0) {
        processFile << "timestamp,pid,process_name,state,cpu_percent,memory_mb,threads\n";
    }
    return true;
}

int main() {
    const chrono::seconds sampleInterval(2);
    ofstream systemFile, processFile;
    if (!initializeCSV(systemFile, processFile)) return 1;

    const long ticksPerSecond = sysconf(_SC_CLK_TCK);
    if (ticksPerSecond <= 0) {
        cerr << "Unable to determine system clock ticks.\n";
        return 1;
    }

    map<string, ProcessData> previousProcesses;
    auto previousSample = SteadyClock::now();

    cout << "==================================================\n";
    cout << " AI LINUX SYSTEM - UNIFIED TELEMETRY COLLECTOR\n";
    cout << "==================================================\n";
    cout << "System output: data/system_telemetry_v2.csv\n";
    cout << "Process output: data/process_telemetry.csv\n";
    cout << "Shared sampling interval: 2 seconds\n";
    cout << "Both CSV files use one timestamp per collection cycle.\n";
    cout << "Press Ctrl+C to stop.\n\n";

    while (true) {
        const auto cycleStart = SteadyClock::now();
        double elapsed = chrono::duration<double>(cycleStart - previousSample).count();
        if (elapsed <= 0.0) elapsed = chrono::duration<double>(sampleInterval).count();

        // Capture the cycle timestamp once and reuse it in both files.
        const string timestamp = getTimestamp();

        SystemTelemetry system = collectSystemTelemetry();
        map<string, ProcessData> currentProcesses = collectProcesses();

        systemFile << timestamp << ','
                   << fixed << setprecision(2)
                   << system.cpu << ',' << system.memory << ','
                   << system.load1 << ',' << system.load5 << ',' << system.load15 << ','
                   << system.totalProcesses << ',' << system.runningProcesses << ','
                   << system.diskUsage << ',' << system.networkRX << ',' << system.networkTX << ','
                   << system.cpuTemperature << ',' << system.cpuFrequency << ','
                   << system.battery << '\n';
        systemFile.flush();

        size_t recorded = 0;
        for (const auto& item : currentProcesses) {
            const ProcessData& process = item.second;
            double cpuPercent = -1.0;
            auto previous = previousProcesses.find(item.first);
            if (previous != previousProcesses.end()) {
                unsigned long long currentTicks = process.userTime + process.systemTime;
                unsigned long long previousTicks = previous->second.userTime + previous->second.systemTime;
                if (currentTicks >= previousTicks) {
                    cpuPercent = (currentTicks - previousTicks) * 100.0 /
                                 (static_cast<double>(ticksPerSecond) * elapsed);
                }
            }

            string safeName = process.name;
            for (char& c : safeName) {
                if (c == '"' || c == '\n' || c == '\r' || c == ',') c = '_';
            }

            processFile << timestamp << ',' << process.pid << ",\"" << safeName << "\","
                        << process.state << ',' << fixed << setprecision(2)
                        << cpuPercent << ',' << process.memoryMB << ',' << process.threads << '\n';
            ++recorded;
        }
        processFile.flush();

        cout << "[" << timestamp << "] CPU: " << system.cpu
             << "% | RAM: " << system.memory
             << "% | System processes: " << system.totalProcesses
             << " | Process records: " << recorded << '\n';

        previousProcesses = move(currentProcesses);
        previousSample = cycleStart;

        const auto nextCycle = cycleStart + sampleInterval;
        this_thread::sleep_until(nextCycle);
    }

    return 0;
}
