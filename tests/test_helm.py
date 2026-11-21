"""The helm operator: remediation, stall, finalizer, and a status write that
cannot tear the way fluxcd/pkg#934 tears it.

Two halves:

- FluxModel is a scripted Python model of what fluxcd/pkg's patch.Helper does
  (runtime/patch/patch.go @ e270089eb564): the conditions are patched first
  against a fresh read with an optimistic lock, then the rest of the status is
  patched as a merge computed against the snapshot from reconcile start, with
  no precondition. A concurrent writer (or a failed half) leaves Ready
  describing a state the object is not in.

- The same interleavings run against the compiled Amae controller through a
  fake kubectl and a fake helm. The controller writes the whole status once
  per reconcile through a resourceVersion-preconditioned replace, recomputed
  from a fresh read on every conflict, so its successful write has no
  conditions/rest intermediate state.
  This is a scripted model, not execution of the Go helper.
"""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from test_amae import run, setUpModule, ROOT  # noqa: F401

FAKE = r'''#!/usr/bin/env python3
"""A fake kubectl and helm sharing one state file, for a cluster of the mind."""
import json, os, re, sys

p = os.environ['FAKE_STATE']
state = json.load(open(p))

def save():
    with open(p, 'w') as f:
        json.dump(state, f)

def deep_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = v

def find_hr(ns, name):
    for o in state.get('helmreleases', []):
        if o['metadata']['namespace'] == ns and o['metadata']['name'] == name:
            return o
    sys.stderr.write('helmreleases.helm.amae.io "%s" not found in %s\n' % (name, ns))
    sys.exit(1)

def bump_rv(o):
    o['metadata']['resourceVersion'] = str(int(o['metadata'].get('resourceVersion', '0')) + 1)

who = os.path.basename(sys.argv[0])
args = sys.argv[1:]

if who == 'kubectl':
    assert args[:2] == ['--context', 'imagined'], args
    args = args[2:]
    if args[:2] == ['get', 'helmreleases.helm.amae.io']:
        if '-A' in args or args[2] == '-n':
            n = state.get('hr_polls', 0)
            state['hr_polls'] = n + 1
            looks = state.get('hr_looks')
            if looks is not None:
                if n < len(looks):
                    for update in looks[n]:
                        found = next((o for o in state['helmreleases'] if o['metadata']['name'] == update['metadata']['name']), None)
                        if found is None:
                            state['helmreleases'].append(update)
                        else:
                            rv = found['metadata']['resourceVersion']
                            found['metadata'].update(update['metadata'])
                            found['metadata']['resourceVersion'] = rv
                            found['spec'] = update['spec']
                save()
            print(json.dumps({'items': state.get('helmreleases', [])}))
        else:
            ns = args[args.index('-n') + 1]
            print(json.dumps(find_hr(ns, args[2])))
    elif args[:2] == ['patch', 'helmreleases.helm.amae.io']:
        name, ns = args[2], args[args.index('-n') + 1]
        body = json.load(sys.stdin)
        o = find_hr(ns, name)
        if body.get('metadata', {}).get('resourceVersion') != o['metadata']['resourceVersion']:
            sys.exit('Conflict')
        deep_merge(o['metadata'], body.get('metadata', {}))
        bump_rv(o)
        state.setdefault('finalizer_patches', []).append(
            {'name': name, 'ns': ns, 'finalizers': o['metadata'].get('finalizers', [])})
        save()
    elif args[:2] == ['replace', '--raw'] and args[2].endswith('/status'):
        m = re.match(r'/apis/helm\.amae\.io/v1/namespaces/([^/]+)/helmreleases/([^/]+)/status', args[2])
        ns, name = m.group(1), m.group(2)
        body = json.load(sys.stdin)
        o = find_hr(ns, name)
        inject = state.get('inject', {})
        entry = {'name': name, 'ns': ns, 'rv': body['metadata'].get('resourceVersion')}
        # A concurrent writer landing mid-reconcile, before the precondition
        # is even checked: the write that follows must conflict.
        if inject.get('bump') and not state.get('bumped'):
            state['bumped'] = 1
            deep_merge(o.setdefault('status', {}), inject.get('concurrent_patch', {}))
            if inject.get('helm_state'):
                state['releases'][ns + '/' + name]['status'] = inject['helm_state']
            if inject.get('generation'):
                o['metadata']['generation'] = inject['generation']
            bump_rv(o)
        if state.get('fail_writes_left', 0) > 0:
            state['fail_writes_left'] -= 1
            bump_rv(o)  # prove the retry read fresh state
            entry['failed'] = 'injected api failure'
            state.setdefault('status_writes', []).append(entry)
            save()
            sys.stderr.write('Error: injected api failure\n')
            sys.exit(1)
        if o['metadata'].get('resourceVersion') != body['metadata'].get('resourceVersion'):
            entry['failed'] = 'conflict'
            state.setdefault('status_writes', []).append(entry)
            save()
            sys.stderr.write('Operation cannot be fulfilled: the object has been modified\n')
            sys.exit(1)
        o['status'] = body['status']
        bump_rv(o)
        entry['status'] = body['status']
        state.setdefault('status_writes', []).append(entry)
        save()
    elif args[:2] == ['create', '--raw'] and args[2].endswith('/events'):
        state.setdefault('events', []).append(json.load(sys.stdin))
        save()
    else:
        sys.exit('fake kubectl cannot ' + ' '.join(args))
elif who == 'helm':
    while args and args[0].startswith('--'):
        args = args[2:]  # --kubeconfig X / --kube-context Y both take values
    cmd = args[0]
    releases = state.setdefault('releases', {})

    def rel(ns, name):
        return releases.get(ns + '/' + name)

    def parse(args):
        out = {}
        i = 0
        while i < len(args):
            if args[i] in ('-n', '--repo', '--version', '-f', '--timeout'):
                out[args[i]] = args[i + 1]
                i += 2
            else:
                i += 1
        return out

    if cmd == 'history':
        opts = parse(args[2:])
        r = rel(opts.get('-n', 'default'), args[1])
        print(json.dumps([{'revision': 1, 'status': 'deployed'}] if r else []))
    elif cmd == 'status':
        opts = parse(args[2:])
        r = rel(opts.get('-n', 'default'), args[1])
        if not r or r['status'] == 'uninstalled':
            sys.stderr.write('Error: release: not found\n')
            sys.exit(1)
        print(json.dumps({'name': args[1], 'namespace': opts.get('-n', 'default'),
                          'version': r['revision'],
                          'info': {'status': r['status'], 'description': r.get('description', '')},
                          'chart': {'metadata': {'name': r['chart'], 'version': r['version']}}}))
    elif cmd == 'upgrade':
        name, ref = args[2], args[3]
        opts = parse(args[4:])
        ns = opts.get('-n', 'default')
        values = {}
        if '-f' in opts:
            values = json.load(open(opts['-f']))
        state.setdefault('helm_calls', []).append(
            {'op': 'upgrade', 'name': name, 'ns': ns, 'ref': ref, 'repo': opts.get('--repo'),
             'version': opts.get('--version'), 'values': values})
        fails = state.get('fail_next', {}).get(name, [])
        key = ns + '/' + name
        old = releases.get(key)
        if old and old['status'] == 'deployed':
            state.setdefault('helm_history', {}).setdefault(key, {})[str(old['revision'])] = json.loads(json.dumps(old))
        revision = (old or {}).get('revision', 0) + 1
        if fails:
            msg = fails.pop(0)
            save()
            releases[key] = {'revision': revision, 'status': 'failed', 'chart': ref.split('/')[-1],
                             'version': opts.get('--version') or (old or {}).get('version', ''),
                             'values': values, 'description': msg}
            save()
            sys.stderr.write('Error: UPGRADE FAILED: %s\n' % msg)
            sys.exit(1)
        releases[key] = {'revision': revision, 'status': 'deployed', 'chart': ref.split('/')[-1],
                         'version': opts.get('--version') or (old or {}).get('version', ''),
                         'values': values}
        save()
        print('Release %s upgraded' % name)
    elif cmd == 'rollback':
        opts = parse(args[3:])
        ns = opts.get('-n', 'default')
        state.setdefault('helm_calls', []).append({'op': 'rollback', 'name': args[1], 'ns': ns})
        r = rel(ns, args[1])
        if not r:
            sys.stderr.write('Error: release: not found\n')
            sys.exit(1)
        revision = r['revision'] + 1
        prior = state.get('helm_history', {}).get(ns + '/' + args[1], {}).get(args[2])
        if prior:
            r.update(prior)
        r['revision'] = revision
        r['status'] = 'deployed'
        r.pop('description', None)
        save()
        print('Rollback was a success')
    elif cmd == 'uninstall':
        opts = parse(args[2:])
        ns = opts.get('-n', 'default')
        if state.get('uninstall_error'):
            sys.exit('Error: permission denied')
        state.setdefault('helm_calls', []).append({'op': 'uninstall', 'name': args[1], 'ns': ns})
        releases.pop(ns + '/' + args[1], None)
        save()
        print('release "%s" uninstalled' % args[1])
    elif cmd == 'get':
        opts = parse(args[3:])
        r = rel(opts.get('-n', 'default'), args[2])
        if not r or r['status'] == 'uninstalled':
            sys.stderr.write('Error: release: not found\n')
            sys.exit(1)
        print(json.dumps(r.get('values', {})))
    else:
        sys.exit('fake helm cannot ' + ' '.join(args))
else:
    sys.exit('who am I: ' + who)
'''


