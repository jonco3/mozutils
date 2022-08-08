# gcprofile
#
# Summarise GC profiling information from log data.

import re

# Detect whether we're currently running a raptor test, or between
# tests.
StartTestText = 'Testing url'
EndTestText = 'PageCompleteCheck returned true'

def summariseProfile(text, result, filterMostActiveRuntime = True):
    majorFields, majorData, minorFields, minorData, testCount = parseOutput(text)

    if filterMostActiveRuntime:
        runtime = findMostActiveRuntimeByFrequency(majorData + minorData)
        majorData = filterByRuntime(majorData, runtime)
        minorData = filterByRuntime(minorData, runtime)

    countMajorGCs(result, majorFields, majorData)

    summariseAllData(result, majorFields, majorData, minorFields, minorData)
    if testCount != 0:
        summariseAllDataByInTest(result, majorFields, majorData, minorFields, minorData, True)

    findFirstMajorGC(result, majorFields, majorData)

def findFirstMajorGC(result, majorFields, majorData):
    timestampField = majorFields.get('Timestamp')
    sizeField = majorFields.get('SizeKB')
    timeField = majorFields.get('total')
    statesField = majorFields.get('States')

    for line in majorData:
        # Skip collections where we don't collect anything.
        if int(line[timeField]) == 0 and line[statesField] == "0 -> 0":
            continue

        result['First major GC'] = float(line[timestampField])
        result['Heap size / KB at first major GC'] = int(line[sizeField])

def countMajorGCs(result, majorFields, majorData):
    statesField = majorFields.get('States')
    reasonField = majorFields.get('Reason')

    count = 0
    for line in majorData:
        if "0 ->" in line[statesField] and not isShutdownReason(line[reasonField]):
            count += 1

    result['Major GC count'] = count

def isShutdownReason(reason):
    return 'SHUTDOWN' in reason or 'DESTROY' in reason or reason == 'ROOTS_REMOVED'

def extractHeapSizeData(text):
    majorFields, majorData, _, _, _ = parseOutput(text)

    pidField = majorFields.get('PID')
    runtimeField = majorFields.get('Runtime')
    timestampField = majorFields.get('Timestamp')
    sizeField = majorFields.get('SizeKB')
    assert pidField is not None
    assert runtimeField is not None
    assert sizeField is not None

    runtimes = dict()

    # Estimate global time from times in previous traces.
    latestTimestamp = None
    startTimes = dict()

    for line in majorData:
        key = (line[pidField], line[runtimeField])
        timestamp = float(line[timestampField])
        size = int(line[sizeField])

        if key not in runtimes:
            runtimes[key] = list()
            if latestTimestamp is None:
                startTimes[key] = 0
                latestTimestamp = timestamp
            else:
                startTimes[key] = max(latestTimestamp - timestamp, 0)
            runtimes[key].append((startTimes[key], 0))

        timestamp += startTimes[key]
        latestTimestamp = timestamp

        runtimes[key].append((timestamp, size))

    return runtimes

def parseOutput(text):
    majorFields = None
    majorSpans = None
    majorData = list()
    minorFields = None
    minorSpans = None
    minorData = list()

    inTest = False
    testCount = 0
    testNum = 0

    for line in text.splitlines():
        if StartTestText in line:
            assert not inTest
            inTest = True
            testCount += 1
            testNum = testCount
            continue

        if inTest and EndTestText in line:
            inTest = False
            testNum = 0
            continue

        if 'MajorGC:' in line:
            line = line.split('MajorGC: ', maxsplit=1)[1]

            if 'TOTALS:' in line:
                continue
            elif line.startswith('PID'):
                if not majorFields:
                    majorFields, majorSpans = parseHeaderLine(line)
                continue
            else:
                fields = splitWithSpans(line, majorSpans)

            fields.append(testNum)
            if len(fields) != len(majorFields):
                print("Skipping garbled profile line")
                continue

            majorData.append(fields)
            continue

        if 'MinorGC:' in line:
            line = line.split('MinorGC: ', maxsplit=1)[1]

            if 'TOTALS:' in line:
                continue
            elif line.startswith('PID'):
                if not minorFields:
                    minorFields, minorSpans = parseHeaderLine(line)
                continue
            else:
                fields = splitWithSpans(line, minorSpans)

            fields.append(testNum)
            if len(fields) != len(minorFields):
                print("Skipping garbled profile line")
                continue

            minorData.append(fields)
            continue

    assert len(minorData) != 0 or len(majorData) != 0, "No profile data present"

    return majorFields, majorData, minorFields, minorData, testCount

