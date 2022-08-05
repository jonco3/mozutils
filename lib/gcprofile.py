# gcprofile
#
# Summarise GC profiling information from log data.

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

    summariseAllData(result, majorFields, majorData, minorFields, minorData)
    if testCount != 0:
        summariseAllDataByInTest(result, majorFields, majorData, minorFields, minorData, True)

    if len(majorData) > 0:
        first = majorData[0]
        result['First major GC'] = float(first[majorFields.get('Timestamp')])
        result['Heap size / KB at first major GC'] = int(first[majorFields.get('SizeKB')])

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
    majorFields = dict()
    majorData = list()
    minorFields = dict()
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
            line = line[:76] + line[83:] # remove optional budget field
            line = line[:55] + line[69:] # remove other annoying to parse fields

            fields = line.split()
            if 'PID' in fields:
                if not majorFields:
                    majorFields = makeFieldMap(fields)
                continue

            if 'TOTALS:' in fields:
                continue

            fields.append(testNum)
            if len(fields) != len(majorFields):
                # todo: this would skip lines without budget (including
                # non-incremental slices) if we didn't strip that field
                # above
                continue

            majorData.append(fields)
            continue

        if 'MinorGC:' in line:
            fields = line.split('MinorGC: ', maxsplit=1)[1].split()
            if 'PID' in fields:
                if not minorFields:
                    minorFields = makeFieldMap(fields)
                continue

            if 'TOTALS:' in fields:
                continue

            fields.append(testNum)
            if len(fields) != len(minorFields):
                continue

            minorData.append(fields)
            continue

    assert len(minorData) != 0 or len(majorData) != 0, "No profile data present"

    return majorFields, majorData, minorFields, minorData, testCount

def makeFieldMap(fields):
    # Add our generated fields:
    fields.append('testNum')

    fieldMap = dict()
    for i in range(len(fields)):
        fieldMap[fields[i]] = i

    # Assumed by findMostActiveRuntime
    assert fieldMap.get('PID') == 0
    assert fieldMap.get('Runtime') == 1

    return fieldMap

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
