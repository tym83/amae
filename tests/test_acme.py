"""Live Amae controller, persistent kubectl fake and a verifying RFC 8555 peer.

No Python crypto dependency: RSA PKCS#1 v1.5 verification uses modular
exponentiation; OpenSSL signs the test CA/CSRs. All protocol bytes are checked.
"""
import base64
import datetime
import hashlib
import http.server
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]

def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip('=')

def unb64(data):
    return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4))

FAKE = r'''#!/usr/bin/env python3
import json, os, sys, re
from pathlib import Path
p=Path(os.environ['FAKE_STATE'])
s=json.loads(p.read_text()); args=sys.argv[1:]
if '--context' in args:
 i=args.index('--context'); del args[i:i+2]
ns='default'
if '-n' in args:
 i=args.index('-n'); ns=args[i+1]; del args[i:i+2]
s.setdefault('calls',[]).append(args)
def save():
 q=p.with_suffix('.tmp'); q.write_text(json.dumps(s)); q.replace(p)
def key(kind,name,namespace): return namespace+'/'+kind.lower().split('.')[0].rstrip('s')+'/'+name
def out(x): print(json.dumps(x))
if args[0]=='get':
 if args[1]=='secrets' and s.pop('fail_secret_get_once',False):
  save(); print('transientSecretReadFailure',file=sys.stderr); sys.exit(1)
 resource=args[1]; singular=resource.split('.')[0].rstrip('s')
 items=[x for x in s['objects'].values() if x['kind'].lower()==singular and ('-A' in args or x['metadata']['namespace']==ns)]
 if len(args)>2 and not args[2].startswith('-'):
  item=next((x for x in items if x['metadata']['name']==args[2]),None)
  if item: out(item)
 else: out({'items':items})
elif args[0]=='apply':
 x=json.load(sys.stdin); assert re.fullmatch(r'[a-z0-9]([-a-z0-9]*[a-z0-9])?',x['metadata']['name']); k=key(x['kind'],x['metadata']['name'],x['metadata']['namespace'])
 old=s['objects'].get(k,{})
 if x['kind']=='Secret':
  assert not old or old['type']==x['type'], 'Secret type is immutable'
  if x['type']=='kubernetes.io/tls': assert 'tls.key' in x['data'] and 'tls.crt' in x['data']
 x['metadata'].setdefault('uid',old.get('metadata',{}).get('uid','uid-'+x['metadata']['name']))
 x['metadata'].setdefault('generation',old.get('metadata',{}).get('generation',1))
 if 'status' in old: x['status']=old['status']
 for owner in x['metadata'].get('ownerReferences',[]): assert owner['controller'] is True
 if x['kind']=='Deployment':
  assert x['spec']['strategy']=={'type':'RollingUpdate','rollingUpdate':{'maxSurge':0,'maxUnavailable':1}}
  assert x['spec']['template']['spec']['automountServiceAccountToken'] is False
  assert x['spec']['template']['spec']['containers'][0]['volumeMounts'][0]['readOnly'] is True
 s['objects'][k]=x; s.setdefault('writes',[]).append(x); out(x)
elif args[0]=='patch':
 assert '--subresource=status' in args
 k=key(args[1],args[2],ns); x=s['objects'][k]
 x.setdefault('status',{}).update(json.load(sys.stdin)['status'])
 s.setdefault('patches',[]).append(k); out(x)
elif args[0]=='create' and '/events' in args[2]:
 if s.pop('fail_event_once',False):
  save(); print('transientEventFailure',file=sys.stderr); sys.exit(1)
 x=json.load(sys.stdin); s.setdefault('events',[]).append(x); out(x)
elif args[0] in ('create','replace') and '/leases' in args[2]:
 x=json.load(sys.stdin); s['objects'][key('Lease',x['metadata']['name'],x['metadata']['namespace'])]=x; out(x)
else: raise AssertionError(args)
save()
'''