def hr(name="web", ns="demo", generation=1, chart=None, values=None, interval=None,
       timeout=None, install_retries=None, upgrade_retries=None, status=None,
       annotations=None, deletion=False, finalizers=None, rv="1"):
    spec = {"chart": chart or {"repository": "https://charts.test", "name": "hello",
                               "version": "0.1.0"}}
    if values is not None:
        spec["values"] = values
    if interval is not None:
        spec["interval"] = interval
    if timeout is not None:
        spec["timeout"] = timeout
    if install_retries is not None:
        spec["install"] = {"remediation": {"retries": install_retries}}
    if upgrade_retries is not None:
        spec["upgrade"] = {"remediation": {"retries": upgrade_retries}}
    meta = {"name": name, "namespace": ns, "uid": "uid-" + name, "generation": generation,
            "resourceVersion": rv, "creationTimestamp": "2026-11-20T00:00:00Z"}
    if annotations:
        meta["annotations"] = annotations
    if finalizers:
        meta["finalizers"] = finalizers
    if deletion:
        meta["deletionTimestamp"] = "2026-11-21T00:00:00Z"
    o = {"apiVersion": "helm.amae.io/v1", "kind": "HelmRelease", "metadata": meta, "spec": spec}
    if status is not None:
        o["status"] = status
    return o


