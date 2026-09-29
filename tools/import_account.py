"""Convert preserved protocol arrays into typed database rows."""
import msgpack
from helpers.user_data import _camel
from models.keys import KEYS

def row_dict(name, values):
    def convert(base, array, kind, value):
        if value is None:
            return None
        if array:
            return [convert(base, False, kind, v) for v in value]
        if base == 'DateTime' and isinstance(value, msgpack.Timestamp):
            return value.seconds * 1000000 + value.nanoseconds // 1000
        if kind == 'model' and isinstance(value, list):
            return row_dict(base, value)
        return value
    return {_camel(attr): convert(base, array, kind, values[index])
            for index, attr, base, array, kind, nullable in KEYS[name]
            if index < len(values)}

