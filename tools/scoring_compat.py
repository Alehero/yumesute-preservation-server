"""Repair typed character stats from preserved raw master data.

Sirius Status keys are vocal=0, expression=1, concentration=2 (see the
OpenSiriusServer dto/schema.go Status definition). The upstream importer
reversed the two outer fields. LiveStatus has a distinct wire layout.
"""
from pathlib import Path
from helpers.cache import cache
from helpers.mastermemory import unpack


def repair_character_stats():
    path=Path(__file__).resolve().parents[1]/'private/upstream/master-original.db'
    if not path.exists():
        raise RuntimeError('Preserved raw master data required for scoring correction')
    rows={r[0]:r[7] for r in unpack(path.read_bytes())['CharacterMaster']}
    for m in cache.character_master:
        raw=rows.get(m.id_)
        if raw is not None and m.min_level_status is not None:
            m.min_level_status.vocal=raw[0]
            m.min_level_status.expression=raw[1]
            m.min_level_status.concentration=raw[2]