def release(name="web", ns="demo", revision=1, version="0.1.0", values=None, status="deployed"):
    return {f"{ns}/{name}": {"revision": revision, "status": status, "chart": "hello",
                             "version": version, "values": values or {}}}


def ready_status(revision=1, version="0.1.0", reason="InstallSucceeded", failures=0,
                 install_failures=0, upgrade_failures=0, generation=1, message=None):
    chart = "hello-" + version
    message = message or ("Installed " + chart + " (revision " + str(revision) + ")")
    return {"observedGeneration": generation, "lastAttemptedRevision": version,
            "failures": failures, "installFailures": install_failures,
            "upgradeFailures": upgrade_failures,
            "history": [{"revision": revision, "chart": chart, "time": "2026-11-20T00:00:10Z"}],
            "conditions": [
                {"type": "Ready", "status": "True", "reason": reason, "message": message,
                 "observedGeneration": generation, "lastTransitionTime": "2026-11-20T00:00:10Z"},
                {"type": "Released", "status": "True", "reason": reason, "message": message,
                 "observedGeneration": generation, "lastTransitionTime": "2026-11-20T00:00:10Z"},
                {"type": "Remediated", "status": "False", "reason": "NotRequired", "message": "",
                 "observedGeneration": generation, "lastTransitionTime": "2026-11-20T00:00:10Z"}]}