def parseHeaderLine(line):
    fieldMap = dict()
    fieldSpans = list()

    for match in re.finditer(r"(\w+)\s*", line):
        name = match.group(1)
        span = match.span()
        fieldMap[name] = len(fieldMap)
        fieldSpans.append(span)

    # Assumed by findMostActiveRuntime
    assert fieldMap.get('PID') == 0
    assert fieldMap.get('Runtime') == 1

    # Add our generated field:
    fieldMap['testNum'] = len(fieldMap)

    return fieldMap, fieldSpans

def splitWithSpans(line, spans):
    fields = []
    for span in spans:
        field = line[span[0]:span[1]].strip()
        fields.append(field)

    return fields

def summariseAllDataByInTest(result, majorFields, majorData, minorFields, minorData, inTest):
    majorData = filterByInTest(majorFields, majorData, inTest)
    minorData = filterByInTest(minorFields, minorData, inTest)

    suffix = ' in test' if inTest else ' outside test'

    summariseAllData(result, majorFields, majorData, minorFields, minorData, suffix)

def summariseAllData(result, majorFields, majorData, minorFields, minorData, keySuffix = ''):
    summariseMajorMinorData(result, majorFields, majorData, minorFields, minorData, keySuffix)

    result['Max heap size / KB' + keySuffix] = findMax(majorFields, majorData, 'SizeKB')

    result['ALLOC_TRIGGER slices' + keySuffix] = \
        len(filterByReason(majorFields, majorData, 'ALLOC_TRIGGER'))

    result['TOO_MUCH_MALLOC slices' + keySuffix] = \
        len(filterByReason(majorFields, majorData, 'TOO_MUCH_MALLOC'))

    result['Full store buffer nursery collections' + keySuffix] = \
        len(filterByFullStoreBufferReason(minorFields, minorData))

    result['Mean full nusery promotion rate' + keySuffix] = \
        meanPromotionRate(minorFields, filterByReason(minorFields, minorData, 'OUT_OF_NURSERY'))

def summariseMajorMinorData(result, majorFields, majorData, minorFields, minorData, keySuffix):
    majorCount, majorTime = summariseData(majorFields, majorData)
    minorCount, minorTime = summariseData(minorFields, minorData)
    minorTime /= 1000
    totalTime = majorTime + minorTime
    result['Major GC slices' + keySuffix] = majorCount
    result['Major GC time' + keySuffix] = majorTime
    result['Minor GC count' + keySuffix] = minorCount
    result['Minor GC time' + keySuffix] = minorTime
    result['Total GC time' + keySuffix] = majorTime + minorTime

def summariseData(fieldMap, data):
    count = 0
    totalTime = 0
    for fields in data:
        count += 1
        time = int(fields[fieldMap['total']])
        totalTime += time
    return count, totalTime

# Work out which runtime we're interested in. This is a heuristic that
# may not always work.
def findMostActiveRuntimeByFrequency(data):
    lineCount = dict()
    for fields in data:
        runtime = (fields[0], fields[1])

        if runtime not in lineCount:
            lineCount[runtime] = 0

        lineCount[runtime] += 1

    mostActive = None
    maxCount = 0
    for runtime in lineCount:
        if lineCount[runtime] > maxCount:
            mostActive = runtime
            maxCount = lineCount[runtime]

    assert mostActive
    return mostActive

def filterByRuntime(data, runtime):
    return list(filter(lambda f: f[0] == runtime[0] and f[1] == runtime[1], data))

def filterByInTest(fields, data, inTest):
    i = fields['testNum']
    return list(filter(lambda f: (f[i] != 0) == inTest, data))

def filterByReason(fields, data, reason):
    i = fields['Reason']
    return list(filter(lambda f: f[i] == reason, data))

def filterByFullStoreBufferReason(fields, data):
    i = fields['Reason']
    return list(filter(lambda f: f[i].startswith('FULL') and f[i].endswith('BUFFER'), data))

def meanPromotionRate(fields, data):
    if len(data) == 0:
        return 0

    i = fields['PRate']
    sum = 0
    for line in data:
        rate = line[i]
        ensure(rate.endswith('%'), "Bad promotion rate" + rate)
        rate = float(rate[:-1])
        sum += rate

    return sum / len(data)

def findMax(fields, data, key):
    i = fields[key]
    result = 0

    for line in data:
        result = max(result, int(line[i]))

    return result

def ensure(condition, error):
    if not condition:
        sys.exit(error)
