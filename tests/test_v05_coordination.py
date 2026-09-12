import tempfile,unittest
from pathlib import Path
from gar_ai.coordination import *
class T(unittest.TestCase):
 def test_lock(self):
  with tempfile.TemporaryDirectory() as td:
   m=AreaLockManager(Path(td)/'l.json');m.acquire(lock_id='a',task_id='t1',footprint=Footprint(0,0,10,10))
   with self.assertRaises(AreaLockConflict):m.acquire(lock_id='b',task_id='t2',footprint=Footprint(5,5,12,12))
   self.assertTrue(m.release('a',task_id='t1'))
 def test_reservation_double_spend(self):
  with tempfile.TemporaryDirectory() as td:
   m=MaterialReservationManager(Path(td)/'m.json');m.reserve(reservation_id='r1',task_id='t1',requested={'f':8},available={'f':10})
   with self.assertRaises(MaterialReservationError):m.reserve(reservation_id='r2',task_id='t2',requested={'f':3},available={'f':10})
   m.consume('r1','f',5);self.assertEqual(m.release('r1')['f'],3);m.reserve(reservation_id='r2',task_id='t2',requested={'f':3},available={'f':10})
