import glob
import os.path
import re
import sys

# Match double quoted but not angle bracketed includes.
IncludeRe = re.compile('^#include\s+"([^\s]+)"')

def findAllPublicHeaders():
    return glob.glob("public/*.h") + glob.glob("public/*/*.h")

def dirContainsSource(name):
    return not ("test" in name or
                "build" in name or
                "devtools" in name or
                "libffi" in name or
                "none" in name or
                "arm" in name or
                "mips" in name or
                "x64" in name or
                "vtune" in name or
                "zydis" in name or
                "gdb" in name)

def findPathsBySuffix(rootPath, suffix):
    paths = []
    for root, dirs, names in os.walk(rootPath):
        dirs[:] = filter(dirContainsSource, dirs)
        for name in names:
            if name.endswith(suffix):
                paths.append(os.path.join(root, name))

    return paths

def findAllCppFiles():
    return findPathsBySuffix('src', '.cpp')

def findAllHeaderFiles():
    return findAllPublicHeaders() + findPathsBySuffix('src', '.h')

def shouldProcessInclude(path):
    return (path.endswith(".h") and
            not (path.startswith("mozilla/") or
                 path.startswith("unicode/") or
                 path.startswith("devtools/") or
                 path.startswith("pr") or
                 path.startswith("ICU4X") or
                 path.endswith("Generated.h") or
                 path.endswith(".out.h") or
                 path.endswith("javascript-trace.h") or
                 path.endswith("double-conversion.h") or
                 path.endswith("Opcodes.h") or
                 path.endswith("ProfilingCategoryList.h") or
                 "arm" in path or
                 "mips" in path or
                 "generated" in path or
                 path in ["js-config.h",
                          "fdlibm.h",
                          "ffi.h",
                          "Instruments.h",
                          "sharkctl.h",
                          "gdb-tests.h",
                          "VMPI.h",
                          "vprof.h",
                          "mozmemory.h",
                          "unix.h",
                          "os9.h",
                          "dtoa.c",
                          "jscustomallocator.h",
                          "FuzzerDefs.h",
                          "FuzzingInterface.h",
                          "diplomat_runtime.h"
                          ]))

def mapInclude(path):
    if path.startswith("js/"):
        return re.sub("^js/", "public/", path)
    return "src/" + path

cachedFileInfo = {}

def readFileInfo(path):
    assert path not in cachedFileInfo
    if not os.path.exists(path):
        sys.exit("File not found: " + path)

    lineCount = 0
    includes = []
    with open(path, "r") as file:
        for line in file:
            lineCount += 1
            match = IncludeRe.match(line)
            if not match:
                continue
            include = match.group(1)
            if shouldProcessInclude(include):
                includes.append(mapInclude(include))

    cachedFileInfo[path] = [lineCount, includes]

def getLineCount(path):
    if path not in cachedFileInfo:
        readFileInfo(path)
    return cachedFileInfo[path][0]

def getIncludes(path):
    if path not in cachedFileInfo:
        readFileInfo(path)
    return cachedFileInfo[path][1]

inclusionMap = None

def buildInclusionMap():
    global inclusionMap

    assert not inclusionMap
    inclusionMap = {}

    headers = findAllHeaderFiles()
    for path in headers:
        inclusionMap[path] = []

    sources = findAllCppFiles()
    for path in headers + sources:
        includes = getIncludes(path)
        for include in includes:
            inclusionMap[include].append(path)

def getInclusions(path):
    if not inclusionMap:
        buildInclusionMap()

    return inclusionMap[path]
