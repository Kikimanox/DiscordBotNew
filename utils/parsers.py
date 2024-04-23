import re

TIME_UNITS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def time_string_to_seconds(length):
    match = re.findall("([0-9]+[smhd])", length)  # Thanks to 3dshax server's former bot
    return (
        sum([int(item[:-1]) * TIME_UNITS[item[-1]] for item in match])
        if match
        else None
    )


def time_seconds_to_string(length):
    time_units = {}
    for unit, seconds in TIME_UNITS.items():
        if length // seconds:
            time_units[unit] = length // seconds
            length -= seconds * (length // seconds)
    return "".join([f"{magnitude}{unit}" for unit, magnitude in time_units.items()])
