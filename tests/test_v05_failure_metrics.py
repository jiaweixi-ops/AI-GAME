import unittest
from gar_ai.failure_fingerprint import *
from gar_ai.metrics import *
class C:
 def __init__(self):self.t=1000
 def __call__(self):return self.t
class T(unittest.TestCase):
 def test_failure_guard(self):
  env={'blocked':True};f=FailureFingerprint.build(task_id='t',task_type='smelt',tool='place',target='f',position=[1,2],environment=env,reason_code='COLLISION');s=FailureFingerprintStore();s.record(f);s.mark_recovery(f.fingerprint,{'shift':2});self.assertTrue(s.should_reject_recovery(f.fingerprint,{'shift':2},current_environment=env));self.assertFalse(s.should_reject_recovery(f.fingerprint,{'shift':2},current_environment={'blocked':False}))
 def test_metrics(self):
  c=C();m=MetricsRecorder(clock=c);m.record_progress(ProgressKind.ENTITY);m.record_ai_call(cost=.1);m.record_keeper_runtime(10);c.t+=3600;r=m.report();self.assertAlmostEqual(r['Progress Rate'],1);self.assertAlmostEqual(r['AI Cost / Game Hour'],.1);self.assertEqual(r['Keeper Zero-Token Ratio'],1)
