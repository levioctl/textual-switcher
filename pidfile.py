import os


def create(pid_filepath):
    with open(pid_filepath, "w") as f:
        pid = str(os.getpid())
        f.write(pid)
