"""Keep captured client layout while applying persistent database changes."""
from collections import defaultdict


def identity(item):
    key, values = item
    return key, values[0]


def compatible_value(value, template):
    # JSON round-trips through PostgreSQL may turn integral floats into integers.
    if isinstance(template, float) and isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list) and isinstance(template, list):
        return [compatible_value(v, template[i]) if i < len(template) else v
                for i, v in enumerate(value)]
    return value


def merge_account(original, baseline, current):
    """Apply DB deltas onto the original wire layout, retaining order and null markers.

    Duplicate union/id pairs are matched by occurrence, as in the captured array.
    Never interpret IDs globally across entity types. New/deleted rows are reflected.
    """
    def indexed(items):
        counts = defaultdict(int)
        result = {}
        for item in items:
            if item is None:
                continue
            key = identity(item)
            occurrence = counts[key]
            counts[key] += 1
            result[key + (occurrence,)] = item
        return result

    old = indexed(baseline)
    live = indexed(current)
    positions = defaultdict(int)
    result = []
    used = set()
    for item in original:
        if item is None:
            result.append(None)
            continue
        key = identity(item)
        occurrence = positions[key]
        positions[key] += 1
        full_key = key + (occurrence,)
        if full_key not in live:
            continue
        used.add(full_key)
        _, source = item
        _, now = live[full_key]
        prior = old.get(full_key)
        if prior is None:
            result.append(live[full_key])
            continue
        prior = prior[1]
        values = list(source)
        for i, value in enumerate(now):
            if i >= len(prior) or value != prior[i]:
                while len(values) <= i:
                    values.append(None)
                values[i] = compatible_value(value, source[i]) if i < len(source) else value
        result.append([item[0], values])
    result.extend(item for key, item in live.items() if key not in used)
    return result
