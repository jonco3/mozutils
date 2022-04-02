# -*- coding: utf-8 -*-

# A clearable display.

import ansi.cursor

class Null:
    def print(self, text=''):
        pass
    def clear(self):
        pass

class Terminal:
    def __init__(self):
        self.linesDisplayed = 0

    def print(self, text=''):
        print(text)
        self.linesDisplayed += 1

    def clear(self):
        for i in range(self.linesDisplayed):
            print(ansi.cursor.up() + ansi.cursor.erase_line(), end='')
        self.linesDisplayed = 0

class File:
    def __init__(self, file):
        self.file = file

    def print(self, text=''):
        self.file.write(text + "\n")

    def clear(self):
        pass
