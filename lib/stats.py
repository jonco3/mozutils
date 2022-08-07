# -*- coding: utf-8 -*-

# Caclulate some basic statistics on a list of samples.

import math
from scipy import stats

class Stats:
    def __init__(self, results):
        self.count = len(results)
        self.mean, self.stdv = Stats.meanstdv(results)
        if self.mean:
            self.cofv = self.stdv / self.mean
        else:
            self.cofv = 0
        self.min = min(results)
        self.max = max(results)
        self.samples = results

    def meanstdv(x):
        assert(isinstance(x, list))

        # from http://www.physics.rutgers.edu/~masud/computing/WPark_recipes_in_python.html
        n, mean, std = len(x), 0, 0
        for a in x:
            mean = mean + a
        mean = mean / float(n)
        for a in x:
            std = std + (a - mean) ** 2
        if n > 1:
            std = math.sqrt(std / float(n - 1))
        else:
            std = 0.0
        return mean, std

    def compareTo(self, other):
        return compareStats(self, other)

class Comparison:
    def __init__(self, diff, factor, pvalue):
        self.diff = diff
        self.factor = factor
        self.pvalue = pvalue

def compareStats(a, b):
    if b is None or a is b:
        return None

    assert isinstance(a, Stats)
    assert isinstance(b, Stats)

    diff = a.mean - b.mean

    if b.mean == 0:
        factor = None
    else:
        factor = diff / b.mean

    if a.count > 1 and b.count > 1 and a.mean != b.mean:
        p = stats.ttest_ind(a.samples, b.samples, equal_var=False).pvalue
    else:
        p = None

    return Comparison(diff, factor, p)
