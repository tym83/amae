#!/usr/bin/env python3
"""Explicit, opt-in stand runner. Never run as part of unittest discovery.

Runs the compiled controller locally; creates resources only in helm-e2e plus
its CRD/ClusterRole. Does not deploy the CI image or execute cleanup commands.
Artifacts go to --output; kubeconfig is read from --stand-root/.stand/kubeconfig.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = 'kubernetes-super-admin@kubernetes-stand'
NS = 'helm-e2e'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stand-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    prefix = ['kubectl', '--kubeconfig', '.stand/kubeconfig', '--context', CONTEXT]
    records = []

    def call(argv, body=None, check=True, timeout=300):
        p = subprocess.run(argv, cwd=args.stand_root, input=body, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        with (out / 'commands.log').open('a') as f:
            f.write(json.dumps(argv) + '\n' + p.stdout + p.stderr + f'EXIT {p.returncode}\n')
        if check and p.returncode:
            raise RuntimeError(p.stderr)
        return p

    def kube(*argv, body=None, check=True):
        return call(prefix + list(argv), body, check)

    def snapshot(label):
        obj = json.loads(kube('get', 'helmreleases.helm.amae.io', 'hello', '-n', NS, '-o', 'json').stdout)
        helm = json.loads(call(['helm', '--kubeconfig', str(args.stand_root / '.stand/kubeconfig'),
                                '--kube-context', CONTEXT, 'status', 'hello', '-n', NS, '-o', 'json']).stdout)
        (out / (label + '.json')).write_text(json.dumps({'object': obj, 'helm': helm}, indent=2))
        return obj, helm

    def record(label, ok, detail):
        records.append({'scenario': label, 'result': 'PASS' if ok else 'FAIL', 'detail': detail})
        (out / 'results.json').write_text(json.dumps(records, indent=2))
        print(json.dumps(records[-1]), flush=True)
        if not ok:
            raise AssertionError(label + ': ' + str(detail))

    wrapper = out / 'kubectl-wrapper'
    wrapper.write_text('''#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path
prefix = ['kubectl', '--kubeconfig', '.stand/kubeconfig']
args = sys.argv[1:]
marker = Path(os.environ['HELM_STAND_MARKER'])
# Place a real competing status patch precisely after the controller's read
# and before its resourceVersion-preconditioned replace.
if 'replace' in args and '--raw' in args and marker.exists():
    marker.unlink()
    patch = {'status': {'failures': 99, 'conditions': [{'type': 'Ready', 'status': 'True',
        'reason': 'ConcurrentReady', 'message': 'injected stale result',
        'lastTransitionTime': '2026-11-21T00:00:00Z'}]}}
    subprocess.run(prefix + args[:2] + ['patch', 'helmreleases.helm.amae.io', 'hello',
        '-n', 'helm-e2e', '--subresource=status', '--type=merge', '-p', json.dumps(patch)], check=True,
        stdout=sys.stderr)
    print('INJECTED concurrent status patch', file=sys.stderr)
os.execvp(prefix[0], prefix + args)
''')
    wrapper.chmod(0o755)
    marker = out / 'inject-once'
    env = {**os.environ, 'KUBECTL': str(wrapper), 'KUBE_CONTEXT': CONTEXT,
           'KUBECONFIG': str(args.stand_root / '.stand/kubeconfig'), 'HELM_NAMESPACE': NS,
           'HELM_LOOKS': '1', 'AMAE_MEMORY': str(out / 'memory.json'),
           'AMAE_HISTORY': str(out / 'history.json'), 'HELM_STAND_MARKER': str(marker)}

    def reconcile(label, inject=False):
        if inject:
            marker.write_text('once')
        p = subprocess.run([str(ROOT / 'build/helm-controller'), '--patience=0'],
                           cwd=args.stand_root, env=env, text=True, capture_output=True, timeout=360)
        (out / (label + '.log')).write_text(p.stdout + p.stderr)
        if p.returncode:
            raise RuntimeError(p.stderr)
        return p

    def change(values, timeout=20, retries=0):
        kube('patch', 'helmreleases.helm.amae.io', 'hello', '-n', NS, '--type=merge',
             '-p', json.dumps({'spec': {'values': values, 'timeout': timeout,
                                      'upgrade': {'remediation': {'retries': retries}}}}))

    def ready(obj):
        return next(c for c in obj['status']['conditions'] if c['type'] == 'Ready')

    # Namespace may have been created during initial connectivity checks.
    exists = kube('get', 'namespace', NS, '-o', 'name', check=False)
    if exists.returncode:
        kube('create', 'namespace', NS)
    docs = (ROOT / 'kube/operators/helm.yaml').read_text().split('\n---\n')
    # All but Deployment: stand must use a local controller, not the CI image.
    kube('apply', '-f', '-', body='\n---\n'.join(docs[:-1]))
    kube('wait', '--for=condition=Established', 'crd/helmreleases.helm.amae.io', '--timeout=30s')
    kube('apply', '--dry-run=server', '-f', str(ROOT / 'kube/operators/helm.yaml'))
    obj = {'apiVersion': 'helm.amae.io/v1', 'kind': 'HelmRelease',
           'metadata': {'name': 'hello', 'namespace': NS},
           'spec': {'chart': {'path': str(ROOT / 'tests/charts/hello')},
                    'values': {'greeting': 'hello', 'image': 'busybox:1.37.0'},
                    'interval': 2, 'timeout': 120}}
    kube('apply', '-f', '-', body=json.dumps(obj))
    reconcile('install')
    obj, helm = snapshot('install')
    record('install', ready(obj)['status'] == 'True' and helm['info']['status'] == 'deployed',
           {'ready': ready(obj), 'revision': helm['version']})

    change({'greeting': 'upgraded', 'image': 'busybox:1.37.0'}, timeout=60)
    reconcile('upgrade')
    obj, helm = snapshot('upgrade')
    cm = json.loads(kube('get', 'configmap', 'hello-hello', '-n', NS, '-o', 'json').stdout)
    record('upgrade values', ready(obj)['status'] == 'True' and cm['data']['greeting'] == 'upgraded',
           {'ready': ready(obj), 'revision': helm['version']})

    change({'image': 'busybox:amae-deliberately-missing-934'}, retries=1)
    reconcile('failed-upgrade')
    obj, helm = snapshot('failed-upgrade')
    conds = {c['type']: c for c in obj['status']['conditions']}
    record('failed upgrade / rollback / exhausted',
           ready(obj)['reason'] == 'UpgradeStalled' and helm['info']['status'] == 'deployed'
           and conds['Remediated']['status'] == 'True' and obj['status']['upgradeFailures'] == 2,
           {'ready': ready(obj), 'revision': helm['version'], 'upgradeFailures': obj['status']['upgradeFailures']})
    revision = helm['version']
    reconcile('stalled-restart')
    obj, helm = snapshot('stalled-restart')
    record('stall survives restart', helm['version'] == revision and ready(obj)['reason'] == 'UpgradeStalled',
           {'revision': helm['version']})

    kube('annotate', 'helmreleases.helm.amae.io', 'hello', '-n', NS,
         'reconcile.fluxcd.io/requestedAt=' + str(time.time_ns()), '--overwrite')
    p = reconcile('concurrent-request', inject=True)
    obj, helm = snapshot('concurrent-request')
    record('requestedAt + concurrent writer',
           'INJECTED concurrent status patch' in p.stderr and 'Conflict' in p.stderr
           and ready(obj)['status'] == 'False' and ready(obj)['reason'] == 'UpgradeStalled'
           and obj['status']['upgradeFailures'] == 4 and obj['status']['failures'] == 2
           and helm['info']['status'] == 'deployed',
           {'ready': ready(obj), 'revision': helm['version'], 'upgradeFailures': obj['status']['upgradeFailures']})

    change({'image': 'busybox:1.37.0'}, timeout=60)
    reconcile('recovery')
    obj, helm = snapshot('recovery')
    record('spec change recovers', ready(obj)['status'] == 'True', {'revision': helm['version']})
    # Delete-finalizer behavior is covered deterministically. Keep stand resources
    # for inspection, as requested; cleanup commands belong only in the report.


if __name__ == '__main__':
    main()
