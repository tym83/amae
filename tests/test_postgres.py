"""Run the compiled Amae state machine against a durable kubectl fake.

Side effects and lost replies survive process restarts, like the API and PGDATA.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_amae import ROOT, compile_source, setUpModule

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
p = os.environ['FAKE_STATE']
s = json.load(open(p))
a = sys.argv[1:]
assert a[:2] == ['--context', 'imagined'], a
a = a[2:]
assert '-A' not in a, a
if '-n' in a:
    assert a[a.index('-n')+1] == 'pg-e2e', a
    k=a.index('-n'); del a[k:k+2]
a=[x for x in a if not x.startswith('--request-timeout=')]
verb=a[0]; result={}; action=''
s.setdefault('calls',[]).append(a)
def save():
    json.dump(s,open(p,'w'))
def fail(message):
    save(); print(message,file=sys.stderr); sys.exit(1)
def merge(dst, src):
    for k,v in src.items():
        if isinstance(v,dict): merge(dst.setdefault(k,{}),v)
        elif v is None: dst.pop(k,None)
        else: dst[k]=v

def pod(name,primary=False,upstream='demo-1'):
    return {'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'pg-e2e','uid':name+'-uid','labels':{'role':'primary' if primary else 'replica'},'annotations':{'postgres.amae.io/upstream':upstream}},'status':{'phase':'Running','conditions':[{'type':'Ready','status':'True'}]}}
if verb=='get':
    r=a[1]; name=a[2] if len(a)>2 and not a[2].startswith('-') else None
    if r=='leases.coordination.k8s.io':
        result=s.get('lease')
        if result and not s.get('foreign'):
            result['spec']['renewTime']='2000-01-01T00:00:00.000000Z'
    elif r=='clusters.postgres.amae.io': result=s['cluster'] if name else {'items':[s['cluster']]}
    elif r=='pods': result=s.setdefault('pods',{}).get(name)
    elif r in ('secret','service'): result=s.setdefault('resources',{}).get(name)
    else: fail('unexpected get '+repr(a))
elif verb in ('create','replace'):
    body=json.load(sys.stdin); kind=body['kind']; name=body['metadata']['name']
    if kind=='Lease':
        s['lease']=body
    elif kind=='Event': s.setdefault('events',[]).append(body)
    elif kind=='Pod':
        assert body['spec']['automountServiceAccountToken'] is False
        assert body['metadata']['ownerReferences'][0]['controller'] is True
        s.setdefault('pods',{})[name]=pod(name,body['metadata']['labels']['role']=='primary',body['metadata']['annotations']['postgres.amae.io/upstream'])
        s.setdefault('pg',{})[name]={'recovery':body['metadata']['labels']['role']!='primary','receivedLSN':'0/300','replayedLSN':'0/300','flushLSN':'0/300'}
        action='create-pod'
    else: s.setdefault('resources',{})[name]=body
elif verb=='patch':
    r,name=a[1:3]; body=json.load(sys.stdin)
    if r=='clusters.postgres.amae.io':
        if '--subresource=status' in a:
            assert body['metadata']['resourceVersion']==s['cluster']['metadata']['resourceVersion']
            action='status:'+body['status']['phase']
            s.setdefault('phases',[]).append(body['status']['phase'])
        merge(s['cluster'],body)
        s['cluster']['metadata']['resourceVersion']=str(int(s['cluster']['metadata']['resourceVersion'])+1)
        result=s['cluster']
    elif r=='pods':
        merge(s['pods'][name],body)
        action='label:'+body['metadata'].get('labels',{}).get('role','')
    elif r=='events': pass
    else: fail('unexpected patch '+repr(a))
elif verb=='delete':
    name=a[2]; s['pods'].pop(name,None); s['pg'].pop(name,None); action='delete-pod'
elif verb=='exec':
    name=a[1]; script=a[-1]
    if s.get('unreachable')==name: fail('node unreachable')
    if name not in s['pods']: fail('pod missing')
    db=s['pg'][name]
    if script.startswith('touch /data/fenced'):
        assert s['cluster']['status']['phase']=='Failover: fencing'
        assert s['pods'][name]['metadata']['labels']['role']=='fenced'
        assert s['cluster']['metadata']['annotations']['postgres.amae.io/fencedInstances']==json.dumps([name],separators=(',',':'))
        db['stopped']=True; action='stop'
        result='0/300' if '/data/barrier; fi;' in script else ''
    elif db.get('stopped'): fail('postgres stopped')
    elif script.startswith('pg_isready'): result=''
    elif 'json_build_object' in script: result=json.dumps({k:v for k,v in db.items() if k!='stopped'})
    elif 'pg_last_wal_replay_lsn() >=' in script: result='f' if s.get('lagging') else 't'
    elif 'SELECT pg_is_in_recovery()' in script: result='t' if db['recovery'] else 'f'
    elif 'promote' in script:
        st=s['cluster']['status']
        assert st['phase']=='Failover: promoting' and st['fenceConfirmed']==1
        assert name==st['targetPrimary']
        assert all(v.get('stopped') or v['recovery'] for k,v in s['pg'].items() if k!=name)
        db['recovery']=False; s.setdefault('promotions',[]).append(name); action='promote'; result=''
    elif 'restart' in script: action='restart'; result=''
    else: fail('unexpected exec '+script)
else: fail('unexpected '+repr(a))
if action:
    s.setdefault('actions',[]).append(action)
    if action==s.get('fail_after'):
        s.pop('fail_after'); fail('injected lost reply after '+action)
save()
print('' if result is None else result if isinstance(result,str) else json.dumps(result))
'''


def initial(stage='Healthy'):
    pods={}
    pg={}
    for i in range(1,4):
        name=f'demo-{i}'
        pods[name]={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'pg-e2e','uid':name+'-uid','labels':{'role':'primary' if i==1 else 'replica'},'annotations':{'postgres.amae.io/upstream':'demo-1'}},'status':{'phase':'Running','conditions':[{'type':'Ready','status':'True'}]}}
        pg[name]={'recovery':i!=1,'receivedLSN':f'0/{i}00','replayedLSN':f'0/{i}00','flushLSN':'0/300'}
    return {'cluster':{'apiVersion':'postgres.amae.io/v1','kind':'Cluster','metadata':{'name':'demo','namespace':'pg-e2e','uid':'cluster-uid','resourceVersion':'1','annotations':{}},'spec':{'instances':3,'image':'postgres:17.9-bookworm'},'status':{'phase':stage,'currentPrimary':'demo-1','targetPrimary':'','unhealthySince':1}},'pods':pods,'pg':pg,'resources':{n:{'kind':'Secret' if n.endswith('auth') else 'Service'} for n in ('demo-auth','demo-rw','demo-ro')}}


class Postgres(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary, error=compile_source(Path(ROOT,'operators/postgres.amae').read_text())
        if error: raise AssertionError(error)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name,'state.json')
        fake=Path(self.tmp.name,'kubectl'); fake.write_text(FAKE); fake.chmod(0o755)
        self.env=dict(os.environ,KUBECTL=str(fake),KUBE_CONTEXT='imagined',PG_NAMESPACE='pg-e2e',PG_LEASE_NAMESPACE='pg-e2e',PG_LOOKS='1',PG_INTERVAL='0',PG_FAILOVER_DELAY='0',FAKE_STATE=str(self.path),AMAE_HISTORY=str(Path(self.tmp.name,'history.json')))

    def write(self,s): self.path.write_text(json.dumps(s))
    def read(self): return json.loads(self.path.read_text())
    def once(self):
        r=subprocess.run([self.binary,'--patience=0'],env=self.env,capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr)
        return r.stderr
    def finish(self):
        for _ in range(16):
            err=self.once(); s=self.read()
            if s['cluster']['status']['phase']=='Healthy': return s
        self.fail(f'did not finish: {s["cluster"]["status"]}; {err}')
    def down(self):
        s=initial(); s['pods'].pop('demo-1'); s['pg'].pop('demo-1'); return s

    def test_failover_chooses_highest_lsn_and_rebuilds(self):
        self.write(self.down()); self.once(); s=self.finish()
        self.assertEqual(s['cluster']['status']['currentPrimary'],'demo-3')
        self.assertEqual(s['promotions'],['demo-3'])
        self.assertEqual(s['cluster']['status']['unhealthySince'],0)
        self.assertEqual(s['cluster']['status']['conditions'][0]['status'],'True')
        self.assertTrue(s['pg']['demo-1']['recovery'])
        self.assertEqual(s['cluster']['metadata']['annotations']['postgres.amae.io/fencedInstances'],'[]')
        for stage in ('fencing','promoting','switching','rebuilding'):
            self.assertIn('Failover: '+stage,s['phases'])

    def test_lost_reply_after_each_step_resumes(self):
        for action in ('status:Failover: fencing','status:Failover: promoting','promote','status:Failover: switching','label:primary','status:Failover: rebuilding','restart','create-pod'):
            with self.subTest(action=action):
                s=self.down(); s['fail_after']=action; self.write(s)
                self.once(); s=self.finish()
                self.assertNotIn('fail_after',s)
                self.assertEqual(s['promotions'],['demo-3'])
                self.assertEqual(sum(not d['recovery'] and not d.get('stopped') for d in s['pg'].values()),1)

    def test_fence_failure_never_promotes(self):
        s=initial(); s['pods']['demo-1']['status']['conditions'][0]['status']='False'; s['unreachable']='demo-1'; self.write(s)
        for _ in range(4): self.once()
        s=self.read(); self.assertEqual(s['cluster']['status']['phase'],'Failover: fencing'); self.assertFalse(s.get('promotions'))
        self.assertEqual(s['pods']['demo-1']['metadata']['labels']['role'],'fenced')

    def test_planned_switchover_waits_for_barrier(self):
        s=initial(); s['cluster']['metadata']['annotations']['postgres.amae.io/switchover-to']='demo-2'; s['lagging']=True; s['fail_after']='stop'; self.write(s)
        for _ in range(4): self.once()
        s=self.read(); self.assertEqual(s['cluster']['status']['phase'],'Failover: promoting'); self.assertFalse(s.get('promotions'))
        self.assertTrue(s['pg']['demo-1']['stopped']); s['lagging']=False; self.write(s)
        s=self.finish(); self.assertEqual(s['promotions'],['demo-2'])

    def test_foreign_lease_blocks_all_mutations(self):
        s=self.down(); s['foreign']=True; s['lease']={'apiVersion':'coordination.k8s.io/v1','kind':'Lease','metadata':{'name':'postgres'},'spec':{'holderIdentity':'other','renewTime':'2099-01-01T00:00:00.000000Z','leaseDurationSeconds':120}}
        self.write(s); self.once(); s=self.read(); self.assertFalse(s.get('actions'))

    def test_delay_survives_restart(self):
        s=self.down(); s['cluster']['status']['unhealthySince']=0; self.write(s)
        self.env['PG_FAILOVER_DELAY']='1000'; self.once(); first=self.read()['cluster']['status']['unhealthySince']; self.once()
        self.assertGreater(first,0); self.assertEqual(self.read()['cluster']['status']['unhealthySince'],first)
        self.assertFalse(self.read().get('promotions'))

    def test_target_uid_change_never_retargets(self):
        self.write(self.down()); self.once(); self.once(); s=self.read()
        self.assertEqual(s['cluster']['status']['phase'],'Failover: promoting')
        s['pods']['demo-3']['metadata']['uid']='replacement'; self.write(s); self.once()
        self.assertFalse(self.read().get('promotions'))

    def test_bootstrap_creates_bare_pods_and_secret(self):
        s=initial(); s['cluster'].pop('status'); s['pods']={}; s['pg']={}; s['resources']={}; self.write(s)
        self.once(); self.once(); s=self.read()
        self.assertEqual(len(s['pods']),3)
        self.assertIn('password',s['resources']['demo-auth']['stringData'])
        self.assertEqual(s['resources']['demo-rw']['spec']['selector']['role'],'primary')

    def test_rebuild_fenced_primary_even_when_upstream_matches(self):
        s=initial()
        s['pods']['demo-1']['metadata']['annotations']['postgres.amae.io/upstream']='demo-2'
        s['cluster']['metadata']['annotations']['postgres.amae.io/switchover-to']='demo-2'
        self.write(s); self.once(); s=self.finish()
        self.assertTrue(s['pg']['demo-1']['recovery'])
        self.assertIn('delete-pod',s['actions'])

    def test_lsn_high_word_beats_low_word(self):
        s=self.down()
        s['pg']['demo-2'].update(receivedLSN='1/0',replayedLSN='0/FFFFFFFF')
        s['pg']['demo-3'].update(receivedLSN='0/FFFFFFFF',replayedLSN='0/FFFFFFFF')
        self.write(s); self.once(); self.once()
        self.assertEqual(self.read()['cluster']['status']['targetPrimary'],'demo-2')

    def test_terminated_primary_is_deleted_before_promotion(self):
        s=initial(); s['pods']['demo-1']['status']['phase']='Failed'; self.write(s)
        self.once(); s=self.finish()
        self.assertLess(s['actions'].index('delete-pod'),s['actions'].index('promote'))
