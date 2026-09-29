"""Extend final-service content windows without changing the archived master DB."""
from functools import lru_cache
from pathlib import Path
import hashlib
import msgpack
from helpers.mastermemory import unpack,pack
from models.keys import KEYS
ROOT=Path(__file__).resolve().parents[1]
# Recovered master contains both clock representations at the service boundary.
BOUNDARIES={1790658000,1790690400}
END=4102444800  # 2100-01-01; game already uses this sentinel for permanent charts.

def extend_row(name,row,changes):
    if not isinstance(row,list):return
    for k,field,base,array,kind,*_ in KEYS.get(name,()):
        if k>=len(row):continue
        value=row[k]
        if base=='DateTime' and 'end' in field and isinstance(value,msgpack.Timestamp) and value.seconds in BOUNDARIES:
            row[k]=msgpack.Timestamp(END,value.nanoseconds);changes.append((name,row[0],field))
        elif kind=='model' and value is not None:
            for child in value if array else [value]:extend_row(base,child,changes)

@lru_cache(maxsize=1)
def preserved_master():
    tables=unpack((ROOT/'private/upstream/master-original.db').read_bytes());changes=[]
    for name,rows in tables.items():
        for row in rows:extend_row(name,row,changes)
    body=pack(tables)
    return body,hashlib.sha256(body).hexdigest()[:16],changes

def repair_cached_dates():
    from helpers.cache import cache
    from helpers.msgpack import iso_to_ts
    def walk(value):
        if isinstance(value,list):
            for x in value:walk(x)
        elif hasattr(type(value),'model_fields'):
            for field,x in list(value.__dict__.items()):
                if 'end' in field and isinstance(x,str):
                    try:
                        if iso_to_ts(x).seconds in BOUNDARIES:setattr(value,field,'2100-01-01T00:00:00Z')
                    except (ValueError,TypeError):pass
                elif isinstance(x,list) or hasattr(type(x),'model_fields'):walk(x)
    walk(cache)