class LiveHelm(unittest.TestCase):
    def reconcile(self, hrs, looks=1, releases=None, env=None, **state):
        with tempfile.TemporaryDirectory() as d:
            for name in ("kubectl", "helm"):
                p = Path(d, name)
                p.write_text(FAKE)
                p.chmod(0o755)
            st = {"helmreleases": hrs, "releases": releases or {}, **state}
            sp = Path(d, "state.json")
            sp.write_text(json.dumps(st))
            life = run(Path(ROOT, "operators/helm.amae").read_text(), flags=("--patience=0",),
                           timeout=120,
                           env={"KUBECTL": str(Path(d, "kubectl")), "HELM": str(Path(d, "helm")),
                                "FAKE_STATE": str(sp), "KUBE_CONTEXT": "imagined",
                                "HELM_SINGLE_INSTANCE": "1", "HELM_INTERVAL": "0.001",
                                "HELM_LOOKS": str(looks), **(env or {})})
            if os.environ.get("HELM_TEST_DEBUG"):
                print(life.err, sp.read_text())
            self.assertEqual(life.code, 0, life.err)
            return json.loads(sp.read_text())

    @staticmethod
    def ops(s, op):
        return [c for c in s.get("helm_calls", []) if c["op"] == op]

    @staticmethod
    def conditions(s, name="web"):
        o = [x for x in s["helmreleases"] if x["metadata"]["name"] == name][0]
        return o["status"], {c["type"]: c for c in o["status"].get("conditions", [])}

    def test_install(self):
        s = self.reconcile([hr(values={"greeting": "hi"})])
        (up,) = self.ops(s, "upgrade")
        self.assertEqual((up["ref"], up["repo"], up["version"], up["values"]),
                         ("hello", "https://charts.test", "0.1.0", {"greeting": "hi"}))
        st, conds = self.conditions(s)
        self.assertEqual(conds["Ready"]["status"], "True")
        self.assertEqual(conds["Ready"]["reason"], "InstallSucceeded")
        self.assertEqual(conds["Released"]["status"], "True")
        self.assertEqual(conds["Remediated"]["reason"], "NotRequired")
        self.assertEqual(st["lastAttemptedRevision"], "0.1.0")
        self.assertEqual((st["failures"], st["installFailures"], st["upgradeFailures"]),
                         (0, 0, 0))
        self.assertEqual(st["history"][0]["revision"], 1)
        self.assertEqual(st["observedGeneration"], 1)
        self.assertEqual([e["reason"] for e in s.get("events", [])], ["InstallSucceeded"])
        self.assertEqual(s["releases"]["demo/web"]["status"], "deployed")

    def test_second_look_is_quiet(self):
        s = self.reconcile([hr(values={"greeting": "hi"})], looks=2)
        self.assertEqual(len(self.ops(s, "upgrade")), 1)
        self.assertEqual(len(s.get("status_writes", [])), 1)

    def test_upgrade_on_values_change(self):
        r = release(values={"greeting": "hi"})
        h = hr(generation=2, values={"greeting": "hello"}, status=ready_status())
        s = self.reconcile([h], releases=r)
        (up,) = self.ops(s, "upgrade")
        self.assertEqual(up["values"], {"greeting": "hello"})
        st, conds = self.conditions(s)
        self.assertEqual(conds["Ready"]["reason"], "UpgradeSucceeded")
        self.assertEqual(st["history"][0]["revision"],
                         s["releases"]["demo/web"]["revision"])
        self.assertEqual(st["history"][1]["revision"], 1)
        self.assertEqual(st["observedGeneration"], 2)

    def test_failed_upgrade_rolls_back_and_retries(self):
        r = release()
        h = hr(generation=2, values={"greeting": "v2"}, upgrade_retries=1,
               status=ready_status())
        s = self.reconcile([h], releases=r, fail_next={"web": ["timed out waiting"]})
        self.assertEqual([c["op"] for c in s["helm_calls"]],
                         ["upgrade", "rollback", "upgrade"])
        st, conds = self.conditions(s)
        self.assertEqual(conds["Ready"]["status"], "True")
        self.assertEqual(conds["Ready"]["reason"], "UpgradeSucceeded")
        self.assertEqual(conds["Remediated"]["status"], "True")
        self.assertEqual(conds["Remediated"]["reason"], "RolledBack")
        self.assertEqual(st["upgradeFailures"], 1)
        self.assertEqual(st["failures"], 0)
        self.assertEqual(st["history"][0]["revision"],
                         s["releases"]["demo/web"]["revision"])

    def test_upgrade_exhaustion_stalls_and_request_requeues(self):
        r = release()
        base = hr(generation=2, values={"greeting": "v2"}, upgrade_retries=1,
                  status=ready_status())
        look2 = copy.deepcopy(base)
        look3 = copy.deepcopy(base)
        look3["metadata"]["annotations"] = {"reconcile.fluxcd.io/requestedAt":
                                            "2026-11-21T00:00:01Z"}
        s = self.reconcile([], looks=3, releases=r, hr_looks=[[base], [look2], [look3]],
                           fail_next={"web": ["t1", "t2"]})
        # The request requeued the stalled release and the retried upgrade won.
        self.assertEqual(len(self.ops(s, "upgrade")), 3)
        st, conds = self.conditions(s)
        self.assertEqual(conds["Ready"]["reason"], "UpgradeSucceeded")

    def test_install_failure_uninstalls_and_retries(self):
        h = hr(values={"greeting": "hi"}, install_retries=1)
        s = self.reconcile([h], fail_next={"web": ["bad chart"]})
        self.assertEqual([c["op"] for c in s["helm_calls"]],
                         ["upgrade", "uninstall", "upgrade"])
        st, conds = self.conditions(s)
        self.assertEqual(conds["Ready"]["status"], "True")
        self.assertEqual(conds["Remediated"]["reason"], "RetriedAfterUninstall")
        self.assertEqual(st["installFailures"], 1)
        self.assertEqual(st["failures"], 0)

    def test_install_exhaustion_stalls(self):
        h = hr(values={"greeting": "hi"}, install_retries=1)
        s = self.reconcile([h], fail_next={"web": ["a", "b"]})
        self.assertEqual([c["op"] for c in s["helm_calls"]],
                         ["upgrade", "uninstall", "upgrade", "uninstall"])
        st, conds = self.conditions(s)
        self.assertEqual(conds["Ready"]["reason"], "InstallStalled")
        self.assertEqual((st["failures"], st["installFailures"]), (1, 2))
        self.assertEqual(s["releases"], {})

    def test_delete_uninstalls_and_removes_finalizer(self):
        h = hr(finalizers=["finalizers.helm.amae.io"], deletion=True)
        s = self.reconcile([h], releases=release())
        self.assertEqual([c["op"] for c in s.get("helm_calls", [])], ["uninstall"])
        self.assertEqual(s.get("status_writes", []), [])
        (patch,) = s["finalizer_patches"]
        self.assertEqual(patch["finalizers"], [])
        self.assertEqual(s["releases"], {})
        self.assertEqual([e["reason"] for e in s.get("events", [])], ["Uninstalled"])

    def test_stalled_release_skips_interval_looks(self):
        base = hr(generation=2, values={"greeting": "v2"}, upgrade_retries=1,
                  status=ready_status())
        stalled = self.reconcile([copy.deepcopy(base)], releases=release(),
                                 fail_next={"web": ["t1", "t2"]})["helmreleases"][0]
        s = self.reconcile([stalled], looks=2, releases=release(
            revision=1, values={"greeting": "v2"}, status="failed"))
        self.assertEqual(self.ops(s, "upgrade"), [])
        self.assertEqual(s.get("status_writes", []), [])

    def test_uninstall_failure_keeps_finalizer(self):
        obj = hr(finalizers=['other.example/finalizer', 'finalizers.helm.amae.io'], deletion=True)
        s = self.reconcile([obj], releases=release(), uninstall_error=True)
        self.assertEqual(s['helmreleases'][0]['metadata']['finalizers'], obj['metadata']['finalizers'])
        self.assertEqual(s.get('finalizer_patches', []), [])

    def test_values_preserve_boolean_null_and_shell_text(self):
        values = {'enabled': True, 'disabled': False, 'nullable': None,
                  'nested': {'message': "a' $(false) `false`"}}
        s = self.reconcile([hr(values=values)])
        self.assertEqual(self.ops(s, 'upgrade')[0]['values'], values)

    def test_oci_reference(self):
        s = self.reconcile([hr(chart={'oci': 'oci://registry.test/hello', 'version': '0.1.0'})])
        self.assertEqual(self.ops(s, 'upgrade')[0]['ref'], 'oci://registry.test/hello')

    def test_upgrade_exhaustion_always_rolls_back(self):
        s = self.reconcile([hr(generation=2, upgrade_retries=1, status=ready_status())],
                           releases=release(), fail_next={'web': ['first', 'second']})
        self.assertEqual([c['op'] for c in s['helm_calls']], ['upgrade', 'rollback'] * 2)
        status, conds = self.conditions(s)
        self.assertEqual(conds['Ready']['reason'], 'UpgradeStalled')
        self.assertEqual(conds['Remediated']['status'], 'True')
        self.assertEqual(status['upgradeFailures'], 2)
        self.assertEqual(s['releases']['demo/web']['status'], 'deployed')
        self.assertEqual(len(s['status_writes']), 1)

    def test_same_request_does_not_reset_stall_after_restart(self):
        obj = hr(install_retries=0, annotations={'reconcile.fluxcd.io/requestedAt': 'once'})
        first = self.reconcile([obj], fail_next={'web': ['bad']})
        stalled = first['helmreleases'][0]
        second = self.reconcile([stalled], looks=2)
        self.assertEqual(second.get('helm_calls', []), [])
        self.assertEqual(second.get('status_writes', []), [])
        stalled['metadata']['generation'] += 1
        third = self.reconcile([stalled])
        self.assertEqual(self.conditions(third)[1]['Ready']['status'], 'True')


