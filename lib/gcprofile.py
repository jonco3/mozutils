# gcprofile
#
# Summarise GC profiling information from log data.

def parseOutput(text, result):
    majorFields = dict()
    majorData = list()
    minorFields = dict()
    minorData = list()

    for line in text.splitlines():
        if 'MajorGC:' in line:
            line = line.split('MajorGC: ', maxsplit=1)[1]
            line = line[:54] + line[75:] # remove annoying to parse fields
            fields = line.split()
            if 'PID' in fields:
                majorFields = makeFieldMap(fields)
                continue

            if 'TOTALS:' in fields:
                continue

            majorData.append(fields)
            continue

        if 'MinorGC:' in line:
            fields = line.split('MinorGC: ', maxsplit=1)[1].split()
            if 'PID' in fields:
                minorFields = makeFieldMap(fields)
                continue

            if 'TOTALS:' in fields:
                continue

            minorData.append(fields)
            continue

    summariseAllData(result, majorFields, majorData, minorFields, minorData)

def makeFieldMap(fields):
    # Add our generated fields:
    fields.append('testNum')

    fieldMap = dict()
    for i in range(len(fields)):
        fieldMap[fields[i]] = i

    # Assumed by findMainRuntime
    assert fieldMap.get('PID') == 0
    assert fieldMap.get('Runtime') == 1

    return fieldMap

def summariseAllData(result, majorFields, majorData, minorFields, minorData):
    mainRuntime = findMainRuntime(majorData + minorData)

    majorData = filterByRuntime(majorData, mainRuntime)
    minorData = filterByRuntime(minorData, mainRuntime)
    summariseMajorMinorData(result, majorFields, majorData, minorFields, minorData)

    result['ALLOC_TRIGGER slices'] = \
        len(filterByReason(majorFields, majorData, 'ALLOC_TRIGGER'))

    result['Full store buffer collections'] = \
        len(filterByFullStoreBufferReason(minorFields, minorData))

def summariseMajorMinorData(result, majorFields, majorData, minorFields, minorData):
    majorCount, majorTime = summariseData(majorFields, majorData)
    minorCount, minorTime = summariseData(minorFields, minorData)
    minorTime /= 1000
    totalTime = majorTime + minorTime
    result['Major GC slices'] = majorCount
    result['Major GC time'] = majorTime
    result['Minor GC count'] = minorCount
    result['Minor GC time'] = minorTime
    result['Total GC time'] = majorTime + minorTime

def summariseData(fieldMap, data):
    count = 0
    totalTime = 0
    for fields in data:
        count += 1
        time = int(fields[fieldMap['total']])
        totalTime += time
    return count, totalTime

def findMainRuntime(data):
    lineCount = dict()
    for fields in data:
        runtime = (fields[0], fields[1])
        if runtime not in lineCount:
            lineCount[runtime] = 0
        lineCount[runtime] += 1

    mostFrequent = None
    count = 0
    for runtime in lineCount:
        if lineCount[runtime] > count:
            mostFrequent = runtime
            count = lineCount[runtime]

    assert mostFrequent
    return mostFrequent

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

def ensure(condition, error):
    if not condition:
        sys.exit(error)
