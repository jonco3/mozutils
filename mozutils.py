# Common functions for python build scripts

import re
import sys
import subprocess

def which(name):
    try:
        return subprocess.check_output('which ' + name, shell = True).splitlines()[0]
    except subprocess.CalledProcessError:
        return None

timeStampRe = re.compile(" *[\d\.:]+ (.+)")

def stripTimestamp(line):
    match = timeStampRe.match(line)
    if not match:
        return line
    return match.group(1)

objectFileRe = re.compile("( *[\d\.:]+ )?\w+\.o")

def run_command(command, verbose, warnings):
    if verbose:
        print(command)
    proc = subprocess.Popen(command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT,
                            shell = True)
    directory_line = None
    sawError = False
    while proc.poll() == None:
        line = proc.stdout.readline().rstrip()
        if not line:
            continue

        if verbose:
            print(line)
        elif "Entering directory" in line:
            directory_line = line
        elif "error:" in line or sawError:
            if directory_line:
                print(stripTimestamp(directory_line))
                directory_line = None
            print(stripTimestamp(line))
            sawError = True
        elif warnings and "warning:" in line:
            if directory_line:
                print(stripTimestamp(directory_line))
                directory_line = None
            print(stripTimestamp(line))
        elif objectFileRe.match(line):
            print(line)

    if proc.returncode:
        sys.exit('Command failed with returncode ' + str(proc.returncode))
