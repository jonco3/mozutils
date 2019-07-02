# Common functions for python build scripts

import io
import os
import re
import subprocess
import sys

def println(str):
    print(str, flush = True)

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

objectFileRe = re.compile("(\w[\w\-_]*)\.o")

pathRe = re.compile("\w[\w\-_/\.]*")

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
        println(" ".join(command))
    proc = subprocess.Popen(command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    directory_line = None
    for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):
        line = line.rstrip();
        if not line:
            continue

        line = stripTimestamp(line)

        if verbose:
            println(line)
            continue

        if "Entering directory" in line:
            directory_line = line
            continue

        if "error:" in line or "required from" in line:
            verbose = True
            if directory_line:
                println(directory_line)
                directory_line = None
            println(line)
            continue

        match = objectFileRe.match(line)
        if (match):
            println("  " + match.group(1))
            continue

        words = line.split()
        if len(words) > 2 and words[0] == "Compiling":
            println("  " + words[1])
            continue

        if len(words) == 1 and pathRe.fullmatch(words[0]):
            println("  " + words[0])

    proc.wait()
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

def get_icecream_path():
    path = which('icecc')
    if path:
        path = os.path.dirname(path)
        if sys.platform == 'darwin':
            path = os.path.dirname(path)
    return path
