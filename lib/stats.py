# -*- coding: utf-8 -*-

# Caclulate some basic statistics on a list of samples.

import math

class Stats:
    def __init__(self, results, compareTo = None):
        self.count = len(results)
        self.mean, self.stdv = Stats.meanstdv(results)
        if self.mean:
            self.cofv = self.stdv / self.mean
        else:
            self.cofv = 0
        self.min = min(results)
        self.max = max(results)
        self.samples = results

        self.diff = None
        if compareTo:
            self.diff = (self.mean - compareTo) / compareTo

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