class Peer(http.server.ThreadingHTTPServer):
    def __init__(self, state, directory):
        super().__init__(('127.0.0.1', 0), Handler)
        self.url = 'http://127.0.0.1:' + str(self.server_port)
        self.state, self.directory = state, directory
        self.nonces, self.accounts, self.orders, self.auths = set(), {}, {}, {}
        self.requests, self.errors = [], []
        self.reject_nonce = False
        self.invalid = False
        self.serial = 0
        self.lifetime = 60
        self.sign(['req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=ACME test root',
                   '-keyout', 'ca.key', '-out', 'ca.pem', '-days', '90'])
    def sign(self, args):
        return subprocess.run(['openssl', *args], cwd=self.directory, check=True,
                              capture_output=True).stdout
    def nonce(self):
        self.serial += 1
        n = 'nonce-' + str(self.serial)
        self.nonces.add(n)
        return n

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def reply(self, body, code=200, location=None, pem=False):
        raw = body.encode() if pem else json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Replay-Nonce', self.server.nonce())
        self.send_header('Content-Type', 'application/pem-certificate-chain' if pem else 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        if location:
            self.send_header('Location', self.server.url + location)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)
    def do_HEAD(self):
        self.server.requests.append(('HEAD', self.path))
        self.reply({})
    def do_GET(self):
        self.server.requests.append(('GET', self.path))
        self.reply({k: self.server.url + '/' + k for k in ('newNonce', 'newAccount', 'newOrder')})
    def do_POST(self):
        try:
            self.handle_post()
        except Exception as e:
            self.server.errors.append(repr(e))
            self.reply({'type': 'test:assertion', 'detail': repr(e)}, 400)
    def handle_post(self):
        s = self.server
        s.requests.append(('POST', self.path))
        assert self.headers['Content-Type'] == 'application/jose+json'
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        protected = json.loads(unb64(body['protected']))
        assert protected['url'] == s.url + self.path
        assert protected['alg'] == 'RS256'
        assert protected['nonce'] in s.nonces, ('nonce replay', protected)
        s.nonces.remove(protected['nonce'])
        if self.path == '/newAccount':
            assert 'kid' not in protected
            jwk = protected['jwk']
        else:
            assert 'jwk' not in protected
            jwk = s.accounts[protected['kid']]
        n, e = int.from_bytes(unb64(jwk['n']), 'big'), int.from_bytes(unb64(jwk['e']), 'big')
        signature = unb64(body['signature'])
        encoded = pow(int.from_bytes(signature, 'big'), e, n).to_bytes((n.bit_length()+7)//8, 'big')
        digest = hashlib.sha256((body['protected']+'.'+body['payload']).encode()).digest()
        tail = bytes.fromhex('3031300d060960864801650304020105000420') + digest
        assert encoded == b'\0\1' + b'\xff'*(len(encoded)-len(tail)-3) + b'\0' + tail, 'bad signature'
        if s.reject_nonce:
            s.reject_nonce = False
            self.reply({'type':'urn:ietf:params:acme:error:badNonce'}, 400)
            return
        payload = json.loads(unb64(body['payload'])) if body['payload'] else None
        if self.path == '/newAccount':
            assert payload['termsOfServiceAgreed'] is True
            key = s.url + '/account/' + b64(hashlib.sha256(json.dumps(jwk, sort_keys=True).encode()).digest())
            exists = key in s.accounts
            s.accounts[key] = jwk
            self.reply({'status':'valid'}, 200 if exists else 201, key[len(s.url):])
        elif self.path == '/newOrder':
            ident = str(len(s.orders)+1)
            auths = []
            for i, identifier in enumerate(payload['identifiers']):
                assert identifier['type']=='dns'
                a = ident+'-'+str(i)
                token = 'token-'+a
                s.auths[a] = {'identifier':identifier, 'status':'pending', 'challenges':[
                    {'type':'http-01','url':s.url+'/challenge/'+a,'token':token,'status':'pending'}]}
                auths.append(s.url+'/auth/'+a)
            s.orders[ident] = {'status':'pending','authorizations':auths,'finalize':s.url+'/finalize/'+ident}
            self.reply(s.orders[ident], 201, '/order/'+ident)
        elif self.path.startswith('/auth/'):
            assert payload is None, 'POST-as-GET must have empty payload'
            self.reply(s.auths[self.path.split('/')[-1]])
        elif self.path.startswith('/challenge/'):
            assert payload == {}
            auth = s.auths[self.path.split('/')[-1]]
            token = auth['challenges'][0]['token']
            thumb = b64(hashlib.sha256(json.dumps(jwk,sort_keys=True,separators=(',',':')).encode()).digest())
            objects = json.loads(s.state.read_text())['objects'].values()
            tokens = {k:v for x in objects if x['kind']=='ConfigMap' for k,v in x['data'].items()}
            assert tokens[token] == token+'.'+thumb, 'key authorization / RFC7638 thumbprint'
            auth['status'] = 'invalid' if s.invalid else 'valid'
            auth['challenges'][0]['status'] = auth['status']
            self.reply(auth['challenges'][0])
        elif self.path.startswith('/order/'):
            assert payload is None
            order = s.orders[self.path.split('/')[-1]]
            if order['status']=='pending' and all(s.auths[x.split('/')[-1]]['status']=='valid' for x in order['authorizations']):
                order['status']='ready'
            self.reply(order)
        elif self.path.startswith('/finalize/'):
            ident=self.path.split('/')[-1]
            order=s.orders[ident]
            assert order['status']=='ready'
            (s.directory/'request.der').write_bytes(unb64(payload['csr']))
            s.sign(['req','-inform','DER','-in','request.der','-verify','-noout'])
            s.sign(['req','-inform','DER','-in','request.der','-out','request.pem'])
            s.sign(['x509','-req','-in','request.pem','-CA','ca.pem','-CAkey','ca.key',
                    '-set_serial',ident,'-days',str(s.lifetime),'-copy_extensions','copy','-out','cert-'+ident+'.pem'])
            order.update(status='valid', certificate=s.url+'/cert/'+ident)
            self.reply(order)
        elif self.path.startswith('/cert/'):
            assert payload is None
            ident=self.path.split('/')[-1]
            self.reply((s.directory/('cert-'+ident+'.pem')).read_text()+(s.directory/'ca.pem').read_text(),pem=True)
        else:
            raise AssertionError(self.path)

class AccountJWK(unittest.TestCase):
    def test_modulus_bytes_in_c_and_utf8_locales(self):
        # Execute the controller's actual shell, comparing bytes independently
        # of its hex conversion and base64 pipeline (including the high bit).
        source = (ROOT/'operators/acme.amae').read_text()
        ritual = source.split('ritual acme_jwk pem\n', 1)[1]
        command, _ = json.JSONDecoder().raw_decode(ritual.split('ask world ', 1)[1])
        available = subprocess.check_output(['locale', '-a'], text=True).splitlines()
        locales = ['C'] + [name for name in available
                           if name.lower().replace('-', '') in
                           ('c.utf8', 'en_us.utf8')]
        shells = ['/bin/sh']
        if shutil.which('dash'):
            shells.append(shutil.which('dash'))
        pem = subprocess.check_output(
            ['openssl', 'genpkey', '-algorithm', 'RSA',
             '-pkeyopt', 'rsa_keygen_bits:2048'], stderr=subprocess.DEVNULL)
        modulus = subprocess.check_output(
            ['openssl', 'rsa', '-noout', '-modulus'], input=pem,
            stderr=subprocess.DEVNULL).decode().strip().split('=', 1)[1]
        expected = bytes.fromhex(modulus)
        self.assertEqual(len(expected), 256)
        self.assertGreaterEqual(expected[0], 128)
        for shell in shells:
            for locale in locales:
                with self.subTest(shell=shell, locale=locale):
                    result = subprocess.run(
                        [shell, '-c', command], input=pem, capture_output=True,
                        check=True, env=dict(os.environ, LC_ALL=locale))
                    jwk = json.loads(result.stdout)
                    self.assertEqual(jwk['kty'], 'RSA')
                    self.assertEqual(unb64(jwk['e']), b'\x01\x00\x01')
                    self.assertEqual(unb64(jwk['n']), expected)


class CertificateDates(unittest.TestCase):
    def test_one_and_two_digit_days(self):
        # Exercise the actual jq filter embedded in the controller's shell command.
        source = (ROOT/'operators/acme.amae').read_text()
        ritual = source.split('ritual acme_dates chain\n', 1)[1]
        command, _ = json.JSONDecoder().raw_decode(ritual.split('ask world ', 1)[1])
        words = shlex.split(command)
        date_filter = words[words.index('jq') + 2]
        for month, name in enumerate(('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'), 1):
            for zone in ('UTC', 'America/Chicago'):
                with self.subTest(month=name, timezone=zone):
                    dates = (f'notBefore={name}  1 00:00:00 2026 GMT\n'
                             f'notAfter={name} 21 18:45:20 2026 GMT\n')
                    result = subprocess.run(['jq', '-Rsc', date_filter], input=dates,
                                            capture_output=True, text=True, check=True,
                                            env=dict(os.environ, TZ=zone))
                    self.assertEqual(json.loads(result.stdout), {
                        'start': datetime.datetime(2026, month, 1,
                                                  tzinfo=datetime.timezone.utc).timestamp(),
                        'finish': datetime.datetime(2026, month, 21, 18, 45, 20,
                                                   tzinfo=datetime.timezone.utc).timestamp(),
                    })


class LiveACME(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(['make','-s','build/acme'],cwd=ROOT,check=True)
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.d = Path(self.temp.name)
        self.state = self.d/'state.json'
        self.peer = Peer(self.state,self.d)
        threading.Thread(target=self.peer.serve_forever,daemon=True).start()
        self.addCleanup(self.peer.server_close)
        self.addCleanup(self.peer.shutdown)
        self.now=int(time.time())
        self.clock=self.d/'clock'; self.clock.write_text(str(self.now))
        self.fake=self.d/'kubectl'; self.fake.write_text(FAKE); self.fake.chmod(0o755)
        self.write({'objects':{
            'demo/issuer/ca':{'apiVersion':'acme.amae.io/v1','kind':'Issuer',
              'metadata':{'name':'ca','namespace':'demo','uid':'issuer-uid','generation':1},
              'spec':{'acme':{'server':self.peer.url+'/directory','email':'a@example.test',
                'privateKeySecretRef':{'name':'account'},'solvers':[{'http01':{'standalone':True}}]}}},
            'demo/certificate/leaf':{'apiVersion':'acme.amae.io/v1','kind':'Certificate',
              'metadata':{'name':'leaf','namespace':'demo','uid':'12345678-1234-1234-1234-123456789abc','generation':1},
              'spec':{'secretName':'leaf-tls','dnsNames':['test.example','second.example'],'issuerRef':{'name':'ca'}}}}})
    def read(self): return json.loads(self.state.read_text())
    def write(self,s): self.state.write_text(json.dumps(s))
    def run_controller(self,looks=14,expected_error='',**overrides):
        env=dict(os.environ,KUBECTL=str(self.fake),KUBE_CONTEXT='fake',FAKE_STATE=str(self.state),
                 ACME_NO_LEASE='1',ACME_NOW=str(self.clock),ACME_LOOKS=str(looks),
                 ACME_INTERVAL='0.001',ACME_POLL_BASE='0',ACME_POLL_CAP='0',ACME_PRESENT_DELAY='0',
                 AMAE_HISTORY=str(self.d/'history'))
        env.update(overrides)
        result=subprocess.run([str(ROOT/'build/acme'),'--patience=0'],env=env,capture_output=True,text=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stderr)
        if expected_error:
            self.assertIn(expected_error,result.stderr)
        else:
            self.assertEqual(result.stderr,'')
        self.assertEqual(self.peer.errors,[])
        return self.read()
    def issued(self,s):
        st=s['objects']['demo/certificate/leaf']['status']
        self.assertEqual(st['state'],'Issued',st)
        self.assertEqual(st['conditions'][0]['status'],'True')
        secret=s['objects']['demo/secret/leaf-tls']
        self.assertEqual(secret['type'],'kubernetes.io/tls')
        self.assertEqual(base64.b64decode(secret['data']['ca.crt']).strip(), (self.d/'ca.pem').read_bytes().strip())
        (self.d/'download.pem').write_bytes(base64.b64decode(secret['data']['tls.crt']))
        subprocess.run(['openssl','verify','-CAfile',str(self.d/'ca.pem'),str(self.d/'download.pem')],check=True,capture_output=True)
        dates = subprocess.run(['openssl','x509','-in',str(self.d/'download.pem'),'-noout','-dates'],
                               check=True,capture_output=True,text=True).stdout.splitlines()
        for field, raw in zip(['notBefore','notAfter'], dates):
            value = datetime.datetime.strptime(raw.split('=',1)[1], '%b %d %H:%M:%S %Y %Z')
            self.assertEqual(st[field], value.isoformat()+'Z')
        expiry = datetime.datetime.fromisoformat(st['notAfter'].replace('Z','+00:00'))
        renewal = expiry - datetime.timedelta(days=30)
        self.assertEqual(st['renewalTime'], renewal.isoformat().replace('+00:00','Z'))
        return st
    def test_issue_and_steady_state(self):
        s=self.run_controller(); self.issued(s)
        self.assertEqual(len(self.peer.orders),1)
        self.assertEqual(len(self.peer.auths),2)
        states=[e['reason'] for e in s['events']]
        for state in ['New','Issuing','Registered','Pending','Presented','Processing','Authorized','Finalizing','Valid','Issued']:
            self.assertIn(state,states)
        traffic=len(self.peer.requests); events=len(s['events']); patches=len(s['patches'])
        s=self.run_controller(3)
        self.assertEqual(len(self.peer.requests),traffic)
        self.assertEqual(len(s['events']),events)
        self.assertEqual(len(s['patches']),patches)
    def test_account_reuse_and_secret_loss(self):
        s=self.run_controller(); self.issued(s)
        account=s['objects']['demo/secret/account']['data']
        del s['objects']['demo/secret/leaf-tls']; self.write(s)
        s=self.run_controller(); self.issued(s)
        self.assertEqual(len(self.peer.orders),2)
        self.assertEqual(s['objects']['demo/secret/account']['data'],account)
        self.assertEqual(sum(p=='/newAccount' for _,p in self.peer.requests),1)
    def test_bad_nonce(self):
        self.peer.reject_nonce=True
        self.issued(self.run_controller())
        self.assertEqual(sum(p=='/newAccount' for _,p in self.peer.requests),2)
    def test_invalid_backoff_and_recovery(self):
        self.peer.invalid=True
        s=self.run_controller()
        st=s['objects']['demo/certificate/leaf']['status']
        self.assertEqual(st['state'],'Failed'); self.assertEqual(st['retryAt'],self.now+60)
        self.assertEqual(st['conditions'][0]['status'],'False')
        self.assertEqual(st['reason'],'InvalidAuthorization')
        self.assertTrue(any(x['kind']=='Challenge' and x.get('status',{}).get('state')=='Failed' for x in s['objects'].values()))
        traffic=len(self.peer.requests)
        self.run_controller(3)
        self.assertEqual(len(self.peer.requests),traffic)
        self.clock.write_text(str(self.now+60)); s=self.run_controller()
        st=s['objects']['demo/certificate/leaf']['status']
        self.assertEqual(st['failures'],2); self.assertEqual(st['retryAt'],self.now+180)
        self.peer.invalid=False; self.clock.write_text(str(self.now+180))
        self.issued(self.run_controller())
    def test_renewal_when_due_reuses_key(self):
        s=self.run_controller(); self.issued(s)
        key=s['objects']['demo/secret/leaf-tls']['data']['tls.key']
        self.peer.lifetime = 90
        self.clock.write_text(str(self.now+31*86400))
        s=self.run_controller(); self.issued(s)
        self.assertEqual(len(self.peer.orders),2)
        self.assertEqual(s['objects']['demo/secret/leaf-tls']['data']['tls.key'],key)
    def test_restart_pending_and_existing_account_lookup(self):
        s=self.run_controller(2)
        self.assertEqual(s['objects']['demo/certificate/leaf']['status']['state'],'Issuing')
        del s['objects']['demo/secret/account']['data']['accountURL']; self.write(s)
        self.issued(self.run_controller())
        self.assertEqual(len(self.peer.accounts),1)
        self.assertEqual(len(self.peer.orders),1)

    def test_retry_cap_and_no_repeated_events(self):
        self.peer.invalid = True
        s = self.run_controller(14, ACME_RETRY_BASE='2', ACME_RETRY_CAP='3')
        self.assertEqual(s['objects']['demo/certificate/leaf']['status']['retryAt'], self.now+2)
        events = len(s['events'])
        self.assertEqual(len(self.run_controller(3)['events']), events)
        self.clock.write_text(str(self.now+2))
        s = self.run_controller(14, ACME_RETRY_BASE='2', ACME_RETRY_CAP='3')
        self.assertEqual(s['objects']['demo/certificate/leaf']['status']['retryAt'], self.now+5)

    def test_secret_transport_retry_preserves_order(self):
        s=self.read(); s['fail_secret_get_once']=True; self.write(s)
        s=self.run_controller(expected_error='acme API retry:')
        self.issued(s)
        self.assertEqual(len(self.peer.orders),1)
        self.assertEqual(s['objects']['demo/certificate/leaf']['status']['failures'],0)

    def test_event_failure_does_not_fail_issuance(self):
        s=self.read(); s['fail_event_once']=True; self.write(s)
        s=self.run_controller(expected_error='acme event queued:')
        self.issued(s)
        self.assertEqual(len(self.peer.orders),1)
        self.assertEqual(sum(e['reason']=='New' for e in s['events']),1)
        self.assertEqual(s['objects']['demo/certificate/leaf']['status']['failures'],0)

    def test_other_leader(self):
        s = self.read()
        s['objects']['amaenetes/lease/acme'] = {
            'apiVersion':'coordination.k8s.io/v1','kind':'Lease',
            'metadata':{'name':'acme','namespace':'amaenetes','resourceVersion':'1'},
            'spec':{'holderIdentity':'someone-else','leaseDurationSeconds':120,
                    'renewTime':'2099-01-01T00:00:00Z'}}
        self.write(s)
        s = self.run_controller(2, ACME_NO_LEASE='0')
        self.assertEqual(self.peer.requests, [])
        self.assertNotIn('status', s['objects']['demo/certificate/leaf'])

    def test_pending_spec_change_starts_new_order(self):
        s = self.run_controller(2)
        cert = s['objects']['demo/certificate/leaf']
        cert['spec']['dnsNames'] = ['changed.example']
        cert['metadata']['generation'] = 2
        self.write(s)
        s = self.run_controller(); self.issued(s)
        self.assertEqual(len(self.peer.orders), 2)
        self.assertEqual(s['objects']['demo/certificate/leaf']['status']['observedGeneration'], 2)
        self.assertEqual(self.peer.auths['2-0']['identifier']['value'], 'changed.example')


if __name__=='__main__': unittest.main()
