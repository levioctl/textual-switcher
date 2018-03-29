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


static const char *PID_FILE_PATH = "/run/lock/textual_switcher.pid";
static const char *PYTHON_EXE_PATH = "/usr/bin/python";
static const char *SCRIPT_PATH = "/usr/share/textual-switcher/switcher.py";


void exec_switcher(void)
{
    char *switcher_argv[] = {(char*)PYTHON_EXE_PATH,
                             (char*)SCRIPT_PATH,
                             (char*)PID_FILE_PATH,
                             NULL};
    execvp(PYTHON_EXE_PATH, switcher_argv);
    exit(1);
}

int main(void)
{
    FILE *pid_file = fopen(PID_FILE_PATH, "r");
    char pid_file_content[20];
    int pid = 0;
    const size_t pid_file_content_buffer_size = sizeof(pid_file_content) /
        sizeof(pid_file_content[0]);
    if (NULL == pid_file) {
        exec_switcher();
    }
    const size_t amount_read = fread(pid_file_content, 1,
        pid_file_content_buffer_size, pid_file);
    if (amount_read <= 0) {
        exec_switcher();
    }
    if (strlen(pid_file_content) == 0) {
        exec_switcher();
    }
    pid = atoi(pid_file_content);
    if (pid < 0) {
        exec_switcher();
    }
    const int result = kill(pid, SIGHUP);
    if (0 != result) {
        exec_switcher();
    }
    return 0;
}
