# -*- coding: utf-8 -*-

# Common functions for python build scripts

import io
import os
import pathlib
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

        if "error: " in line or "required from" in line:
            verbose = True
            if directory_line:
                println(directory_line)
                directory_line = None
            println(line)
            continue

        words = line.split()
        if len(words) >= 2 and (words[0] == "Compiling" or words[0] == "Creating"):
            println("  " + words[1])
        elif len(words) == 1 and re.fullmatch(r"\w[\w\-_/\.]*", words[0]):
            println("  " + words[0])
        else:
            pass # Ignore line

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

def sync_branch(args):
    libDir = os.path.dirname(__file__)
    binDir = os.path.join(libDir, '..', 'bin')
    cmd = [ os.path.join(binDir, 'syncBranch') ]
    if args.sync == "js":
        cmd.append("-j")
    subprocess.check_call(cmd)

def disable_unified_build(path):
    with open(path, "r") as file:
        content = file.read()
    content = re.sub("FILES_PER_UNIFIED_FILE = \\d+\n", "FILES_PER_UNIFIED_FILE = 1", content)
    with open(path, "w") as file:
        file.write(content)

def get_configs_from_args(args):
    names = []
    options = []

    options.append("--with-ccache=$HOME/.mozbuild/sccache/sccache")
    options.append("--enable-warnings-as-errors")

    if args.opt:
        names.append('opt')
        options.append('--enable-optimize')
        options.append('--disable-debug')
    elif args.optdebug:
        names.append('optdebug')
        options.append('--enable-optimize')
        options.append('--enable-debug')
        options.append('--enable-gczeal')
    else:
        options.append('--disable-optimize')
        options.append('--enable-debug')
        options.append('--enable-gczeal')

    if args.target32:
        names.append('32bit')
        options.append('--target=i686-pc-linux')

    return names, options

def get_build_name(config_names):
    """
    Get a canonical build name from a list of configs.
    """
    name_elements = config_names.copy()
    if not name_elements:
        name_elements.append("default")
    return '-'.join(name_elements)

def write_mozconfig(build_dir, options, build_config):
    with open(build_config, "w") as file:
        def w(line):
            file.write(f"{line}\n")

        w(f"mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/{build_dir}")
        w("mk_add_options AUTOCLOBBER=1")
        for option in options:
            w(f"ac_add_options {option}")

# Functions for handling remote builds:

def get_build_remote():
    path = os.path.join(pathlib.Path.home(), ".build-remote")
    if not os.path.isfile(path):
        sys.exit("Can't read remote host from " + path);
    with open(path, "r") as file:
        return file.readline().strip()

def enter_dirs(dirs):
    if not dirs:
        return

    for dir in dirs:
        os.chdir(dir[0])
    println("Entered dir: " + os.getcwd())

def run_remote_comment(args):
    localDir = os.getcwd()
    branchName = os.path.basename(localDir)
    script = os.path.basename(sys.argv[0])
    command = ['ssh', get_build_remote(), '-t', '-t', script, '--dir', 'clone', '--dir',
               branchName] + \
              [ arg for arg in sys.argv[1:] if arg != '-r' and arg != '--remote' ]
    proc = subprocess.Popen(command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
    remoteDir = None
    for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):
        line = line.rstrip();
        if not remoteDir:
            match = re.match("^Entered dir: (.+)", line)
            if match:
                remoteDir = match.group(1)
                println("Remote dir: " + remoteDir)
                continue
        if remoteDir and line.startswith(remoteDir):
            line = localDir + line[len(remoteDir):]
            line = re.sub("/clone/", "/work/", line)
        line = re.sub("‘|’", "'", line)  # This is an encoding problem somewhere.
        println(line)
    proc.wait()
    return proc.returncode
