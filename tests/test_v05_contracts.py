import tempfile,unittest
from pathlib import Path
from gar_ai.contracts import ContractProbeRecord,ContractProbeRegistry,SchemaVersionError,require_compatible
class T(unittest.TestCase):
 def test_major(self):
  require_compatible('1.9','1.1',name='x')
  with self.assertRaises(SchemaVersionError):require_compatible('2.0','1.1',name='x')
 def test_probe_version_key(self):
  with tempfile.TemporaryDirectory() as td:
   r=ContractProbeRegistry(Path(td)/'p.json');r.record(ContractProbeRecord('place','2.0','b1','mods','pass',{}));r.assert_passed('place',game_version='2.0',bridge_version='b1',mod_set_hash='mods')
   with self.assertRaises(RuntimeError):r.assert_passed('place',game_version='2.1',bridge_version='b1',mod_set_hash='mods')
