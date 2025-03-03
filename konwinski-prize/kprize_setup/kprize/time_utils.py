import time


def current_ns():
    return time.time_ns()


def current_ms():
    return round(current_ns() / 1000000)


def seconds_since(time_ms):
    return (current_ms() - time_ms) / 1000
