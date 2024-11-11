# -*- coding: utf-8 -*-

# Common functions for python build scripts

import io
import os
import pathlib
import platform
import re
import shutil
import subprocess
import sys
import time

from mozconfig import *

def add_build_arguments(parser):
    parser.add_argument('-v', '--verbose', action='store_true', help = 'Show all build output')
    parser.add_argument('-W', '--no-warnings', action='store_false', dest='warnings', default=True,
                        help = 'Hide warnings')
    parser.add_argument('--dir', nargs=1, action='append', dest='dirs',
                        help = 'Change directory before building')
    parser.add_argument('-r', '--remote', action='store_true', help = 'Build on remote machine')
    parser.add_argument('-R', '--ignore-remote', action='store_true', help=argparse.SUPPRESS)

    clean_group = parser.add_mutually_exclusive_group()
    clean_group.add_argument('-c', '--clean', action='store_true', help = 'Clean build')
    clean_group.add_argument('-C', '--no-clean', action='store_false', dest = 'clean')

def println(str):
    print(str, flush=True)

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

timeStampRe = re.compile(r" *[\d\.:]+ (.+)")

def stripTimestamp(line):
    match = timeStampRe.match(line)
    if not match:
        return line
    return match.group(1)

pathRe = re.compile(r"\w[\w\-_/\.]*")

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

        if "error:" in line or "error[" in line or "required from" in line:
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
    cmd = [os.path.join(binDir, 'syncBranch')]
    if args.sync_dir:
        cmd.append(args.sync_dir)
    subprocess.check_call(cmd)

def js_build(args):
    args.shell = True
    mach_build(args)

def mach_build(args):
    if os.path.isfile('.cloned-from') and not args.no_sync:
        sync_branch(args);

    config_names, config_options = get_configs_from_args(args)
    build_name = get_build_name(config_names)
    build_dir = build_name + '-build'
    build_config = "mozconfig-" + build_name

    if args.clean and (os.path.exists(build_dir) or os.path.exists(build_config)):
        println('Clean ' + build_name)
        println("  Cleaning will commence in 5 seconds!  Interrupt now to preserve the build")
        time.sleep(5);  # so I can hit ^C after I accidentally do this
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
        if os.path.exists(build_config):
            os.unlink(build_config)

    if not os.path.exists(build_dir):
        os.makedirs(build_dir)

    println("Build %s" % build_name)
    mach(args, ['build'])

def mach(args, mach_args, filter_output = True):
    config_names, config_options = get_configs_from_args(args)
    build_name = get_build_name(config_names)
    build_dir = build_name + '-build'
    build_config = "mozconfig-" + build_name

    if not os.path.exists(build_config):
        print("Generating mozconfig file: " + build_config)
        write_mozconfig(build_dir, config_options, build_config)

    setup_environment(args)
    os.environ['MOZCONFIG'] = os.path.abspath(build_config)
    mach = 'mach.cmd' if platform.system() == 'Windows' else './mach'
    cmd = [mach] + mach_args
    if filter_output:
        run_command(cmd, args.verbose, args.warnings)
    else:
        os.execv(cmd[0], cmd)

def ensure_js_src_links(args):
    config_names, _ = get_configs_from_args(args)
    build_name = get_build_name(config_names)
    config_names.remove('shell')
    js_src_build_name = get_build_name(config_names)

    build_dir = build_name + '-build'
    js_src_build_dir = js_src_build_name + '-build'

    abs_build_dir = os.path.abspath(build_dir)
    os.chdir("js/src")
    if not os.path.exists(js_src_build_dir):
        os.makedirs(js_src_build_dir)
    os.chdir(js_src_build_dir)
    ensure_link(os.path.join(abs_build_dir, 'dist/bin/js'), 'shell')
    ensure_link(os.path.join(abs_build_dir, 'dist/bin/jsapi-tests'), 'jsapi-tests')
    os.chdir("../../..")


def ensure_link(source_path, target_path):
    source_path = get_exe_path(source_path)
    target_path = get_exe_path(target_path)
    if not os.path.lexists(target_path):
        os.symlink(source_path, target_path)

def get_exe_path(path):
    if platform.system() == 'Windows':
        path += '.exe'
    return path

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

def run_remote_command(args):
    def println(str):
        # Why do I have to add CR now???
        print(str + "\r", flush=True)

    localDir = os.getcwd()
    branchName = os.path.basename(localDir)
    script = os.path.basename(sys.argv[0])
    command = ['ssh', get_build_remote(), '-t', '-t', script, '--dir', 'clone', '--dir',
               branchName, '--ignore-remote'] + sys.argv[1:]
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    remoteDir = None
    for line in proc.stdout:
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
