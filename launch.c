#define _POSIX_SOURCE
#include <stdio.h>
#include <errno.h>
#include <signal.h>
#include <unistd.h>
#include <string.h>
#include <stdlib.h>
#include <assert.h>
#include <signal.h>
#include <sys/types.h>


static const char *PID_FILE_PATH_TEMPLATE = "/run/user/%d/textual-switcher.pid";
static const char *PYTHON_EXE_PATH = "/usr/bin/python";
static const char *SCRIPT_PATH = "/usr/share/textual-switcher/main.py";


void exec_switcher(char *pid_file_path)
{
    char *switcher_argv[] = {(char*)PYTHON_EXE_PATH,
                             (char*)SCRIPT_PATH,
                             (char*)pid_file_path,
                             NULL};
    execvp(PYTHON_EXE_PATH, switcher_argv);
    exit(1);
}

int main(void)
{
    char pid_file_path[100];
    const uid_t uid = getuid();
    snprintf((char*)&pid_file_path, sizeof(pid_file_path), PID_FILE_PATH_TEMPLATE, uid);
    FILE *pid_file = fopen(pid_file_path, "r");
    char pid_file_content[20];
    int pid = 0;
    const size_t pid_file_content_buffer_size = sizeof(pid_file_content) /
        sizeof(pid_file_content[0]);
    if (NULL == pid_file) {
        exec_switcher(pid_file_path);
    }
    const size_t amount_read = fread(pid_file_content, 1,
        pid_file_content_buffer_size, pid_file);
    if (amount_read <= 0) {
        exec_switcher(pid_file_path);
    }
    if (strlen(pid_file_content) == 0) {
        exec_switcher(pid_file_path);
    }
    pid = atoi(pid_file_content);
    if (pid < 0) {
        exec_switcher(pid_file_path);
    }
    const int result = kill(pid, SIGHUP);
    if (0 != result) {
        exec_switcher(pid_file_path);
    }
    return 0;
}
