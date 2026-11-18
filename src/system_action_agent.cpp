
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <unistd.h>
#include <sys/wait.h>
#include <limits>

using namespace std;

struct Recommendation {
    string priority;
    int pid;
    string name;
    string cpu;
    string memory;
    string description;
};

struct ProcessInfo {
    int pid;
    string name;
    string start_time;
};

vector<string> splitTSV(const string &line) {
    vector<string> fields;
    string field;
    stringstream stream(line);

    while (getline(stream, field, '\t')) {
        fields.push_back(field);
    }

    return fields;
}

bool loadRecommendations(vector<Recommendation> &items) {
    ifstream file("data/processed/action_queue.tsv");

    if (!file.is_open()) {
        cerr << "Cannot open action_queue.tsv\n";
        return false;
    }

    string line;
    getline(file, line); // Skip header

    while (getline(file, line)) {
        vector<string> fields = splitTSV(line);

        if (fields.size() != 6) {
            continue;
        }

        try {
            Recommendation item;
            item.priority = fields[0];
            item.pid = stoi(fields[1]);
            item.name = fields[2];
            item.cpu = fields[3];
            item.memory = fields[4];
            item.description = fields[5];

            if (item.pid > 0) {
                items.push_back(item);
            }
        }
        catch (...) {
            continue;
        }
    }

    return true;
}

bool getProcessInfo(int pid, ProcessInfo &process) {
    string path = "/proc/" + to_string(pid) + "/stat";

    ifstream file(path);
    if (!file.is_open()) {
        return false;
    }

    string line;
    getline(file, line);

    size_t open = line.find('(');
    size_t close = line.rfind(')');

    if (open == string::npos ||
        close == string::npos || close <= open) {
        return false;
    }

    process.pid = pid;
    process.name = line.substr(open + 1, close - open - 1);

    istringstream stream(line.substr(close + 2));
    string value;

    // Fields after ')' start at field 3.
    // starttime is field 22, so skip 19 fields first.
    for (int i = 0; i <= 19; i++) {
        if (!(stream >> value)) {
            return false;
        }
    }

    process.start_time = value;
    return true;
}

bool confirmAction(const string &description) {
    cout << "\nAction: " << description << "\n";
    cout << "Confirm? (y/n): ";

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

void inspectProcess(const Recommendation &item) {
    ProcessInfo process;

    if (!getProcessInfo(item.pid, process)) {
        cout << "\nProcess no longer exists or is inaccessible.\n";
        return;
    }

    if (process.name != item.name) {
        cout << "\nProcess name mismatch. Aborting.\n";
        return;
    }

    string originalStartTime = process.start_time;

    cout << "\nLive process identified:\n";
    cout << "PID: " << process.pid << "\n";
    cout << "Name: " << process.name << "\n";

    cout << "\nAI observation:\n";
    cout << "Priority: " << item.priority << "\n";
    cout << "CPU: " << item.cpu << "%\n";
    cout << "Memory: " << item.memory << " MB\n";
    cout << "Recommendation: " << item.description << "\n";

    if (!confirmAction("Inspect this process using ps")) {
        cout << "Inspection cancelled.\n";
        return;
    }

    ProcessInfo current;

    if (!getProcessInfo(item.pid, current) ||
        current.name != item.name ||
        current.start_time != originalStartTime) {
        cout << "\nProcess identity changed. Aborting.\n";
        return;
    }

    runCommand({
        "ps", "-p", to_string(item.pid),
        "-o", "pid,ppid,stat,%cpu,%mem,rss,etime,cmd"
    });
}

int main() {
    cout << "====================================================\n";
    cout << "     AI LINUX SYSTEM - INTEGRATED ACTION AGENT\n";
    cout << "====================================================\n";

    cout << "\nLoading Python-generated recommendations...\n";

    vector<Recommendation> recommendations;

    if (!loadRecommendations(recommendations)) {
        return 1;
    }

    if (recommendations.empty()) {
        cout << "\nNo process recommendations available.\n";
        return 0;
    }

    cout << "\nLoaded " << recommendations.size()
         << " recommendations.\n";

    while (true) {
        cout << "\n=============== AI RECOMMENDATIONS ===============\n";

        for (size_t i = 0; i < recommendations.size(); i++) {
            const auto &item = recommendations[i];

            cout << i + 1 << ". [" << item.priority << "] "
                 << item.name << " (PID " << item.pid << ")\n";

            cout << "   CPU: " << item.cpu
                 << "% | Memory: " << item.memory << " MB\n";
        }

        cout << "\n0. Exit\n";
        cout << "Select recommendation: ";

        int choice;

        if (!(cin >> choice)) {
            cout << "Invalid input.\n";
            return 1;
        }

        if (choice == 0) {
            cout << "\nExiting integrated action agent.\n";
            break;
        }

        if (choice < 1 ||
            choice > static_cast<int>(recommendations.size())) {
            cout << "Invalid selection.\n";
            continue;
        }

        inspectProcess(recommendations[choice - 1]);
    }

    return 0;
}
