
#include <iostream>
#include <string>
#include <fstream>
#include <sstream>
#include <filesystem>
#include <vector>
#include <limits>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/types.h>

using namespace std;
namespace fs = std::filesystem;

struct ProcessInfo {
    int pid;
    string name;
    string start_time;
};

bool getProcessInfo(int pid, ProcessInfo &process) {
    string path = "/proc/" + to_string(pid) + "/stat";

    ifstream file(path);
    if (!file.is_open()) {
        return false;
    }

    string line;
    getline(file, line);

    // The process name may contain spaces or parentheses.
    size_t open = line.find('(');
    size_t close = line.rfind(')');

    if (open == string::npos || close == string::npos ||
        close <= open) {
        return false;
    }

    process.pid = pid;
    process.name = line.substr(open + 1, close - open - 1);

    // Fields after ')' begin with field 3 (state).
    istringstream stream(line.substr(close + 2));

    string value;

    // Field 22 is starttime.
    for (int i = 0; i <= 19; i++) {
        if (!(stream >> value)) {
            return false;
        }
    }

    process.start_time = value;
    return true;
}

bool isValidPID(const string &input, int &pid) {
    if (input.empty()) {
        return false;
    }

    for (char ch : input) {
        if (ch < '0' || ch > '9') {
            return false;
        }
    }

    try {
        long long number = stoll(input);

        if (number <= 0 || number > numeric_limits<int>::max()) {
            return false;
        }

        pid = static_cast<int>(number);
        return true;
    }
    catch (...) {
        return false;
    }
}

bool confirmAction(const string &description) {
    cout << "\nAction: " << description << "\n";
    cout << "Do you want to continue? (y/n): ";

    string choice;
    cin >> choice;

    return choice == "y" || choice == "Y";
}

bool runCommand(const vector<string> &arguments) {
    if (arguments.empty()) {
        return false;
    }

    pid_t child = fork();

    if (child < 0) {
        perror("fork");
        return false;
    }

    if (child == 0) {
        vector<char*> args;

        for (const string &arg : arguments) {
            args.push_back(const_cast<char*>(arg.c_str()));
        }

        args.push_back(nullptr);

        execvp(args[0], args.data());

        perror("execvp");
        _exit(127);
    }

    int status;
    if (waitpid(child, &status, 0) < 0) {
        perror("waitpid");
        return false;
    }

    return WIFEXITED(status) && WEXITSTATUS(status) == 0;
}

bool processStillMatches(const ProcessInfo &original) {
    ProcessInfo current;

    if (!getProcessInfo(original.pid, current)) {
        cout << "\nProcess no longer exists.\n";
        return false;
    }

    if (current.start_time != original.start_time) {
        cout << "\nPID has been reused by another process. Aborting.\n";
        return false;
    }

    return true;
}

void inspectProcess(const ProcessInfo &process) {
    if (!processStillMatches(process)) {
        return;
    }

    cout << "\nInspecting process: " << process.name
         << " (PID " << process.pid << ")\n";

    vector<string> command = {
        "ps", "-p", to_string(process.pid),
        "-o", "pid,ppid,stat,%cpu,%mem,rss,etime,cmd"
    };

    runCommand(command);
}

void monitorProcess(const ProcessInfo &process) {
    if (!processStillMatches(process)) {
        return;
    }

    vector<string> command = {
        "top", "-b", "-n", "1",
        "-p", to_string(process.pid)
    };

    runCommand(command);
}

int main() {
    cout << "=================================================\n";
    cout << "       AI LINUX SYSTEM - ACTION AGENT\n";
    cout << "=================================================\n";

    cout << "\nThis agent currently supports read-only inspection.\n";
    cout << "No process will be terminated or modified.\n";

    string input;
    cout << "\nEnter PID from your AI recommendation report: ";
    cin >> input;

    int pid;

    if (!isValidPID(input, pid)) {
        cout << "\nInvalid PID.\n";
        return 1;
    }

    ProcessInfo process;

    if (!getProcessInfo(pid, process)) {
        cout << "\nProcess not found or inaccessible.\n";
        return 1;
    }

    cout << "\nProcess identified successfully.\n";
    cout << "PID: " << process.pid << "\n";
    cout << "Name: " << process.name << "\n";

    while (true) {
        cout << "\n---------------- ACTION MENU ----------------\n";
        cout << "1. Inspect process details\n";
        cout << "2. Monitor process using top\n";
        cout << "3. Refresh process information\n";
        cout << "4. Exit\n";
        cout << "----------------------------------------------\n";

        cout << "Select an option: ";

        int choice;
        if (!(cin >> choice)) {
            cout << "\nInvalid input. Exiting.\n";
            break;
        }

        switch (choice) {
            case 1:
                if (confirmAction("Display process details")) {
                    inspectProcess(process);
                }
                break;

            case 2:
                if (confirmAction("Run a one-time process monitor")) {
                    monitorProcess(process);
                }
                break;

            case 3:
                if (getProcessInfo(pid, process)) {
                    cout << "\nProcess information refreshed.\n";
                    cout << "Name: " << process.name << "\n";
                } else {
                    cout << "\nProcess no longer exists.\n";
                }
                break;

            case 4:
                cout << "\nExiting action agent.\n";
                return 0;

            default:
                cout << "\nInvalid option.\n";
        }
    }

    return 0;
}
