"""Render with kubectl alone: no cluster, YAML library or standalone kustomize."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def render(path):
    return subprocess.check_output(['kubectl', 'kustomize', str(path)], cwd=ROOT, text=True)

def field(doc, name):
    return re.search(r'^  ' + name + r': (.+)$', doc, re.M).group(1)

@unittest.skipUnless(shutil.which('kubectl'), 'kubectl is absent')
class Deploy(unittest.TestCase):
    def test_every_overlay(self):
        docker = (ROOT / 'Dockerfile').read_text()
        image = re.search(r'newTag: (.+)', (ROOT / 'deploy/images/kustomization.yaml').read_text())[1]
        for overlay in sorted((ROOT / 'deploy/overlays').iterdir()):
            with self.subTest(overlay=overlay.name):
                docs = render(overlay).split('---\n')
                deployments = [d for d in docs if '\nkind: Deployment\n' in d]
                bindings = [d for d in docs if re.search(r'^kind: (ClusterRoleBinding|RoleBinding)$', d, re.M)]
                accounts = {(field(d, 'name'), field(d, 'namespace')) for d in docs if '\nkind: ServiceAccount\n' in d}
                expected = 2 if overlay.name == 'minimal' else 10 if overlay.name == 'default-scheduler' else 9
                self.assertEqual(len(deployments), expected)
                for doc in deployments:
                    sa = re.search(r'serviceAccountName: (.+)', doc)[1]
                    ns = field(doc, 'namespace')
                    self.assertIn((sa, ns), accounts)
                    self.assertTrue(any(re.search(r'subjects:\n- kind: ServiceAccount\n  name: '+re.escape(sa)+r'\n  namespace: '+re.escape(ns)+r'\n', b) for b in bindings), sa)
                    for binary in re.findall(r'/opt/amae/bin/([\w-]+)', doc):
                        self.assertIn('-o /out/' + binary, docker)
                    self.assertEqual(re.findall(r'image: (.+)', doc), ['ghcr.io/tym83/amae:' + image])
                self.assertFalse(any('name: amaenetes-helm\n' in b and '\nkind: RoleBinding\n' in b for b in bindings))
                if overlay.name == 'default-scheduler':
                    self.assertTrue(any('\nkind: Role\n' in d and 'namespace: kube-system' in d for d in docs))

    def test_generated_manifests_are_current(self):
        subprocess.run(['python3', 'tools/render-deploy.py', '--check'], cwd=ROOT, check=True)

    def test_target_binding_and_pinned_image(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'deploy/overlays') as tmp:
            Path(tmp, 'kustomization.yaml').write_text('''apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
- ../default
components:
- ../../components/helm-target
images:
- name: ghcr.io/tym83/amae
  newTag: test-pinned
patches:
- target:
    kind: RoleBinding
    name: amaenetes-helm
  patch: |-
    - op: replace
      path: /metadata/namespace
      value: shop
''')
            docs = render(tmp).split('---\n')
        binding, = [d for d in docs if '\nkind: RoleBinding\n' in d and 'name: amaenetes-helm\n' in d]
        self.assertIn('metadata:\n  name: amaenetes-helm\n  namespace: shop', binding)
        self.assertIn('subjects:\n- kind: ServiceAccount\n  name: helm\n  namespace: amaenetes', binding)
        self.assertEqual(re.findall(r'image: (.+)', '\n'.join(docs)), ['ghcr.io/tym83/amae:test-pinned'] * 9)
