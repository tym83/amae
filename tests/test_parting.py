"""Lease fencing and aggregated eviction failures through the real Amae code."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from test_amae import ROOT, run

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
p = Path(os.environ['FAKE_STATE'])
s = json.loads(p.read_text())
a = sys.argv[3:]
if a[:4] == ['-n', 'amaenetes', 'get', 'leases.coordination.k8s.io']:
    print(json.dumps(s['lease']) if s.get('lease') else '')
elif a[:2] in (['create', '--raw'], ['replace', '--raw']) and '/leases' in a[2]:
    s['lease'] = json.load(sys.stdin)
elif a[:2] == ['create', '--raw'] and a[2].endswith('/eviction'):
    s['evictions'] = s.get('evictions', 0) + 1
    p.write_text(json.dumps(s))
    sys.exit('disruption budget refuses eviction')
elif a[:2] == ['create', '--raw'] and a[2].endswith('/events'):
    s.setdefault('events', []).append(json.load(sys.stdin))
elif a[:4] == ['-n', 'shop', 'patch', 'events']:
    s['events'][0].update(json.load(sys.stdin))
else:
    sys.exit('unexpected: ' + repr(a))
p.write_text(json.dumps(s))
'''

class PartingCoordination(unittest.TestCase):
    def act(self, lease=None):
        source = Path(ROOT, 'kube/parting.amae').read_text().split('soul operator')[0] + '''soul probe
    note "live" = 1
    note "object shop/web" = {"metadata": {"name": "web", "namespace": "shop", "uid": "web-uid"}}
    perform act with "evict shop/web"
    perform act with "evict shop/web"
end
'''
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d, 'kubectl');fake.write_text(FAKE);fake.chmod(0o755)
            state = Path(d, 'state.json');state.write_text(json.dumps({'lease': lease}))
            life = run(source, flags=('--patience=0',), env={'KUBECTL':str(fake),
                       'KUBE_CONTEXT':'imagined','HOSTNAME':'parting-test','FAKE_STATE':str(state)})
            self.assertEqual(life.code, 0, life.err)
            return json.loads(state.read_text())

    def test_other_leader_prevents_eviction(self):
        state = self.act({'metadata': {'name':'parting'}, 'spec': {
            'holderIdentity':'another-pod', 'renewTime':'2099-01-01T00:00:00Z', 'leaseDurationSeconds':30}})
        self.assertNotIn('evictions', state)
        self.assertNotIn('events', state)
        self.assertEqual(state['lease']['spec']['holderIdentity'], 'another-pod')

    def test_refused_evictions_aggregate_and_renew_lease(self):
        state = self.act()
        self.assertEqual(state['lease']['spec']['holderIdentity'], 'parting-test')
        self.assertEqual(state['evictions'], 2)
        event, = state['events']
        self.assertEqual((event['reason'], event['count']), ('EvictionFailed', 2))
