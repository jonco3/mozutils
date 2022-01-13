# -*- coding: utf-8 -*-

# Format benchmark data for display.

def statsHeader():
    return "%-8s  %-8s  %-8s  %-6s  %-4s  %-8s  %-6s  %-7s" % (
        "Min", "Mean", "Max", "CofV", "Runs", "Change", "%", "P-value")

def formatStats(stats, comp = None):
    diff = "%8.1f" % comp.diff if comp else ""
    percent = "%5.1f%%" % (comp.factor * 100) if comp and comp.factor != None else ""
    pvalue = "%7.2f" % comp.pvalue if comp and comp.pvalue != None else ""

    return "%8.1f  %8.1f  %8.1f  %5.1f%%  %4d  %8s  %6s  %7s" % (
        stats.min, stats.mean, stats.max, stats.cofv * 100, stats.count, diff, percent, pvalue)

def formatBox(minAll, maxAll, stats):
    width = 40
    scale = (maxAll - minAll) / (width - 1)

    def pos(x):
        assert x >= minAll
        return int((x - minAll) // scale)

    maxDev = stats.mean + stats.stdv / 2
    minDev = stats.mean - stats.stdv / 2

    chars = list()
    for i in range(width):
        x = minAll + i * scale
        if x >= stats.max:
            c = ' '
        elif x >= maxDev:
            c = '-'
        elif x >= minDev:
            c = '='
        elif x >= stats.min:
            c = '-'
        else:
            c = ' '

        chars.append(c)

    chars[pos(stats.min)] = "|"
    chars[pos(stats.max)] = "|"
    chars[pos(stats.mean)] = "O"

    return ''.join(chars)

def formatSamples(minAll, maxAll, stats):
    width = 40
    scale = (maxAll - minAll) / (width - 1)

    def pos(x):
        assert x >= minAll
        return int((x - minAll) // scale)

    chars = [' '] * width
    for x in stats.samples:
        chars[pos(x)] = 'x' if chars[pos(x)] == ' ' else 'X'

    return ''.join(chars)

