import importlib.util
import pathlib
import types
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('egress', pathlib.Path(__file__).resolve().parents[1] / 'ops' / 'nas' / 'forecast_egress.py')
egress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(egress)
class EgressTests(unittest.TestCase):
 def test_restrictive_rules(self):
  rules = egress.rules(); self.assertEqual(len(rules),3)
  for rule in rules:
   self.assertIn('172.28.0.2/32',rule); self.assertIn(egress.BRIDGE,rule); self.assertIn(egress.WAN,rule)
   self.assertEqual(rule[-1],'RETURN'); self.assertNotIn('ACCEPT',rule)
   self.assertNotIn('comment',rule); self.assertEqual(rule.count('-m'),1)
  self.assertEqual({(r[r.index('-p')+1],r[r.index('--dport')+1]) for r in rules},{('tcp','443'),('tcp','53'),('udp','53')})
 def test_idempotent(self):
  calls=[]
  def run(args,check=True): calls.append(args); return types.SimpleNamespace(returncode=0)
  with patch.object(egress,'ownership',return_value=True),patch.object(egress.os,'geteuid',return_value=0),patch.object(egress,'authenticate'),patch.object(egress,'run',run): egress.reconcile()
  self.assertEqual(len(calls),3); self.assertTrue(all('-C'in c for c in calls))
 def test_add_only_exact_rules(self):
  calls=[]
  def run(args,check=True):
   calls.append(args);return types.SimpleNamespace(returncode=1 if '-C'in args else 0)
  with patch.object(egress,'ownership',return_value=True),patch.object(egress.os,'geteuid',return_value=0),patch.object(egress,'authenticate'),patch.object(egress,'run',run):egress.reconcile()
  writes=[c for c in calls if '-I'in c];self.assertEqual(len(writes),3)
  for c,rule in zip(writes,egress.rules()):self.assertEqual(c,[egress.IPTABLES,'-I',egress.CHAIN,'1']+rule)
 def test_remove_only_exact_rules(self):
  calls=[]
  def run(args,check=True):
   calls.append(args); return types.SimpleNamespace(returncode=0 if '-D' in args or len([c for c in calls if c==args])==1 else 1)
  with patch.object(egress,'ownership',return_value=True),patch.object(egress.os,'geteuid',return_value=0),patch.object(egress,'authenticate'),patch.object(egress,'run',run):egress.reconcile(True)
  self.assertEqual([c for c in calls if '-D'in c],[[egress.IPTABLES,'-D',egress.CHAIN]+r for r in egress.rules()])
 def test_identity_failure_no_mutation(self):
  calls=[]
  def run(args,check=True):
   calls.append(args);return types.SimpleNamespace(returncode=0 if '-D' in args or len([c for c in calls if c==args])==1 else 1)
  with patch.object(egress,'ownership',return_value=True),patch.object(egress.os,'geteuid',return_value=0),patch.object(egress,'authenticate',side_effect=RuntimeError),patch.object(egress,'run',run):
   with self.assertRaises(RuntimeError):egress.reconcile()
  self.assertFalse(any('-I' in c for c in calls))
  self.assertEqual([c for c in calls if '-D' in c],[[egress.IPTABLES,'-D',egress.CHAIN]+r for r in egress.rules()])
 def test_duplicates_all_removed(self):
  counts={tuple(r):3 for r in egress.rules()}; calls=[]
  def run(args,check=True):
   calls.append(args); rule=tuple(args[3:])
   if '-D' in args:counts[rule]-=1;return types.SimpleNamespace(returncode=0)
   return types.SimpleNamespace(returncode=0 if counts[rule] else 1)
  with patch.object(egress,'ownership',return_value=True),patch.object(egress.os,'geteuid',return_value=0),patch.object(egress,'run',run):egress.reconcile(True)
  self.assertTrue(all(v==0 for v in counts.values()));self.assertEqual(sum('-D' in c for c in calls),9)
 def test_cron_removal_does_not_authenticate_runtime(self):
  with patch.object(egress,'ownership',return_value=True),patch.object(egress.os,'geteuid',return_value=0),patch.object(egress,'authenticate') as auth,patch.object(egress,'secure_path'),patch.object(egress.Path,'resolve',return_value=egress.DEPLOYED),patch.object(egress.Path,'exists',return_value=False),patch.object(egress.Path,'is_symlink',return_value=False):
   egress.cron_install(True)
   auth.assert_not_called()
 def test_unowned_rules_never_removed(self):
  with patch.object(egress,'ownership',return_value=False),patch.object(egress.os,'geteuid',return_value=0),patch.object(egress,'run') as run:
   egress.reconcile(True)
   run.assert_not_called()
 def test_canonical_second_admission(self):
  baseline='-N FORWARD_FIREWALL\n-A FORWARD_FIREWALL -j DROP\n'
  canonical=[]
  for protocol,port in [('tcp','443'),('udp','53'),('tcp','53')]:
   canonical.append('-A FORWARD_FIREWALL -s 172.28.0.2/32 -i docker-452efc88 -o ovs_eth0 -p '+protocol+' -m '+protocol+' --dport '+port+' -j RETURN\n')
  policy=baseline+''.join(canonical)
  def inspect(kind,ident,template):
   if '{{.Id}} {{.Internal}}'==template:return egress.NETWORK+' false'
   if '{{json .Containers}}'==template:return egress.json.dumps({egress.CONTAINER:{'IPv4Address':'172.28.0.2/16'}})
   if 'source-tree' in template:return 'a8ac6e20d74d7b0e1b39a36ed21ce947b220fbe7 5b203057454d6e066caf3e2f7b625f5cb2753a58 lakehouse-weather forecast'
   return {'{{.Id}}':egress.CONTAINER,'{{.Image}}':egress.IMAGE,'{{.State.Running}}':'true'}[template]
  writes=[]
  def run(args,check=True):
   if '-I' in args or '-D' in args:writes.append(args)
   return types.SimpleNamespace(returncode=0,stdout=policy if '-S'in args else '1.1.1.1 via 10.0.0.1 dev ovs_eth0')
  with patch.object(egress.os,'geteuid',return_value=0),patch.object(egress,'ownership',return_value=True),patch.object(egress,'inspect',inspect),patch.object(egress,'run',run),patch.object(egress,'BASELINE_SHA',egress.hashlib.sha256(baseline.encode()).hexdigest()):
   egress.reconcile()
  self.assertFalse(writes)
 def test_fingerprint_rejects_extra_or_duplicate_fields(self):
  tokens=['-A',egress.CHAIN]+egress.rules()[0]
  self.assertNotEqual(egress.fingerprint(tokens),egress.fingerprint(tokens+['-m','comment']))
  self.assertIsNone(egress.fingerprint(tokens+['-s',egress.SOURCE]))
 def test_commands_are_bounded(self):
  with patch.object(egress.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)) as run:
   egress.run(['/bin/true'])
   self.assertEqual(run.call_args.kwargs['timeout'],15)
 def test_dedicated_cron(self):
  self.assertEqual(str(egress.CRON),'/etc/cron.d/weather-forecast-egress')
  self.assertIn('/usr/bin/python3 -I ',egress.CRON_CONTENT)
  self.assertNotIn('/etc/crontab',egress.CRON_CONTENT)
if __name__=='__main__':unittest.main()
