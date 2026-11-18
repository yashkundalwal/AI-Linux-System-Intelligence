
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
#include <sys/statvfs.h>

using namespace std;
namespace fs = std::filesystem;

struct Telemetry {
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

double getCPUUsage() {
    static unsigned long long previousIdle = 0;
    static unsigned long long previousTotal = 0;
    static bool initialized = false;

    ifstream file("/proc/stat");

    string cpu;
    unsigned long long user, nice, system, idle;
    unsigned long long iowait, irq, softirq, steal;

    if (!(file >> cpu >> user >> nice >> system
          >> idle >> iowait >> irq >> softirq >> steal)) {
        return -1;
    }

    unsigned long long idleAll = idle + iowait;

    unsigned long long total =
        user + nice + system + idle + iowait +
        irq + softirq + steal;

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
    unsigned long long total = 0;
    unsigned long long available = 0;
    unsigned long long value;

    while (file >> key >> value >> unit) {
        if (key == "MemTotal:") total = value;
        if (key == "MemAvailable:") available = value;
    }

    if (total == 0) return -1;

    return 100.0 * (total - available) / total;
}

void getLoadAverage(Telemetry& t) {
    ifstream file("/proc/loadavg");

    if (file.is_open()) {
        file >> t.load1 >> t.load5 >> t.load15;
    }
}

void getProcessInformation(Telemetry& t) {
    error_code ec;

    for (const auto& entry : fs::directory_iterator("/proc", ec)) {
        if (ec) break;

        string name = entry.path().filename().string();

        if (name.empty()) continue;

        bool numeric = true;

        for (char c : name) {
            if (!isdigit(static_cast<unsigned char>(c))) {
                numeric = false;
                break;
            }
        }

        if (!numeric) continue;

        ifstream status(entry.path() / "status");

        string line;

        while (getline(status, line)) {
            if (line.rfind("State:", 0) == 0) {
                t.totalProcesses++;

                if (line.find("R") != string::npos)
                {
                    t.runningProcesses++;
                }

                break;
            }
        }
    }
}

double getDiskUsage() {
    struct statvfs diskInfo {};

    if (statvfs("/", &diskInfo) != 0) {
        return -1;
    }

    unsigned long long total =
        static_cast<unsigned long long>(diskInfo.f_blocks) *
        diskInfo.f_frsize;

    unsigned long long available =
        static_cast<unsigned long long>(diskInfo.f_bavail) *
        diskInfo.f_frsize;

    if (total == 0) return -1;

    unsigned long long used = total - available;

    return 100.0 * used / total;
}

void getNetworkTraffic(Telemetry& t) {
    ifstream file("/proc/net/dev");

    if (!file.is_open()) return;

    string line;

    getline(file, line);
    getline(file, line);

    while (getline(file, line)) {
        size_t colon = line.find(':');

        if (colon == string::npos) continue;

        string interfaceName = line.substr(0, colon);

        interfaceName.erase(
            0, interfaceName.find_first_not_of(" \t")
        );

        // Count physical Ethernet and Wi-Fi interfaces.
        bool physical =
            interfaceName.rfind("en", 0) == 0 ||
            interfaceName.rfind("eth", 0) == 0 ||
            interfaceName.rfind("wl", 0) == 0;

        if (!physical) continue;

        istringstream values(line.substr(colon + 1));

        unsigned long long rx = 0, tx = 0;
        unsigned long long packets, errors, drops;

        if (!(values >> rx >> packets >> errors >> drops)) {
            continue;
        }

        for (int i = 0; i < 4; i++) {
            unsigned long long ignored;
            if (!(values >> ignored)) break;
        }

        if (!(values >> tx)) continue;

        t.networkRX += rx;
        t.networkTX += tx;
    }
}

double getCPUTemperature() {
    error_code ec;

    fs::path hwmon("/sys/class/hwmon");

    if (fs::exists(hwmon, ec)) {
        for (const auto& device : fs::directory_iterator(hwmon, ec)) {
            if (ec) break;

            for (const auto& sensor :
                 fs::directory_iterator(device.path(), ec)) {
                if (ec) break;

                string name = sensor.path().filename().string();

                if (name.find("temp") != 0 ||
                    name.find("_input") == string::npos) {
                    continue;
                }

                ifstream file(sensor.path());

                long long value;

                if (file >> value) {
                    return value / 1000.0;
                }
            }
        }
    }

    return -1;
}

double getCPUFrequency() {
    error_code ec;

    fs::path cpuPath("/sys/devices/system/cpu");

    double total = 0;
    int count = 0;

    if (!fs::exists(cpuPath, ec)) return -1;

    for (const auto& cpu : fs::directory_iterator(cpuPath, ec)) {
        if (ec) break;

        string name = cpu.path().filename().string();

        if (name.rfind("cpu", 0) != 0 ||
            name.size() <= 3) {
            continue;
        }

        bool numeric = true;

        for (char c : name.substr(3)) {
            if (!isdigit(static_cast<unsigned char>(c))) {
                numeric = false;
                break;
            }
        }

        if (!numeric) continue;

        long long frequency = 0;

        ifstream file(
            cpu.path() / "cpufreq/scaling_cur_freq"
        );

        if (!(file >> frequency)) continue;

        total += frequency / 1000.0;
        count++;
    }

    if (count == 0) return -1;

    return total / count;
}

int getBatteryPercentage() {
    error_code ec;

    fs::path powerPath("/sys/class/power_supply");

    if (!fs::exists(powerPath, ec)) return -1;

    for (const auto& device : fs::directory_iterator(powerPath, ec)) {
        if (ec) break;

        ifstream typeFile(device.path() / "type");

        string type;

        if (!(typeFile >> type) || type != "Battery") {
            continue;
        }

        ifstream capacityFile(device.path() / "capacity");

        int capacity;

        if (capacityFile >> capacity) {
            return capacity;
        }
    }

    return -1;
}

string getTimestamp() {
    time_t now = time(nullptr);
    tm* local = localtime(&now);

    if (!local) return "Unavailable";

    stringstream stream;

    stream << put_time(local, "%Y-%m-%d %H:%M:%S");

    return stream.str();
}

Telemetry collectTelemetry() {
    Telemetry t;

    t.cpu = getCPUUsage();
    t.memory = getMemoryUsage();

    getLoadAverage(t);
    getProcessInformation(t);

    t.diskUsage = getDiskUsage();

    getNetworkTraffic(t);

    t.cpuTemperature = getCPUTemperature();
    t.cpuFrequency = getCPUFrequency();
    t.battery = getBatteryPercentage();

    return t;
}

int main() {
    const string filename = "data/system_telemetry_v2.csv";

    ofstream file(filename, ios::app);

    if (!file.is_open()) {
        cerr << "Unable to open telemetry CSV.\n";
        return 1;
    }

    if (file.tellp() == 0) {
        file << "timestamp,cpu_usage,memory_usage,"
             << "load_1,load_5,load_15,"
             << "total_processes,running_processes,"
             << "disk_usage,network_rx_bytes,network_tx_bytes,"
             << "cpu_temperature,cpu_frequency_mhz,battery_percent\n";
    }

    cout << "AI Linux Integrated System Agent Started\n";
    cout << "Collecting system telemetry...\n";
    cout << "Output: " << filename << endl;
    cout << "Press Ctrl+C to stop.\n\n";

    while (true) {
        Telemetry t = collectTelemetry();

        if (t.cpu >= 0 && t.memory >= 0) {
            string timestamp = getTimestamp();

            file << timestamp << ","
                 << fixed << setprecision(2)
                 << t.cpu << ","
                 << t.memory << ","
                 << t.load1 << ","
                 << t.load5 << ","
                 << t.load15 << ","
                 << t.totalProcesses << ","
                 << t.runningProcesses << ","
                 << t.diskUsage << ","
                 << t.networkRX << ","
                 << t.networkTX << ","
                 << t.cpuTemperature << ","
                 << t.cpuFrequency << ","
                 << t.battery << "\n";

            file.flush();

            cout << "CPU: " << t.cpu
                 << "% | RAM: " << t.memory
                 << "% | Processes: " << t.totalProcesses
                 << " | Disk: " << t.diskUsage
                 << "% | Temperature: " << t.cpuTemperature
                 << " C | Battery: " << t.battery
                 << "%\n";
        }

        this_thread::sleep_for(chrono::seconds(2));
    }

    return 0;
}
