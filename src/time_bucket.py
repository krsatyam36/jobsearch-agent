import re


def parse_time_string(time_str: str) -> int:
    time_str = time_str.strip().lower()

    match = re.search(r"(\d+)\s*minute", time_str)
    if match:
        return int(match.group(1))

    match = re.search(r"(\d+)\s*hour", time_str)
    if match:
        return int(match.group(1)) * 60

    match = re.search(r"(\d+)\s*day", time_str)
    if match:
        return int(match.group(1)) * 1440

    match = re.search(r"(\d+)\s*week", time_str)
    if match:
        return int(match.group(1)) * 10080

    match = re.search(r"(\d+)\s*month", time_str)
    if match:
        return int(match.group(1)) * 43200

    return 999999


def assign_bucket(minutes: int, buckets: list[tuple[str, int]]) -> str:
    for label, threshold in buckets:
        if minutes <= threshold:
            return label
    return ">24h"
