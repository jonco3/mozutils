# -*- coding: utf-8 -*-

import os.path
import re
import subprocess
import sys

import stats
import format

################################################################################
# Utils
################################################################################

def ensure(condition, error):
    if not condition:
        sys.exit(error)

def canExecute(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)

################################################################################
# Tests
################################################################################

class Test:
    def __init__(self, name, args):
        self.name = name
        self.args = args

    def checkArgs(self, args):
        pass

def findTest(tests, name):
    for test in tests:
        if test.name == name:
            return test
    return None

################################################################################
# Builds
################################################################################

class Build:
    def __init__(self, spec):
        elements = spec.split()
        path = elements[0]
        self.name = os.path.normpath(path) + ' '.join(elements[1:])
        self.path = os.path.abspath(path)
        ensure(os.path.isdir(self.path), "Build path is not a directory")
        ensure(canExecute(os.path.join(self.path, 'dist', 'bin', 'firefox')),
               f"Build {self.name} does not contain FF executable")
        ensure(canExecute(os.path.join(self.path, '..', 'mach')),
               f"Build {self.name} does not contain mach executable")

        self.dir = os.path.dirname(self.path)
        self.mozconfig = self.findMozConfig()
        ensure(self.mozconfig,
               "Can't find MOZCONFIG line in config/autoconf.mk")
        ensure(os.path.isfile(self.mozconfig),
               "Can't find MOZCONFIG file: " + self.mozconfig)

        self.prefs = []
        for pref in elements[1:]:
            ensure(re.match(r'[\w\.]+=', pref),
                   "Bad pref setting: " + pref)
            self.prefs.append(pref)

        self.results = ResultSet()

    def __repr__(self):
        return f"Build({self.name}, {self.path}, {self.dir}, {self.mozconfig})"

    def findMozConfig(self):
        config_file = os.path.join(self.path, 'config', 'autoconf.mk')
        ensure(os.path.isfile(config_file), "Can't find config/autoconf.mk")
        with open(config_file) as file:
            for line in file:
                match = re.match(r'MOZCONFIG = (.+)', line)
                if match:
                    return match.group(1)
        return None

################################################################################
# Tasks
################################################################################

class Task:
    def __init__(self, build, test, cmd, env, cwd, profilePath):
        self.build = build
        self.test = test
        self.cmd = cmd
        self.env = env
        self.cwd = cwd
        self.profilePath = profilePath
        self.running = False

    def start(self):
        self.proc = subprocess.Popen(self.cmd, env=self.env, cwd=self.cwd, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.running = True

    def failed(self):
        assert not self.running
        return self.proc.poll() != 0

    def poll(self, timeout=1):
        try:
            self.stdout, self.stderr = self.proc.communicate(timeout=timeout)
            self.proc.wait()
            self.running = False
        except subprocess.TimeoutExpired:
            pass
        except:
            self.proc.kill()
            self.proc.wait()
            raise

    def run(self):
        self.start()
        while self.running:
            self.poll(1)  # seconds

        if self.failed():
            self.reportFailedAndExit()

    def reportFailedAndExit(self):
        print(f"Error running benchmark {self.test.name} for build {self.build.name}:")
        print(' '.join(self.cmd))
        print('stdout:')
        print(self.stdout)
        print('stderr:')
        print(self.stderr)
        sys.exit(1)

################################################################################
# Test results
################################################################################

# The results from many test runs
class ResultSet:
    def __init__(self):
        self.results = dict()
        self.stats = None

    def keys(self):
        return self.results.keys()

    def addResult(self, key, value):
        if key not in self.results:
            self.results[key] = []
        self.results[key].append(value)

    def createStatsSet(self):
        statsSet = dict()
        for name in self.results:
            statsSet[name] = stats.Stats(self.results[name])
        return statsSet

################################################################################
# Display
################################################################################

def displayResults(out, builds, showSamples):
    out.clear()

    statsSets = dict()
    for build in builds:
        statsSets[build.name] = build.results.createStatsSet()

    keysToDisplay = findAllKeys(list(statsSets.values()))
    if not keysToDisplay:
        out.print("No results to display")
        return

    displayHeader(out)

    for key in keysToDisplay:
        statsSetsForKey = [statsSets[build.name][key] for build in builds
                           if key in statsSets[build.name]]
        minAll = min(map(lambda stats: stats.min, statsSetsForKey))
        maxAll = max(map(lambda stats: stats.max, statsSetsForKey))

        if minAll == 0 and maxAll == 0:
            continue  # No interesting data, skip this key.

        compareTo = None
        if len(statsSetsForKey) > 1:
            compareTo = statsSetsForKey[0]

        out.print(f"{key}:")

        for build in builds:
            if key not in statsSets[build.name]:
                continue

            stats = statsSets[build.name][key]
            comp = stats.compareTo(compareTo)
            main = format.formatStats(stats, comp)

            box = ''
            if minAll != maxAll and stats.count > 1:
                box = format.formatBox(minAll, maxAll, stats)

            out.print("  %20s  %s  %s" % (build.name[-20:], main, box))

            if showSamples and minAll != maxAll:
                samples = format.formatSamples(minAll, maxAll, stats)
                out.print("%76s%s" % ('', samples))

def findAllKeys(statsSets):
    keys = list(statsSets.pop(0).keys())
    for statsSet in statsSets:
        for key in statsSet.keys():
            if key not in keys:
                keys.append(key)
    return keys

def displayHeader(out):
    header = (24 * " ") + format.statsHeader()
    out.print(header)
    out.print(len(header) * "=")
