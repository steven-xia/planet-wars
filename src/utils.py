"""
file: utils.py

description: contains general utility definitions.
"""


import math
import sys


# set a large number for utility purposes
INFINITY = 1 << 32


def distance(x1, y1, x2, y2):
    """
    find the euclidean distance between two points (x1, y1) and (x2, y2).
    :param x1: `float` x-value of first point
    :param y1: `float` y-value of first point
    :param x2: `float` x-value of second point
    :param y2: `float` y-value of second point
    :return: `float` the euclidean distance between the two points
    """

    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def error_print(*args, **kwargs):
    """
    `print()` wrapper to print to `sys.stderr` for logging. the game engine
    captures all stdout but allows stderr to pass through.
    :param args: *args to pass to `print()`
    :param kwargs: **kwargs to pass to `print()`
    :return: `None`
    """

    print(*args, file=sys.stderr, **kwargs)
