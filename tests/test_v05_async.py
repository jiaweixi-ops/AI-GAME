import unittest
from gar_ai.async_verify import *
class C:
 def __init__(self):self.t=0
 def __call__(self):return self.t
class T(unittest.TestCase):
 def test_pending_verified(self):
  c=C();s={'n':0};v=AsyncVerifier(lambda:dict(s),clock=c);p=v.start(AsyncVerificationSpec('x',10,1,2));v.poll_once(p,lambda x:(False,{}));s['n']=1;c.t=1;v.poll_once(p,lambda x:(True,{}));self.assertEqual(p.status,AsyncVerificationStatus.PENDING);c.t=2;v.poll_once(p,lambda x:(True,{}));self.assertEqual(p.status,AsyncVerificationStatus.VERIFIED)
 def test_timeout(self):
  c=C();v=AsyncVerifier(lambda:{},clock=c);p=v.start(AsyncVerificationSpec('x',2,0,1));c.t=3;v.poll_once(p,lambda x:(False,{}));self.assertEqual(p.status,AsyncVerificationStatus.TIMEOUT)
