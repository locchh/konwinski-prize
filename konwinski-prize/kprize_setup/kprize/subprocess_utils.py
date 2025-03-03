# waits for full command to complete, output sent to file and console
import subprocess

from kprize.time_utils import current_ms, seconds_since


def run_commands(cmds: list[str], log_file=None, console_log=True, log_commands=False):
    if log_file:
        print(f"Writing command logs to {log_file.name}")
    commands = '\n'.join(cmds)
    if log_commands:
        print("Running commands:")
        print(commands)
        print("\n")
    process = subprocess.Popen(
        '/bin/bash',
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True)
    out, err = process.communicate(commands)
    if console_log:
        print("Command stderr:")
        print(err)
        print("Command stdout:")
        print(out)
    if log_file:
        log_file.write(err)
        log_file.write(out)


def run_command_stream(cmds: list[str], log_file=None):
    """
    Run a list of commands in a subprocess, streaming the output to the console and optionally to a log file

    WARNING: This function DOES NOT wait for the command to complete before returning

    :param cmds:
    :param log_file:
    :return:
    """
    if log_file:
        print(f"Writing command logs to {log_file.name}")
    commands = ';'.join(cmds)
    start_ms = current_ms()
    tsk = subprocess.Popen(
        commands,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        universal_newlines=True,
        executable="/bin/bash"
    )

    while tsk.poll() is None:
        line = tsk.stdout.readline()
        print(line, end="")
        if log_file:
            log_file.write(line)

    tsk.wait()
    print(f"Completed in {seconds_since(start_ms)} seconds")


def echo_command_start_and_finish(cmds: [str]):
    cmds_with_echo = []
    for idx, cmd in enumerate(cmds):
        cmds_with_echo.append(f'echo "=== START: Command {idx} ==="')  # {shlex.quote(cmd)[0:30]}
        cmds_with_echo.append(cmd)
        cmds_with_echo.append(f'echo "=== FINISH: Command {idx} ==="')

    return cmds_with_echo