class RaceAgainstTheController(unittest.TestCase):
    """The #934 interleavings, run against the compiled controller."""

    def reconcile(self, hrs, **kwargs):
        return LiveHelm.reconcile(self, hrs, **kwargs)

    def test_concurrent_writer_mid_reconcile_cannot_tear(self):
        """A concurrent writer bumps the object between the controller's read
        and its write. The preconditioned write conflicts; the controller
        re-reads, recomputes and lands a coherent status in one piece."""
        concurrent = {"conditions": [
                          {"type": "Ready", "status": "True", "reason": "UpgradeSucceeded",
                           "message": "stale ready from a concurrent writer",
                           "observedGeneration": 1, "lastTransitionTime": "2026-11-20T00:00:00Z"}],
                      "failures": 0, "installFailures": 41,
                      "history": [{"revision": 99, "chart": "bogus-9.9.9",
                                   "time": "2026-11-20T00:00:00Z"}]}
        s = self.reconcile([hr(values={"greeting": "hi"})],
                           inject={"bump": 1, "concurrent_patch": concurrent})
        writes = s["status_writes"]
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0]["failed"], "conflict")
        (o,) = [x for x in s["helmreleases"] if x["metadata"]["name"] == "web"]
        st, conds = LiveHelm.conditions(s)
        # The final status says what Helm said, not what the writer said.
        self.assertEqual(conds["Ready"]["reason"], "InstallSucceeded")
        self.assertEqual(st["installFailures"], 0)  # operation facts, not the bogus counter
        # ...and the recompute was made from the fresh read: the writer's
        # bogus history entry survived under the new one.
        self.assertEqual(st["history"][1]["revision"], 99)

    def test_failing_api_retries_and_recovers(self):
        s = self.reconcile([hr(values={"greeting": "hi"})], fail_writes_left=2)
        writes = s["status_writes"]
        self.assertEqual(len(writes), 3)
        self.assertEqual([w.get("failed") for w in writes[:2]], ["injected api failure"] * 2)
        st, conds = LiveHelm.conditions(s)
        self.assertEqual(conds["Ready"]["status"], "True")

    def test_when_every_write_fails_the_old_status_stays(self):
        """With one write there is no half: if it never lands, the object
        keeps the previous, coherent status."""
        s = self.reconcile([hr(values={"greeting": "hi"})], fail_writes_left=99)
        (o,) = [x for x in s["helmreleases"] if x["metadata"]["name"] == "web"]
        self.assertNotIn("status", o)
        self.assertEqual(o["metadata"]["resourceVersion"], "7")
        self.assertEqual(s.get("events", []), [])

    def test_conflict_reobserves_changed_helm_state(self):
        s = self.reconcile([hr()], inject={'bump': 1, 'helm_state': 'failed'})
        status, conds = LiveHelm.conditions(s)
        self.assertEqual(s['status_writes'][0]['failed'], 'conflict')
        self.assertEqual(conds['Ready']['status'], 'False')
        self.assertEqual(conds['Ready']['reason'], 'ReleaseNotReady')
        self.assertEqual(status['history'][0]['status'], 'failed')
        self.assertEqual(len(LiveHelm.ops(s, 'upgrade')), 1)

    def test_generation_change_does_not_label_old_result_as_new(self):
        s = self.reconcile([hr()], inject={'bump': 1, 'generation': 2})
        self.assertEqual(len(s['status_writes']), 1)
        self.assertEqual(s['status_writes'][0]['failed'], 'conflict')
        self.assertEqual(s['helmreleases'][0].get('status', {}), {})

    def test_same_concurrent_ready_writer_as_split_patch_model(self):
        concurrent = {'conditions': [ready('True', 'ConcurrentReady', 'stale', 1)]}
        s = self.reconcile([hr(install_retries=0)], fail_next={'web': ['bad chart']},
                           inject={'bump': 1, 'concurrent_patch': concurrent})
        status, conds = LiveHelm.conditions(s)
        self.assertEqual(conds['Ready']['reason'], 'InstallStalled')
        self.assertEqual(conds['Ready']['status'], 'False')
        self.assertEqual(status['installFailures'], 1)
        self.assertEqual(s['status_writes'][0]['failed'], 'conflict')
        self.assertEqual(len([w for w in s['status_writes'] if 'status' in w]), 1)


