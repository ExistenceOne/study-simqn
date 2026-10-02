"""예제에서 공통으로 사용하는 argparse 숫자 검증."""

import argparse
import math


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수가 필요함")
    return number


def seed_value(value):
    number = int(value)
    if not 0 <= number <= 2**32 - 1:
        raise argparse.ArgumentTypeError("seed는 0부터 4294967295까지 가능함")
    return number


def nonnegative_float(value):
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise argparse.ArgumentTypeError("0 이상의 유한한 숫자가 필요함")
    return number


def positive_float(value):
    number = nonnegative_float(value)
    if number == 0:
        raise argparse.ArgumentTypeError("0보다 큰 숫자가 필요함")
    return number


def probability(value):
    number = nonnegative_float(value)
    if number > 1:
        raise argparse.ArgumentTypeError("확률은 0부터 1까지 가능함")
    return number
