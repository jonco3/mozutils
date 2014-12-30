# Common functions for python build scripts

import re
import os
import sys
import subprocess

# based on http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
def which(program):
    for path in os.environ["PATH"].split(os.pathsep):
        path = path.strip('"')
        file = os.path.join(path, program)
        if os.path.isfile(file) and os.access(file, os.X_OK):
            return file
    return None

def ensureExe(name):
    path = which(name)
    if not path:
        sys.exit("Can't find %s on path" % name)
    return path

timeStampRe = re.compile(" *[\d\.:]+ (.+)")

def stripTimestamp(line):
    match = timeStampRe.match(line)
    if not match:
        return line
    return match.group(1)

objectFileRe = re.compile("( *[\d\.:]+ )?\w+\.o")

def exit_with_code(code, message):
    sys.stderr.write(message + "\n")
    sys.exit(code)

# Exit with a message, skipping this revision for bisection
def exit_build_failed(message):
    exit_with_code(125, message)

# Exit with a message, aborting any bisection
def exit_fatal(message):
    exit_with_code(127, message)

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
            directory_line = stripTimestamp(line)
        elif "error:" in line or sawError:
            if directory_line:
                print(directory_line)
                directory_line = None
            print(stripTimestamp(line))
            sawError = True
        elif warnings and "warning:" in line:
            if directory_line:
                print(directory_line)
                directory_line = None
            print(stripTimestamp(line))
        elif objectFileRe.match(line):
            print(line)

    if proc.returncode:
        exit_build_failed("Command failed with returncode %d" % proc.returncode)

def chdir_to_source_root():
    lastDir = os.getcwd()
    while not os.path.isfile("client.mk") or not os.path.isdir("mfbt") or not os.path.isdir("js"):
        os.chdir("..")
        currentDir = os.getcwd()
        if currentDir == lastDir:
            sys.exit('Please run from within the mozilla source tree')
        lastDir = currentDir