# ---------------------------------------------------------------------------
# The scripted model of the Go helper: fluxcd/pkg runtime/patch @ e270089.
# ---------------------------------------------------------------------------

class Conflict(Exception):
    pass


class Store:
    """The API server: merge patches, optimistic-lock precondition, history of
    every stored revision so a watcher can be shown what it would have seen."""

    def __init__(self, obj):
        self.obj = copy.deepcopy(obj)
        self.rv = int(obj["metadata"]["resourceVersion"])
        self.history = [self.snapshot()]

    def snapshot(self):
        s = copy.deepcopy(self.obj)
        s["metadata"]["resourceVersion"] = str(self.rv)
        return s

    def get(self):
        return self.snapshot()

    def write_status_merge(self, patch, precondition=None):
        if precondition is not None and str(precondition) != str(self.rv):
            raise Conflict()
        deep = self.obj.setdefault("status", {})
        for k, v in patch.get("status", {}).items():
            deep[k] = copy.deepcopy(v)
        self.rv += 1
        self.history.append(self.snapshot())


class GoHelper:
    """Subset of patch.Helper.Patch for one owned Ready condition, against a fresh read
    with an optimistic lock (patch.go:271-344); then metadata/spec; then the
    rest of status as a merge computed from the reconcile-start snapshot with
    no precondition at all (patch.go:251-260, utils.go:91-99)."""

    def __init__(self, store, before):
        self.store = store
        self.before = copy.deepcopy(before)

    def patch(self, after, between=None, fail=None):
        errors = []
        conditions_ok = False
        unchanged = self.before["status"].get("conditions") == after["status"].get("conditions")
        conditions_ok = unchanged
        for _ in range(0 if unchanged else 5):
            latest = self.store.get()
            conditions = copy.deepcopy(after["status"]["conditions"])
            patch = {"status": {"conditions": conditions}}
            if fail == "conditions":
                break
            try:
                self.store.write_status_merge(patch, precondition=latest["metadata"]["resourceVersion"])
                conditions_ok = True
                break
            except Conflict:
                continue
        if not conditions_ok:
            errors.append("conditions patch failed")
        # The race window: a concurrent writer lands here, between the
        # conditions and the rest of the status.
        if between:
            between(self.store)
        rest_before = {k: v for k, v in self.before["status"].items() if k != "conditions"}
        rest_after = {k: v for k, v in after["status"].items() if k != "conditions"}
        merge = {k: copy.deepcopy(v) for k, v in rest_after.items()
                 if rest_before.get(k) != v}
        if fail == "rest":
            errors.append("rest patch failed")
        else:
            if merge:
                self.store.write_status_merge({"status": merge})
        return errors


