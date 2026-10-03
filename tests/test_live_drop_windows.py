import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from live_drop_windows import frame_active

class DropWindows(unittest.TestCase):
    def test_boundaries(self):
        frame=SimpleNamespace(start_date='2026-01-01T00:00:00Z',end_date='2026-01-02T00:00:00Z')
        for date,expected in [('2025-12-31',False),('2026-01-01',True),('2026-01-02',False),('2026-10-03',False)]:
            self.assertEqual(frame_active(frame,datetime.fromisoformat(date).replace(tzinfo=timezone.utc)),expected)
    def test_permanent_and_invalid(self):
        now=datetime(2026,10,3,tzinfo=timezone.utc)
        for start,end,expected in [(None,None,True),('', '',True),('2026-10-03T01:00:00+01:00',None,True),(None,'2100-01-01T00:00:00Z',True),('bad',None,False)]:
            self.assertEqual(frame_active(SimpleNamespace(start_date=start,end_date=end),now),expected)
