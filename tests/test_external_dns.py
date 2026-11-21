"""Exercise the compiled controller against persistent kubectl and PowerDNS fakes."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from test_amae import run, setUpModule, ROOT

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
from urllib.parse import unquote
p = os.environ['FAKE_STATE']
s = json.load(open(p))
a = sys.argv[1:]
result = {}
if os.path.basename(sys.argv[0]) == 'kubectl':
    assert a[:2] == ['--context', 'imagined'], a
    a = a[2:]
    s.setdefault('calls', []).append(a)
    if s.get('fail_list') and a[:2] == ['get', 'services']:
        s.pop('fail_list')
        json.dump(s,open(p,'w'))
        print('injected list failure',file=sys.stderr)
        sys.exit(1)
    if 'get' in a:
        resource = a[a.index('get')+1]
        if resource == 'leases.coordination.k8s.io':
            result = s.get('lease')
        elif resource == 'services':
            n = s.get('looks', 0)
            s['looks'] = n + 1
            if 'snapshots' in s:
                s['services'] = s['snapshots'][min(n, len(s['snapshots'])-1)]
            result = {'items':s.get('services', [])}
        elif resource == 'ingresses.networking.k8s.io':
            result = {'items':s.get('ingresses', [])}
        else:
            raise AssertionError(a)
    elif a[0] in ('create', 'replace'):
        body = json.load(sys.stdin)
        if body['kind'] == 'Lease':
            s['lease'] = body
        elif body['kind'] == 'Event':
            s.setdefault('events', []).append(body)
        else:
            raise AssertionError(body)
    else:
        raise AssertionError(a)
else:
    assert a[a.index('-H')+1] == 'X-API-Key: fake-key'
    method = a[a.index('-X')+1]
    url = next(v for v in a if v.startswith('http://'))
    zone = unquote(url.split('/zones',1)[1].lstrip('/'))
    assert '/servers/localhost/zones' in url
    if method == 'GET':
        result = {'rrsets':s.get('rrsets',[])} if zone else [{'id':'example.test.', 'name':'example.test.'}]
    elif method == 'PATCH':
        assert zone == 'example.test.', zone
        body = json.load(sys.stdin)
        if s.pop('fail_patch',False):
            json.dump(s,open(p,'w'))
            print('injected patch failure',file=sys.stderr)
            sys.exit(1)
        s.setdefault('patches', []).append(body)
        for rr in body['rrsets']:
            assert rr['changetype'] in ('REPLACE', 'DELETE')
            s['rrsets'] = [r for r in s.get('rrsets',[]) if (r['name'],r['type']) != (rr['name'],rr['type'])]
            if rr['changetype'] == 'REPLACE':
                assert all(r['disabled'] is False for r in rr['records']), rr
                s['rrsets'].append({k:v for k,v in rr.items() if k != 'changetype'})
    else:
        raise AssertionError(a)
json.dump(s, open(p,'w'))
print('' if result is None else json.dumps(result))
'''


class LiveExternalDNS(unittest.TestCase):
    def service(self, name='web', host='web.example.test', ip='192.0.2.10', **annotations):
        return {'apiVersion':'v1', 'kind':'Service',
                'metadata':{'name':name, 'namespace':'demo', 'uid':'uid-'+name,
                            'creationTimestamp':'2024-01-01T00:00:00Z',
                            'annotations':{'external-dns.alpha.kubernetes.io/hostname':host,
                                           **annotations}},
                'spec':{'type':'LoadBalancer'},
                'status':{'loadBalancer':{'ingress':[{'ip':ip}]}}}

    def reconcile(self, services=None, looks=1, env=None, expected_error=None, **state):
        with tempfile.TemporaryDirectory() as d:
            for name in ('kubectl', 'curl'):
                p = Path(d, name)
                p.write_text(FAKE)
                p.chmod(0o755)
            p = Path(d,'state.json')
            p.write_text(json.dumps(dict(services=services or [], **state)))
            life = run(Path(ROOT,'operators/external-dns.amae').read_text(),
                       flags=('--patience=0',), timeout=60,
                       env={'KUBECTL':str(Path(d,'kubectl')), 'PDNS_CURL':str(Path(d,'curl')),
                            'FAKE_STATE':str(p), 'KUBE_CONTEXT':'imagined',
                            'PDNS_API_URL':'http://fake', 'PDNS_API_KEY':'fake-key',
                            'EXTERNAL_DNS_LOOKS':str(looks), 'EXTERNAL_DNS_INTERVAL':'0.001',
                            **(env or {})})
            self.assertEqual(life.code,0,life.err)
            if expected_error:
                self.assertIn(expected_error,life.err)
            else:
                self.assertEqual(life.err,'')
            return json.loads(p.read_text())

    def test_service_and_steady_state(self):
        s = self.reconcile([self.service()], looks=3)
        self.assertEqual(len(s['patches']),1)
        a, txt = s['patches'][0]['rrsets']
        self.assertEqual((a['name'],a['type'],a['records'][0]['content']),
                         ('web.example.test.','A','192.0.2.10'))
        self.assertEqual(txt['name'],'a-web.example.test.')
        self.assertEqual(txt['records'][0]['content'],
            '"heritage=external-dns,external-dns/owner=amaenetes,external-dns/resource=service/demo/web"')
        self.assertEqual([e['reason'] for e in s['events']],['Created'])

    def test_ingress_cname(self):
        ing = self.service()
        ing.update(kind='Ingress',apiVersion='networking.k8s.io/v1',spec={'rules':[{'host':'web.example.test'}]})
        ing['metadata']['annotations'] = {}
        ing['status']['loadBalancer']['ingress'] = [{'hostname':'lb.provider.test'}]
        s = self.reconcile(ingresses=[ing])
        self.assertEqual(s['rrsets'][0]['type'],'CNAME')
        self.assertEqual(s['rrsets'][0]['records'][0]['content'],'lb.provider.test.')
        self.assertIn('ingress/demo/web',s['rrsets'][1]['records'][0]['content'])

    def test_ttl_and_ipv6_multiple_names(self):
        obj = self.service(host='web.example.test, other.example.test.', ip='2001:db8::1',
                           **{'external-dns.alpha.kubernetes.io/ttl':'90'})
        s = self.reconcile([obj],looks=2)
        self.assertEqual(len(s['patches']),1)
        self.assertEqual(len(s['rrsets']),4)
        self.assertTrue(all(r['ttl']==90 for r in s['rrsets']))
        self.assertEqual(s['rrsets'][0]['type'],'AAAA')

    def test_update_and_delete(self):
        old = self.service()
        new = self.service(ip='192.0.2.20')
        s = self.reconcile(looks=4,snapshots=[[old],[new],[],[]])
        self.assertEqual(len(s['patches']),3)
        self.assertEqual(s['patches'][1]['rrsets'][0]['records'][0]['content'],'192.0.2.20')
        self.assertTrue(all(r['changetype']=='DELETE' for r in s['patches'][2]['rrsets']))
        self.assertEqual(s['rrsets'],[])
        self.assertEqual([e['reason'] for e in s['events']],['Created','Updated','Deleted'])

    def test_upsert_only(self):
        s = self.reconcile(looks=2,snapshots=[[self.service()],[]],env={'EXTERNAL_DNS_POLICY':'upsert-only'})
        self.assertEqual(len(s['patches']),1)
        self.assertEqual(len(s['rrsets']),2)

    def test_foreign_owner_refused_once(self):
        first = self.reconcile([self.service()],env={'EXTERNAL_DNS_OWNER_ID':'other'})
        s = self.reconcile([self.service(ip='192.0.2.99')],looks=3,rrsets=first['rrsets'])
        self.assertNotIn('patches',s)
        self.assertEqual(s['rrsets'],first['rrsets'])
        self.assertEqual(len(s['events']),1)
        self.assertEqual(s['events'][0]['reason'],'Refused')
        self.assertEqual(s['events'][0]['message'],'web.example.test. belongs to other')

    def test_domain_filter(self):
        obj = self.service(host='web.example.test, web.notexample.test')
        s = self.reconcile([obj],env={'EXTERNAL_DNS_DOMAIN_FILTER':'other.test'})
        self.assertNotIn('patches',s)
        s = self.reconcile([obj],env={'EXTERNAL_DNS_DOMAIN_FILTER':'example.test,other.test'})
        self.assertEqual(len(s['rrsets']),2)

    def test_older_source_wins(self):
        old = self.service(name='old')
        young = self.service(name='young',ip='192.0.2.20')
        young['metadata']['creationTimestamp']='2024-02-01T00:00:00Z'
        s = self.reconcile([young,old],looks=3)
        self.assertEqual(s['rrsets'][0]['records'][0]['content'],'192.0.2.10')
        refused=[e for e in s['events'] if e['reason']=='Refused']
        self.assertEqual(len(refused),1)
        self.assertEqual(refused[0]['involvedObject']['name'],'young')

    def test_internal_opt_in(self):
        obj=self.service()
        obj['spec']={'type':'ClusterIP','clusterIP':'10.0.0.1'}
        s=self.reconcile([obj])
        self.assertNotIn('patches',s)
        s=self.reconcile([obj],env={'EXTERNAL_DNS_PUBLISH_INTERNAL':'1'})
        self.assertEqual(s['rrsets'][0]['records'][0]['content'],'10.0.0.1')

    def test_unowned_records_are_not_adopted(self):
        rr={'name':'web.example.test.','type':'A','ttl':300,'records':[{'content':'192.0.2.1','disabled':False}]}
        s=self.reconcile([self.service()],rrsets=[rr],looks=2)
        self.assertNotIn('patches',s)
        self.assertEqual(len(s['events']),1)

    def test_restart_delete_and_filter_protect(self):
        first=self.reconcile([self.service()])
        s=self.reconcile(rrsets=first['rrsets'])
        self.assertEqual(s['rrsets'],[])
        self.assertEqual(s['events'][0]['involvedObject']['kind'],'Service')
        s=self.reconcile(rrsets=first['rrsets'],env={'EXTERNAL_DNS_DOMAIN_FILTER':'other.test'})
        self.assertNotIn('patches',s)

    def test_single_instance_has_no_lease_calls(self):
        s=self.reconcile([self.service()],looks=2,env={'EXTERNAL_DNS_SINGLE_INSTANCE':'1'})
        self.assertNotIn('lease',s)
        self.assertFalse(any('leases.coordination.k8s.io' in c for c in s['calls']))
        self.assertEqual(len(s['patches']),1)

    def test_failed_list_never_deletes(self):
        first=self.reconcile([self.service()])
        s=self.reconcile(rrsets=first['rrsets'],fail_list=True,expected_error='injected list failure')
        self.assertNotIn('patches',s)
        self.assertEqual(s['rrsets'],first['rrsets'])

    def test_failed_patch_retries_without_success_event(self):
        s=self.reconcile([self.service()],looks=2,fail_patch=True,expected_error='injected patch failure')
        self.assertEqual(len(s['patches']),1)
        self.assertEqual([e['reason'] for e in s['events']],['Created'])

    def test_metadata_change_does_not_repeat_refusal(self):
        first=self.reconcile([self.service()],env={'EXTERNAL_DNS_OWNER_ID':'other'})
        old=self.service()
        new=self.service()
        new['metadata']['resourceVersion']='2'
        new['metadata']['annotations']['unrelated']='changed'
        s=self.reconcile(looks=3,snapshots=[[old],[new],[new]],rrsets=first['rrsets'])
        self.assertEqual(len(s['events']),1)

    def test_many_sources_survive_fading(self):
        objects=[self.service(name='web-'+str(i),host='web-'+str(i)+'.example.test') for i in range(24)]
        s=self.reconcile(objects,looks=2)
        self.assertEqual(len(s['patches']),1)
        self.assertEqual(len(s['rrsets']),48)
        self.assertEqual(len(s['events']),24)