def ready(status, reason, message, generation):
    return {"type": "Ready", "status": status, "reason": reason, "message": message,
            "observedGeneration": generation, "lastTransitionTime": "2025-05-27T21:27:13Z"}


BASE = {"apiVersion": "helm.amae.io/v1", "kind": "HelmRelease",
        "metadata": {"name": "web", "namespace": "demo", "generation": 2,
                     "resourceVersion": "2292285", "uid": "u"},
        "spec": {"chart": {"repository": "https://charts.test", "name": "hello",
                           "version": "0.2.0"}},
        "status": {}}


def deployed_rev1():
    obj = copy.deepcopy(BASE)
    obj["status"] = {
        "observedGeneration": 2, "lastAttemptedRevision": "hello-0.1.0",
        "failures": 0, "installFailures": 0, "upgradeFailures": 0,
        "history": [{"revision": 1, "chart": "hello-0.1.0"}],
        "conditions": [ready("True", "UpgradeSucceeded", "Upgraded hello-0.1.0",
                             2)]}
    return obj


def reconcile_model(store, failed, attempted, note, between=None, fail=None,
                    skip_helm=False):
    """What a Flux-style reconciler hands to the helper: the conditions and
    the counters of the outcome it observed, all against the start snapshot."""
    before = store.get()
    after = copy.deepcopy(before)
    st = after["status"]
    gen = before["metadata"]["generation"]
    if skip_helm:
        pass  # the stalled early-return: nothing observed, mark carried over
    elif failed:
        st["conditions"] = [ready("False", note, note + ": timed out waiting", gen)]
        st["failures"] = before["status"].get("failures", 0) + 1
        st["lastAttemptedRevision"] = attempted
    else:
        st["conditions"] = [ready("True", "UpgradeSucceeded", "Upgraded " + attempted, gen)]
        st["failures"] = 0
        st["lastAttemptedRevision"] = attempted
        st["history"] = ([{"revision": before["status"]["history"][0]["revision"] + 1,
                           "chart": attempted}] + before["status"].get("history", []))
    st["observedGeneration"] = gen
    return GoHelper(store, before).patch(after, between=between, fail=fail)


