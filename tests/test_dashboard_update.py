import importlib.util
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
PATH = Path(__file__).resolve().parents[1] / 'ops/nas/update_dashboard.py'
spec=importlib.util.spec_from_file_location('update',PATH)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class UpdateTests(unittest.TestCase):
 def test_only_dashboard_no_dependencies_or_pull(self):
  commands=[]
  def run(args,**kwargs): commands.append((args,kwargs));return types.SimpleNamespace(returncode=0)
  def field(kind,target,template):return 'healthy' if 'Health' in template else 'newimage'
  with patch.object(m.subprocess,'run',run),patch.object(m.runtime,'field',field),patch.object(m,'forecast_identity'):
   m.compose('newimage')
  args,kwargs=commands[0]; self.assertEqual(args[-1],'dashboard');self.assertIn('--no-deps',args);self.assertEqual(args[args.index('--pull')+1],'never');self.assertEqual(kwargs['timeout'],120)
  self.assertNotIn('forecast',args)
 def test_forecast_drift_blocks_before_compose(self):
  args=['--image-id','newimage','--reviewed-head','a'*40,'--reviewed-tree','b'*40,'--expected-dashboard-id','c'*64,'--expected-old-image','oldimage','--apply']
  with patch.object(m.os,'geteuid',return_value=0),patch.object(m.runtime,'identity'),patch.object(m,'forecast_identity',side_effect=ValueError),patch.object(m,'compose') as compose:
   with self.assertRaises(ValueError):m.main(args)
   compose.assert_not_called()
 def test_failed_update_restores_old_image_only(self):
  args=['--image-id','newimage','--reviewed-head','a'*40,'--reviewed-tree','b'*40,'--expected-dashboard-id','c'*64,'--expected-old-image','oldimage','--apply']
  def field(kind,target,t):
   if t=='{{.Id}} {{.Image}}':return 'c'*64+' oldimage'
   return 'dashboard' if 'service' in t else 'lakehouse-weather'
  with tempfile.TemporaryDirectory() as d,patch.object(m,'BASE',Path(d)),patch.object(m.os,'geteuid',return_value=0),patch.object(m.runtime,'identity'),patch.object(m.runtime,'field',field),patch.object(m,'forecast_identity'),patch.object(m,'compose',side_effect=[ValueError,None]) as compose:
   with self.assertRaisesRegex(ValueError,'prior image restored'):m.main(args)
   self.assertEqual([v.args[0] for v in compose.call_args_list],['newimage','oldimage'])
 def test_docker_guard_bounded(self):
  with patch.object(m.subprocess,'run',return_value=types.SimpleNamespace(returncode=0,stdout='ok')) as run:
   self.assertEqual(m.bounded_docker('version'),'ok');self.assertEqual(run.call_args.kwargs['timeout'],15)
if __name__=='__main__':unittest.main()
