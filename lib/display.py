# -*- coding: utf-8 -*-

# A clearable display.

import ansi.cursor

linesDisplayed = 0

def display(text=''):
    global linesDisplayed

    print(text)
    linesDisplayed += 1

def clearDisplay():
    global linesDisplayed

    for i in range(linesDisplayed):
        print(ansi.cursor.up() + ansi.cursor.erase_line(), end='')

    linesDisplayed = 0