class FluxModel(unittest.TestCase):
    def test_original_git_repository_intermediate_revision(self):
        # The reported #934 object sequence, with symbolic artifact revisions.
        before = {"metadata": {"resourceVersion": "2292286"}, "status": {
            "artifact": {"revision": "old", "url": "https://source/old.tar.gz"},
            "conditions": [ready("Unknown", "Progressing", "building new", 2)],
            "observedGeneration": 2}}
        store = Store(before)
        after = copy.deepcopy(before)
        after["status"]["conditions"] = [ready("True", "Succeeded", "stored new", 2)]
        after["status"]["artifact"] = {"revision": "new", "url": "https://source/new.tar.gz"}
        seen = []
        self.assertEqual(GoHelper(store, before).patch(after, between=lambda s: seen.append(s.get())), [])
        self.assertEqual(seen[0]["metadata"]["resourceVersion"], "2292287")
        self.assertEqual(seen[0]["status"]["conditions"][0]["status"], "True")
        self.assertEqual(seen[0]["status"]["artifact"]["revision"], "old")
        self.assertEqual(store.get()["metadata"]["resourceVersion"], "2292288")
        self.assertEqual(store.get()["status"]["artifact"]["revision"], "new")

    def test_watcher_sees_ready_true_with_the_old_revision(self):
        """A Helm-shaped analogue of the issue: the conditions land first, the rest of the status
        later, and a watcher keyed on Ready acts on stale release data."""
        store = Store(deployed_rev1())
        seen = []

        def watcher(s):
            seen.append(s.get())

        errors = reconcile_model(store, failed=False, attempted="hello-0.2.0",
                                 note="UpgradeFailed", between=watcher)
        self.assertEqual(errors, [])
        torn = [s for s in seen
                if s["status"]["conditions"][0]["status"] == "True"
                and "0.2.0" in s["status"]["conditions"][0]["message"]
                and s["status"]["lastAttemptedRevision"] == "hello-0.1.0"]
        self.assertTrue(torn, "the watcher never saw the torn state")
        final = store.get()
        self.assertEqual(final["status"]["lastAttemptedRevision"], "hello-0.2.0")

    def test_concurrent_ready_writer_between_patches_leaves_wrong_final_ready(self):
        store = Store(deployed_rev1())
        concurrent = {"conditions": [ready("True", "ConcurrentReady", "stale", 1)]}
        errors = reconcile_model(store, failed=True, attempted="hello-0.2.0",
                                 note="InstallStalled",
                                 between=lambda s: s.write_status_merge({"status": concurrent}))
        self.assertEqual(errors, [])
        final = store.get()['status']
        self.assertEqual(final['conditions'][0]['status'], 'True')
        self.assertEqual(final['failures'], 1)
        self.assertEqual(final['lastAttemptedRevision'], 'hello-0.2.0')

    def test_conditions_failure_keeps_ready_true_while_release_failed(self):
        """The conditions write fails (its retry loop exhausted); the rest of
        the status still lands. Ready stays True for a release that failed."""
        store = Store(deployed_rev1())
        errors = reconcile_model(store, failed=True, attempted="hello-0.2.0",
                                 note="UpgradeFailed", fail="conditions")
        self.assertEqual(errors, ["conditions patch failed"])
        final = store.get()
        self.assertEqual(final["status"]["conditions"][0]["status"], "True")
        self.assertEqual(final["status"]["failures"], 1)
        self.assertEqual(final["status"]["lastAttemptedRevision"], "hello-0.2.0")

    def test_failed_rest_patch_leaves_a_stall_without_its_evidence(self):
        """The stall's conditions land; the write that would record the
        failure never does. The next reconcile sees the stall and skips Helm,
        so the object asserts a failure the rest of its status never heard
        of, indefinitely."""
        store = Store(deployed_rev1())
        errors = reconcile_model(store, failed=True, attempted="hello-0.2.0",
                                 note="UpgradeStalled", fail="rest")
        self.assertEqual(errors, ["rest patch failed"])
        # the next reconcile: stalled, so Helm is not asked again
        reconcile_model(store, failed=False, attempted="hello-0.2.0",
                        note="UpgradeStalled", skip_helm=True)
        final = store.get()
        self.assertEqual(final["status"]["conditions"][0]["reason"], "UpgradeStalled")
        self.assertEqual(final["status"]["failures"], 0)
        self.assertEqual(final["status"]["lastAttemptedRevision"], "hello-0.1.0")


if __name__ == "__main__":
    unittest.main()
