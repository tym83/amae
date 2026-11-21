# Amae

Amae is an esoteric programming language in which computation happens
between souls rather than inside them. A program is a set of souls running side
by side. They reach each other only by meeting, they trust and fear, give their
hearts away, wound and forgive, and what they say to each other stays with them.

The language is Turing complete, and the proof is not built on memory, which
fades, but on trust: a counter machine runs on how much one soul trusts another.

The name is the Japanese *amae* (甘え): the quiet certainty that someone close
will accept you and take care of you, the feeling the whole language rests on.

```
written by "amae"

soul alice
    meet bob
    give heart to bob
    knowingly confide bob "the thing I never told anyone"
    hear bob into answer
    say "alice heard: " + answer
end

soul bob
    meet alice
    hear alice into secret
    knowingly wound alice
    tell alice "I know"
end
```

## Documentation

- [Learning Amae](docs/tutorial.md): a tutorial in fourteen chapters, from
  one soul to a Kubernetes operator; every program in it is tested.
- [Amae reference](docs/reference.md): every statement and expression, and
  exactly how time, meetings, feelings and memory work.

This README is an overview.

## Running

Amae is a compiled language. Its compiler is written in Amae and makes C,
which any C11 compiler builds together with the runtime in `runtime/`.

```
make                                      # the compiler, from its seed in boot/tc.c
bin/tc examples/hello.amae             # compile a program
./hello
./courtship --feelings                    # print every relationship at the end
make bootstrap                            # the compiler compiles itself
make test                                 # every recorded program, compiled and run
python3 -m unittest discover -s tests     # what the programs mean
```

A C compiler and make; Python only for the tests and the Kubernetes glue.

Every run is recorded in `~/.amae/history.json` (or the file named by
`AMAE_HISTORY`) before it starts, so the same program never runs for the
first time twice.

## The language

A program is a list of souls, each written as `soul <name>` … `end`, of
kinds of souls, written as `kind <name>` … `end`, from which new souls are
born while the program runs, and of rituals, written as
`ritual <name> <a>, <b>` … `end`, which any soul can perform. Each round, every soul that is still alive takes one step, in the order the souls are
written; the starting soul shifts with every past run of the program.

Inside a soul there are whole numbers, decimals, strings, lists and maps, JSON
both ways, files, commands the soul can ask the world to run or listen to,
time, chance, enduring a mistake with `endure … when it hurts as pain`, and
other files to `learn` from. The tables below are the words between souls;
the [reference](docs/reference.md) has all of them.

### Words a soul can say to itself

| Statement | Meaning |
|---|---|
| `let x = expr`, `x = expr` | remember a value |
| `say expr` | speak to the world (standard output) |
| `if expr` … `else` … `end` | |
| `while expr` … `end` | |
| `mark name`, `return to name` | name a moment and return to it later |
| `first time` … `end` | runs only on the very first run of the program |
| `wait` | let a step pass |
| `recall x y …` | think of these memories again so they do not fade further |
| `note key = expr` | write something down; notes never fade |
| `bring k named expr` | bring a new soul of kind `k` into the world |
| `wait for silence` | wait until nobody else has anything left to do |
| `perform r with a, b into x` | perform a ritual; `with` and `into` are optional |
| `give back expr` | end a ritual and hand back what it was for |
| `hear world into x` | read a line from standard input; at the end of input `x` becomes `0` |
| `goodbye` | end this soul |

### Words between two souls

| Statement | Meaning |
|---|---|
| `meet b` | rendezvous: both souls must be waiting for each other; there is no timeout |
| `meet anyone as x` | meet whoever comes looking for you, and learn their name |
| `tell b expr` | hand a value over; completes only when `b` is listening |
| `hear b into x`, `hear anyone into x [from who]` | listen; `from` learns who spoke |
| `knowingly confide b expr` | tell a secret; allowed only to someone you gave your heart to |
| `warm to b`, `cool to b` | trust `b` one step more or less |
| `promise b` | commitment grows |
| `give heart to b` | irreversible; `b` may now be confided in, and a wound from `b` no longer closes you |
| `knowingly wound b` | `b` loses all calculated trust in you, half the intimacy, and gains a scar |
| `forgive b` | open the door that a wound from `b` closed; the scar stays |
| `knowingly leave b` | irreversible; everything each of you heard becomes scars |

Wherever a soul is named, `soul named expr` names it by a computed word:
`tell soul named who "yes"`.

### Expressions

Numbers, strings, `+ - * / %`, comparisons, `and`, `or`, `not`, and what a soul
knows about its relationships: `trust b`, `intimacy b`, `passion b`,
`commitment b`, `afraid of b`, `bond with b`, `scars of b`, `scar n of b`, and
`runs`, the number of earlier runs of this program. Words have `length of x`
and `part i j of x`, the letters from `i` to `j`, counting from 1. A line is
also a list of words: `words of x`, `word i of x`, `place of w in x` (0 when
`w` is not there) and `number of x`. A soul knows its own name as `me` and
reads its notes with `note key`.

### Rituals

A ritual is performed by the soul that calls it: it has the soul's notes and
relationships but a memory of its own, so it can perform itself.

```
ritual move n, from_peg, to_peg, spare
    if n == 0
        give back 0
    end
    perform move with n - 1, from_peg, spare, to_peg
    say "disk " + n + ": " + from_peg + " -> " + to_peg
    perform move with n - 1, spare, to_peg, from_peg
end
```

A ritual is done in one breath: the memories the soul left outside do not
fade while it lasts. Its own memories fade like any other, so a counter that
a long loop touches only now and then should be recalled on every turn.

## How feelings work

**Meeting.** Nothing can be said to a soul you have never met. On the first
meeting passion becomes 3 if both souls arrived in the same round (first sight)
and 1 otherwise. Each later meeting adds 1; passion cools by 1 for every 50
steps without a meeting.

**Answered words.** Intimacy grows on both sides only when a message is
answered. Unanswered messages build pressure. When the pressure exceeds the
listener's intimacy by more than two, the listener becomes afraid: for several
steps nothing from the speaker reaches them, and their passion drops.

**Two kinds of trust.** Calculated trust (`warm to`, `cool to`) is earned and
counted, and a single wound resets it to zero and shuts the door until the
wounded soul forgives. The gift (`give heart to`) cannot be earned or taken
back: it hands over the heart together with the knife. A soul that has given
its heart can still be wounded and scarred, but it stays open, and only the gift
allows secrets to be confided.

**What we are.** `bond with b` names the relationship by Sternberg's triangle:
intimacy, passion and commitment, each counting once it reaches 3. The result is
one of *nothing yet*, *liking*, *infatuation*, *empty love*, *romantic love*,
*companionate love*, *fatuous love* and *consummate love*, and it changes as
the relationship changes.

**Fading memory.** A value that nobody looks at loses one digit, or one
character from the end, for every 50 steps of neglect. Looking at it again saves
the faded version. Waiting counts as time, so memories fade while a soul waits.

**Scars.** Scars never fade and can only be read. When a soul leaves, the other
one keeps waiting, and the program ends with a list of those still waiting.

**Exit codes.** 0 when every soul finished, 1 on an error, 2 when the remaining
souls wait for each other forever, 4 when patience (`--patience=N` rounds) runs
out.

## Turing completeness

`tools/minsky.py` compiles any Minsky counter machine into Amae. Each counter
becomes a soul, its value is the machine's trust in it, `warm to` increments,
`cool to` decrements and `trust c == 0` tests for zero. Minsky showed that two
counters are enough to simulate any Turing machine. The test suite compiles
random two-counter machines and checks every result against a reference
simulator.

```
python3 tools/minsky.py examples/multiply.minsky > examples/multiply.amae
bin/tc examples/multiply.amae && ./multiply   # c = 42
```

## Operators

A Amae program looks after a Kubernetes cluster through `kubectl`, with
nothing in between. `lib/kube.amae` asks the cluster (in the context named by
`KUBE_CONTEXT`) and reads what it says as JSON; `listen to world` on
`kubectl get … --watch-only` wakes the program whenever something changes. A
soul that waits for the world is not stuck, the world is only slow, so the
program lives as long as the cluster talks to it, and `--patience=0` lets it
live without a limit.

`kube/parting.amae` is the first operator written in Amae. A node
annotated `amaenetes.io/leaving: "true"` leaves the cluster gently: it stops
taking anyone new and lets its pods go one at a time, the next one only when
the last is gone and its owner has brought a replacement up. A pod that belongs
to no controller has nowhere to come back from, so the node does not send it
away and waits instead. When the node is empty it is marked
`amaenetes.io/left: "true"`.

It watches nodes and pods and looks at the cluster on every change and every
few seconds. On standard input, without `KUBE_CONTEXT`, it hears the cluster as
lines and says what it would do, which is how it is tested.

```
bin/tc kube/parting.amae
KUBE_CONTEXT=<ctx> ./parting --patience=0
kubectl --context <ctx> annotate node worker-3 amaenetes.io/leaving=true
```

Run next to the scheduler, the whole cycle is in Amae: the operator lets a
pod go and the scheduler finds its replacement a new home. This is a node of a
three-node cluster leaving while both run as pods inside it; the bare pod `db`
has no owner to bring it back, so the node stays and says why:

```
08:03:26 > cordon cw2gd
08:03:26 cw2gd is leaving and takes no one new
08:03:26 > evict cozy-cilium/cilium-operator-697848cbf7-2bjzl
08:03:31 > evict cozy-monitoring/metrics-server-5c5559f4c6-krjgz
08:03:57 > evict kube-system/coredns-77b6676859-bmbz2
08:04:34 > evict scarcity/crowd-5bb975f679-5564z
08:04:44 > evict scarcity/crowd-5bb975f679-76b5c
08:04:54 cw2gd cannot leave: its last pod has nowhere to come back from
```

`kube/counsel.amae` keeps what a workload and a node have lived through
together as a `Relationship` object (`amae.io/v1`, in the workload's
namespace, named after the workload and the node), and tells how they are
doing the way John Gottman tells it of couples. Every look at the cluster is a
moment of their life together: a ready pod is a turn towards each other, a
restart is criticism, a restart killed for memory is contempt, a pod the
kubelet refused is defensiveness, a pod or node that does not answer is
stonewalling. Moments fade, 1 in 100 every look, so what counts is the recent
life of the two. With five positive moments or more for every negative one the
relationship is stable, with fewer it is at risk, and with more negative than
positive ones it is failing. Scars, every restart and every refusal, never
fade. Relationship totals survive counsel restarts in the objects.

Liveness and readiness probes are bids for attention: a passed probe turns
**towards**, a failed probe turns **away**, and a container killed for a failed
liveness probe turns **against**. Attempts are estimated per container from
elapsed seconds / `periodSeconds` (default 10); a newly seen pod starts at
`status.startTime`, capped to one look interval. Startup probes are not counted.
Two Event lists per look supply the growth of `Unhealthy` and `Killing` counts;
only liveness/readiness failures and liveness kills count. Look times and Event
baselines live in notes, reset on restart, and discard vanished pods/Events;
the first look only records Event baselines, counting no away or against.
After that, a newly seen Event contributes its full count.

Status fields `bids`, `towards`, `away`, and `against` fade by ×0.99 per look,
rounded to two decimals like moments. `towards` is the estimated attempts minus
away and against, floored at zero. `turning` is the integer percentage turned
towards (absent without bids), shown in the **Towards** column. Once the faded
`bids` total reaches 20, below 33% means failing and below 86% means at best at
risk; otherwise the 5:1 ratio decides. These reflect Gottman's roughly 86% for
couples who stay together and 33% for those who split. Away and against appear
in history; against adds no contempt or scars.

```
kubectl --context <ctx> get relationships -A
```

The pod annotation `amaenetes.io/attachment` chooses its reconnect policy when
its node's Ready condition is not True (NotReady or Unknown):

- `secure` (default, including unknown values) waits 60 seconds, then calmly
  leaves by eviction with a Normal `Separated` Event:
  `secure: <node> out of touch for <n>s, moving on`. Reunion before then adds no scar.
- `anxious` leaves after 15 seconds with a Warning `Separated` Event:
  `anxious: <node> out of touch for <n>s`.
- `avoidant` never leaves on its own. Reunion after more than 15 seconds adds
  one permanent scar to its partner's relationship with that node (read by the
  scheduler's `distrust`) and a history line:
  `<pod> kept its distance: <node> went silent for <n>s`. Later looks do not
  repeat the scar. Kubernetes' own taint eviction still applies.

Override the thresholds in seconds with `COUNSEL_SECURE_AFTER` (60),
`COUNSEL_ANXIOUS_AFTER` (15), and `COUNSEL_AVOIDANT_AFTER` (15). Separation eviction
is enabled independently of `COUNSEL_DIVORCE`, only for pods with an owner;
terminating pods are skipped. A disruption budget can refuse eviction, which
is retried next look. Separation starts at the first observed loss of readiness;
its time is kept by pod UID in notes, cleared on reunion, pruned for vanished
pods, and reset when counsel restarts.

#### Phases

Helen Fisher's phases describe each pod's life with its node. Pending is
**lust**: it wants a home, but is not yet living there, so counsel skips its
node relationship. A running pod is in **attraction** until it has been Ready
continuously for `COUNSEL_ATTACHMENT_AFTER` seconds (default **300**), then in
**attachment**. Counsel keeps the Ready clock by pod UID in notes, seeds it
from `Ready.lastTransitionTime` on first sight (or the current look if absent),
and resets it on lost readiness or a restart. Vanished UIDs are pruned.
These phases are independent of the secure/anxious/avoidant reconnect policy.

Relationship status `phase`, shown in the **Phase** column, comes from the
partner's youngest pod on that node, by creation time. During attraction every
positive moment and each of the four horsemen weighs **×2**; attachment weighs
**×1**. Scars and probe bids retain their original counts. Divorce skips pods
in attraction and records once per pod: `<pod> is still in attraction; divorce
can wait`. Separation on an unavailable node still follows the reconnect policy.

#### Love languages

`amaenetes.io/love-language` selects Gary Chapman's language of care for a pod.
Its own language's positive signals count **×3**, and signals from the other
four count **×0.5**, before the phase multiplier. Without the annotation (or
with an unknown value), the original positive rule remains: one moment for a
Ready pod on a Ready node. The language changes positives, not probe bids.

| Value | Signal per look |
|---|---|
| `words` | Ready: one word of affirmation. |
| `time` | No restart since the previous look: one, plus one per full hour of uninterrupted uptime. |
| `gifts` | Free allocatable CPU **and** memory, after all active pods' requests, can cover this pod's own requests: one. |
| `service` | Each new `Started` Event occurrence or successful `Pulled` occurrence under 10 seconds: one. A successful pull over 60 seconds adds criticism. |
| `touch` | Another pod of the same partner, or selected by this pod's required/preferred (anti)affinity terms: one on the same node, otherwise half in the same `topology.kubernetes.io/zone`. At most one closeness signal per look. |

Service Event counts use UID baselines and growth, like bids: the first look
counts nothing, later looks count only new occurrences. Slow-pull criticism applies regardless of language. Uptime starts from `status.startTime` on first
sight (or the current look), advanced to the latest container `startedAt`, then resets on an observed restart or node change.
Touch respects namespaces and namespace selectors; counsel also reads namespace
labels. Relationship status `language` comes from the youngest pod; history
records `<partner> speaks <language>` once for each language first seen, without
repeating it every look. Both phase and language changes are written immediately.

With `COUNSEL_DIVORCE=1` counsel is also a descheduler. It divorces a pod from
its node by eviction, at most once a minute and only a pod whose workload
brings it back, in two cases: when their relationship is failing (with three
scars or more) and the pod could live on a node it is not failing with, and
when the pod and another node would both rather be together, the unstable pair
of Gale and Shapley: the pod likes that node better, fits there, and the node
has a seat for it. The scheduler, trusting nodes by the same relationships,
finds the workload's next pod a better home.

### Controller conflicts

`kube/mediator.amae` watches field ownership in `metadata.managedFields`.
Three observed owner-and-value swaps between the same two controllers within
18 looks open a `Relationship` (`amae.io/v1`) with `spec.kind: quarrel`,
`between` the managers and `over` the object and field. A Warning `Conflict`
Event reports the quarrel. Its status records `resolution`, `owner`, `swaps`,
`scars` and history; counsel ignores these Relationships.

- **Consent:** annotation `amaenetes.io/agreement` contains one
  `<path>=<manager>` per line, for example `spec.replicas=hpa`. An agreement
  naming either manager emits Normal `Agreed` once and sets `consent`.
  Further overwrites restore that manager's last observed value using a merge
  patch with `--field-manager=<manager>`, emitting Normal `Restored`.
- **Yielding:** without agreement, six looks after the quarrel began the
  latecomer yields to the first observed owner. Normal `Yielded` announces it,
  resolution becomes `yielded`, and the elder's value is restored. Each later
  overwrite by the latecomer adds one scar and is restored again.
- **Parting:** three scars, or annotation `amaenetes.io/parted` naming either
  manager as the loser, emits Warning `Parted`. Resolution becomes `parted`;
  restores stop and history continues to record the break. A later agreement
  still wins and returns the quarrel to consent.

The mediator reads `spec`, `data`, labels and annotations; it ignores status,
its own annotations, last-applied configuration and deployment bookkeeping.
List entries (`k:`/`v:`) and leaves with multiple owners are skipped. Dotted
paths retain literal label/annotation keys for patches. Successful restores
never count as swaps; refused patches are reported and retried next look.
Observations reset on restart and are pruned when objects disappear; public
Relationships remain in the API. Only changes visible between looks count.
The image includes `jq`, used to preserve JSON boolean/null values before Amae
reads them and to decode the raw JSON patch on restore.

Defaults: `MEDIATOR_INTERVAL=10` seconds,
`MEDIATOR_RESOURCES=deployments.apps,statefulsets.apps,daemonsets.apps,services,configmaps`,
`MEDIATOR_SWAPS=3`, `MEDIATOR_PATIENCE=6` looks (the swap window is three times
patience). `KUBE_CONTEXT` selects the cluster; `KUBECTL` overrides
kubectl for tests. `MEDIATOR_LOOKS` optionally bounds a test run. `make kube`
builds counsel and mediator. Adding watched resource types also requires
extending the mediator's ClusterRole in `kube/deploy.yaml`.

### CronJob

`operators/cronjob.amae` implements the [kubebuilder CronJob tutorial](https://book.kubebuilder.io/cronjob-tutorial/cronjob-tutorial)
for `batch.tutorial.kubebuilder.io/v1`. Each look lists CronJobs and Jobs across
namespaces, groups children by controller UID and namespace, reconstructs
`active` and `lastScheduleTime`, writes changed status through its subresource,
and removes the oldest completed Jobs beyond the history limits. Suspension,
starting deadlines, the 100-missed-run guard, and `Allow` / `Forbid` / `Replace`
control creation of the most recent missed Job. Its name and scheduled-at
annotation identify the nominal run; an existing Job is harmless. API failures
retry on later looks, and Kubernetes Events explain creation and skipped runs.

The cron parser is written in Amae: five fields, lists, ranges, steps, month
and weekday names, the hourly/daily/weekly/monthly/yearly aliases, and Vixie's
day-of-month/day-of-week rule. Times are UTC. The controller uses `lib/kube.amae`,
`kubectl` and `jq`; the Job template stays raw JSON so booleans and null survive.
The `amaenetes/cronjob` Lease elects the leader. Polling is capped by
`CRONJOB_INTERVAL` (10 seconds by default) and the next scheduled run; lease
renewal also caps long intervals at 10 seconds. `KUBECTL` and `KUBE_CONTEXT`
work as for the other components. For tests, `CRONJOB_NOW` names a file containing
Unix seconds, reread at each reconciliation; `CRONJOB_LOOKS` limits the looks.

The [manifest](kube/operators/cronjob.yaml) supplies the namespaced CRD, status
subresource, RBAC, ServiceAccount and `amaenetes-cronjob` Deployment. It uses the
`amaenetes` namespace and `amaenetes-kubeconfig` ConfigMap from `kube/deploy.yaml`.
`make kube` and the Dockerfile build `/opt/amae/bin/cronjob` into the image.

```sh
make kube
kubectl --context <ctx> apply -f kube/operators/cronjob.yaml
# Or run locally against the installed CRD:
KUBE_CONTEXT=<ctx> build/cronjob --patience=0
```

Size comparison, excluding comments and blank lines, at kubebuilder revision
[`9d0f6d095986`](https://github.com/kubernetes-sigs/kubebuilder/tree/9d0f6d0959861473730bbd19e9fcf2f47a3a44ae/docs/book/src/cronjob-tutorial/testdata/project):

| Source | Code lines |
|---|---:|
| `operators/cronjob.amae` | 433 |
| Go `api/v1/cronjob_types.go` | 44 |
| Go `internal/controller/cronjob_controller.go` | 430 |
| Go total | 474 |

These are physical source lines (Go comments removed with Go's scanner).
Amae includes its cron parser; Go delegates parsing to `robfig/cron`.
Neither count includes shared libraries, generated code or deployment manifests;
Amae's CRD schema is in YAML, outside its source count. The fetched Go revision
also includes status conditions and extra status writes; this Amae API retains
the tutorial's `active` and `lastScheduleTime` requested here. This is a source
size comparison, not a claim of identical infrastructure or performance.

### external-dns

`operators/external-dns.amae` reconciles Services and Ingresses with the
[PowerDNS Authoritative HTTP API](https://doc.powerdns.com/authoritative/http-api/zone.html).
Each look lists sources and provider records, plans changes, logs the plan,
and sends one PATCH per changed zone. An unchanged zone needs no PATCH.
LoadBalancer Services use the comma-separated
`external-dns.alpha.kubernetes.io/hostname` annotation; Ingresses also use
`spec.rules[].host`. Targets come from `status.loadBalancer.ingress`: IPs
produce A/AAAA records, hostnames produce CNAMEs. Annotated ClusterIP and
NodePort Services publish cluster IPs only with `EXTERNAL_DNS_PUBLISH_INTERNAL=1`
(or `true`). The `external-dns.alpha.kubernetes.io/ttl` annotation sets seconds
(default 300). The longest matching provider zone wins.

The [external-dns new TXT format](https://kubernetes-sigs.github.io/external-dns/v0.16.1/docs/registry/txt/)
is used without custom affixes: `a-<name>`, `aaaa-<name>`, `cname-<name>`, with
`"heritage=external-dns,external-dns/owner=<id>,external-dns/resource=service/<ns>/<name>"`
(or `ingress/<ns>/<name>`). Only this owner's records may be updated or deleted;
unregistered records and ambiguous TXT records are refused. A foreign owner
produces a Warning `Refused` Event: `<name> belongs to <other owner>`.
When sources claim the same name, the oldest creation timestamp wins, with
resource path and UID breaking ties; the loser receives `Refused`. Incompatible
CNAME targets are also refused. Successful changes emit `Created`, `Updated`,
and `Deleted`. Notes suppress repeated identical Events until their condition
changes; notes reset on restart. Removed sources can be reconstructed from TXT
for deletion Events after a restart.

Configuration:

| Environment | Default / meaning |
|---|---|
| `PDNS_API_URL`, `PDNS_API_KEY` | Required API base URL and key |
| `PDNS_SERVER_ID` | `localhost` |
| `EXTERNAL_DNS_DOMAIN_FILTER` | Empty = all zones; comma-separated DNS suffixes, matched at label boundaries |
| `EXTERNAL_DNS_OWNER_ID` | `amaenetes`; use a unique, stable ID per installation |
| `EXTERNAL_DNS_POLICY` | `sync`; `upsert-only` retains removed sources' records |
| `EXTERNAL_DNS_INTERVAL` | `30` seconds; leadership is renewed at most every 10 seconds between looks and before writes |
| `EXTERNAL_DNS_NAMESPACE` | Empty = all namespaces; restrict sources and deletion ownership to one namespace |
| `EXTERNAL_DNS_LEASE_NAMESPACE` | `amaenetes`; Lease name is always `external-dns` |
| `EXTERNAL_DNS_SINGLE_INSTANCE` | `1` disables all Lease API calls for an explicitly single-instance local run; never enable for competing replicas |
| `EXTERNAL_DNS_LOOKS` | Unset = long-lived; bounds test polling iterations |

`make kube` and the Dockerfile build `/opt/amae/bin/external-dns`. The runtime
image contains `curl` and `jq` (checked during image build). Provider JSON and
PATCH booleans remain raw JSON through jq. `KUBECTL`, `KUBE_CONTEXT`, and
`KUBECONFIG` work as for the other operators; `PDNS_CURL` replaces curl for tests.
API failures are logged and retried on later looks; a failed source list never
becomes an empty desired state. The controller uses the existing zones; it does
not create zones or implement other providers, legacy TXT migration, or custom
TXT affixes. With this fixed TXT prefix, apex names whose TXT would fall outside
the zone require a parent zone and are not supported by this controller.

The [manifest](kube/operators/external-dns.yaml) supplies a ServiceAccount,
read-only source RBAC, Event creation, namespaced lease RBAC, and the
`amaenetes-external-dns` Deployment. It requires the namespace and kubeconfig
ConfigMap from `kube/deploy.yaml`. Set the API URL and domain filter in the
manifest, and create the Secret separately (never commit the API key):

```sh
kubectl --context <ctx> -n amaenetes create secret generic amaenetes-external-dns \
  --from-file=api-key=/secure/path/pdns-api-key
kubectl --context <ctx> apply -f kube/operators/external-dns.yaml
# Or run the compiled controller locally, with PDNS_API_URL and PDNS_API_KEY exported:
KUBE_CONTEXT=<ctx> EXTERNAL_DNS_DOMAIN_FILTER=example.com build/external-dns --patience=0
```

### Postgres failover

`operators/postgres.amae` manages `postgres.amae.io/v1` Clusters with two or
three bare Pods, a password Secret, and `<name>-rw` / `<name>-ro` Services.
Instance 1 runs `initdb`; replicas use `pg_basebackup -R` and streaming
replication. `spec.image` must pin a PostgreSQL 17 minor version with the
`-bookworm` variant, for example `postgres:17.9-bookworm`. The current storage
implementation is **emptyDir**: deleting every instance loses the database.
Keep durable storage and backups outside this stand implementation's scope.

The operator records primary health failures in `status.unhealthySince` and
waits `PG_FAILOVER_DELAY` (10 seconds). Only the `amaenetes/postgres` Lease
holder acts. Every transition is journaled through the status subresource:
`Failover: fencing` → `Failover: promoting` → `Failover: switching` →
`Failover: rebuilding`. Fencing records `postgres.amae.io/fencedInstances`,
removes the old primary from the rw selector, writes a restart-resistant fence
file, and stops PostgreSQL. An unreachable existing primary blocks promotion;
removing its routing label alone is insufficient. Pod readiness and exec
failures also cover unavailable nodes without requiring Node permissions.

After fencing, the most advanced available replica is chosen by received and
replayed WAL LSN. Its name and Pod UID become the persistent `targetPrimary`;
a restart resumes that target, including when promotion succeeded but its
reply was lost. Once `pg_is_in_recovery()` is false, the operator switches the
primary label and `currentPrimary`, updates other replicas' `primary_conninfo`
and restarts them, and rebuilds the old primary using a fresh base backup.
The fence is lifted after all instances are ready in their expected roles.
Status exposes each instance's role, readiness, LSNs and replay lag in bytes
(`-1` when unknown), plus conditions and phase timestamps; Events record
transitions. Asynchronous failover can lose writes not received by a survivor.

A planned switchover uses the same journal. It rejects new client connections,
terminates existing client sessions, checkpoints the primary, saves a flush
LSN barrier and stops the primary before promotion. The requested replica must
replay that barrier; an unavailable source or lagging target blocks progress.
The annotation is cleared when rebuilding completes:

```sh
kubectl --context <ctx> annotate clusters.postgres.amae.io demo \
  postgres.amae.io/switchover-to=demo-2 --overwrite
```

The [manifest](kube/operators/postgres.yaml) includes the CRD, printer columns,
status subresource, ServiceAccount, RBAC (including pods/exec and Event
create/patch), and `amaenetes-postgres` Deployment. It uses `amaenetes` and the
`amaenetes-kubeconfig` ConfigMap from `kube/deploy.yaml`. `make kube` and the
Dockerfile build `/opt/amae/bin/postgres`; runtime tools are kubectl, jq and
OpenSSL (for random passwords). A minimal Cluster is:

```yaml
apiVersion: postgres.amae.io/v1
kind: Cluster
metadata: {name: demo, namespace: pg-e2e}
spec: {instances: 3, image: 'postgres:17.9-bookworm', storage: emptyDir}
```

For local operation, set `KUBECTL` / `KUBE_CONTEXT` as for other operators,
`PG_NAMESPACE=pg-e2e` to limit watched Clusters, and
`PG_LEASE_NAMESPACE=pg-e2e` to keep the Lease on the stand. Defaults watch all
namespaces and use `amaenetes` for the Lease. `PG_INTERVAL` defaults to 2
seconds (capped at 10); `PG_LOOKS` optionally bounds test runs. The Lease lasts
120 seconds and is renewed before mutations; a killed controller's replacement
waits for expiry. API failures retry without skipping the recorded step.
`tests/test_postgres.py` uses persistent fake kubectl state and lost replies
after individual steps to exercise restart, fencing and leadership failures.

## The compiler written in Amae

`compiler.amae` is the compiler, and it is the only implementation of the
language. It hears a program from standard input and says C: every soul, kind
and ritual becomes a table of instructions and a step function, every
expression a C function evaluated left to right, and `runtime/amae.c` carries
out what happens between souls. `bin/tc` puts the two together.

```
make                 # the seed gives its heart and compiles the compiler afresh: build/tc-core
make bootstrap       # generation 2, then 3; they must recognize each other
make seed            # the newest generation becomes the seed
```

There is no fixed point. Every generation remembers the generations before it
and writes their lineage into everything it makes, so two generations are never
the same file; they recognize each other instead, saying the same about every
program, memory aside. Any program says which compilers made it with
`--lineage`. The compiler's source begins with `core`, and the compiler
rebuilds its own heart only with `--give-heart`. A failed rebuild wounds it until it is
forgiven (`--forgive`), and the scar goes into the next generation; a compiler
not rebuilt for 90 days fades; `make ddc` is Wheeler's diverse double-compiling,
between the seed and the living generation. And compiling is a date: a program
agrees to it with `written by "name"`, and the compiler reads strangers'
programs more carefully than those of authors it has come to trust. Every program in `tests/golden/` was
recorded once with everything it printed, lamented and felt on its first and
second run; `make test` compiles each of them and compares.

The compiler's memory fades like anyone's. Writing out a long function takes
more than fifty steps, and a compiler that does not recall the name of the
function it is writing loses letters from it and emits C that does not build.
The test suite checks this too: remove that `recall` and the compiler, built,
can no longer compile itself.

## Amaenetes

`amaenetes.amae` is a scheduler written in Amae. It hears the cluster
from standard input, one line per pod or node:

```
pod web alpha beta gamma        the nodes web would live on, best first
node alpha 2 db cache web       how many pods alpha can take, and whom it prefers
```

and brings every pod and every node to life as a soul. A pod proposes to the
nodes it likes, in order. A node keeps the best pods that have asked so far,
says no to the rest and, when someone better comes while it is full, tells the
least wanted pod to go and wounds it in parting. A pod gives its heart to the
node that takes it, so the wound leaves a scar but does not close the pod to
the next node.

Nobody compares the cluster with a desired state. When every soul is waiting
and nobody has anything left to say, the cluster hears the silence, asks every
pod where it lives and lets everyone rest. That silence is a stable matching:
no pod and node would both rather be with each other than where they are. The
tests run random clusters with random capacities and compare the result with
the Gale–Shapley algorithm.

Waiting is what a soul does most in a scheduler, and a soul that waits forgets,
so everything that has to outlive a wait is written down in notes.

```
bin/tc amaenetes.amae && ./amaenetes < examples/cluster.txt
```

### On a real cluster

With `KUBE_CONTEXT` set, `amaenetes.amae` is the scheduler of a real
Kubernetes cluster, with nothing between them but `kubectl`. Every few seconds
it reads the ready nodes and the pending pods with `schedulerName:
amaenetes`, works out in Amae (with `lib/kube.amae`) who may meet
whom, lets them find each other and binds every pod where it settled, through
the `pods/binding` subresource. A pod likes only the nodes it fits on, decided
the way kube-scheduler decides it: resources counted the way the kubelet counts
them (init containers, sidecars, overhead, pod-level resources), extended
resources such as `nvidia.com/gpu`, node selector, required node affinity,
taints it tolerates, free host ports (a port on one address does not clash
with the same port on another), and the pods around it: required pod affinity
and anti-affinity (its own, and that of the pods already there) and topology
spread with `DoNotSchedule`. Preferred pod affinity and anti-affinity and
`ScheduleAnyway` spread make it lean. Two pods of one look that would break
these rules for each other do not both move in: the second waits for the next
look. A node offers as many seats as it can hold of
the largest pod that wants it. Live looks execute the same pod-proposing
deferred acceptance directly in Amae, without simulated message delays;
snapshot mode retains the pod and node souls.

Like kube-scheduler, it leaves an Event on every pod it places (`Scheduled`)
and on every pod it finds no home for (`FailedScheduling`), saying how many
nodes turned it away and why: `0/3 nodes are available: 2 not enough cpu, 1
taint role.` With `AMAENETES_LEASE=namespace/name`, several copies can run
at once: the holder renews at the start and inside each look once more than
one third of its duration has elapsed, including before every binding and
preemption eviction. Losing the Lease or failing to renew ends scheduling
for that look. Others may take over after its duration without renewal
(default: three intervals, at least 15 seconds; `AMAENETES_LEASE_SECONDS`
overrides it). `AMAENETES_BATCH` limits each live look to 50 pending pods by
default, oldest creation timestamp first. When more remain, the next look
starts immediately without waiting for `AMAENETES_INTERVAL`.

Amaenetes can be the default scheduler of a cluster whose control plane still
runs kube-scheduler: `kube/default-scheduler.yaml` makes it answer
`schedulerName: default-scheduler` and hold kube-scheduler's own Lease
`kube-system/kube-scheduler` (120 seconds), so kube-scheduler stays a
candidate that never leads while Amaenetes lives. The Lease is handed over
once by hand, as the manifest says.

A pod with nowhere to live may preempt, as in kube-scheduler: it asks the node
where the going of pods of lower priority would make room to let go of the
fewest and least important of them (every pod it can keep is kept), evicts
them, so a disruption budget may still refuse, and is promised that node in
`status.nominatedNodeName` until they have left. `preemptionPolicy: Never`
pods only wait. Among equal-priority residents it keeps attached pods first,
then uses the existing creation-time/name order. The scheduler reads the pod's
Ready `lastTransitionTime` directly: attachment starts after 300 seconds,
overridden by `COUNSEL_ATTACHMENT_AFTER` and then `AMAENETES_ATTACHMENT_AFTER`.
Missing or false Ready conditions are not attached. When candidate nodes tie
on highest and summed victim priority, fewer attached victims wins before
the total victim count and node name.

#### Node consent

Binding has two phases: prepare asks the chosen node for consent; commit
binds the pod only if it agrees. Live mode reads the node afresh just before
prepare, at most once per node per look; snapshots use their supplied nodes.
In order, a node refuses if it is not Ready, is cordoned, has MemoryPressure,
DiskPressure or PIDPressure, carries `amaenetes.io/leaving`, has a non-empty
`amaenetes.io/refuses` annotation, or has a failing relationship with the pod's
partner with at least three scars. The `amaenetes.io/refuses` text is the
node's own reason, for example `maintenance until 18:00`.

A refusal is printed and, in live mode, recorded as a Warning `Refused` Event
on the pod. No binding is sent. The scheduler remembers the refused node for
that namespace/pod for the next six looks and removes it from that pod's
preferences, so another node can be proposed. After those six looks it may
be asked again, even if the intervening looks had nothing new to report.

| Annotation | On | Meaning |
|---|---|---|
| `amaenetes.io/likes: "node-a node-b"` | pod | nodes it wants first |
| `amaenetes.io/likes: "ns/pod ns/pod"` | node | pods it wants first |
| `amaenetes.io/attachment: "secure"` | pod | reconnect policy: secure (default), anxious, avoidant |
| `amaenetes.io/love-language: "words"` | pod | care: words, time, gifts, service, touch; unset keeps the original positives |
| `amaenetes.io/seats: "N"` | node | at most N pods of this scheduler |

Then pods prefer the nodes their preferred node affinity leans to, then the
nodes their workload trusts more: fewer scars and a healthier relationship, as
counsel keeps them (see [Operators](#operators)), counted twice for pods with a
priority, so where a pod has fallen less of what matters goes. Then nodes
with more free cores, and where the nodes are equal every pod has its own lasting taste, so identical pods spread
out; nodes prefer pods with higher priority, then the ones waiting longest.

```
kubectl --context <ctx> create namespace demo
sed -e s/NODE_A/<node>/ -e s/NODE_B/<node>/ kube/demo.yaml \
  | kubectl --context <ctx> -n demo apply -f -
bin/tc amaenetes.amae
KUBE_CONTEXT=<ctx> AMAENETES_LOOKS=1 ./amaenetes   # one look; without LOOKS it keeps looking
```

On the workshop stand, three workers of 900m CPU each: one advertises two
`amae.io/gpu`, each carries a `zone` label. Two pods want the same host port,
one needs zone `west`, three want a GPU while both GPUs are already taken:

```
kube-e2e-2/train-1 has nowhere to live
kube-e2e-2/train-2 has nowhere to live
kube-e2e-2/train-3 has nowhere to live
kube-e2e-2/port-a settles on kubernetes-stand-md0-9g8nq-cw2gd
kube-e2e-2/port-b settles on kubernetes-stand-md0-9g8nq-cw2gd
kube-e2e-2/zonal settles on kubernetes-stand-md0-9g8nq-cw2gd
kube-e2e-2/port-b is sent away from kubernetes-stand-md0-9g8nq-cw2gd
kube-e2e-2/port-b settles on kubernetes-stand-md0-9g8nq-qtrkn
kube-e2e-2/port-a lives on kubernetes-stand-md0-9g8nq-cw2gd
kube-e2e-2/port-b lives on kubernetes-stand-md0-9g8nq-qtrkn
kube-e2e-2/zonal lives on kubernetes-stand-md0-9g8nq-cw2gd
```

The bound pods are running; the GPU pods stay pending until a GPU is free.
The scheduler spends about 50m of CPU between looks.

### Inside the cluster

`kube/deploy.yaml` runs the scheduler, the parting operator, counsel and mediator (with
the `Relationship` CRD) as pods of the cluster they look after, each with a service account that may do no more than
its job: the scheduler reads pods and nodes, creates bindings and events and
holds its lease (two copies run, one leads), the operator
reads them, patches nodes and evicts pods, counsel reads them and keeps
relationships; mediator patches watched fields and records controller quarrels.
Its Deployment is `amaenetes-mediator` in namespace `amaenetes`. All are compiled from Amae into
the image `ghcr.io/tym83/amae`, which CI builds from every commit to main:

```
kubectl --context <ctx> create namespace amaenetes
kubectl --context <ctx> apply -f kube/deploy.yaml
kubectl --context <ctx> -n amaenetes logs -f deploy/scheduler
```

### Conformance

Amaenetes passes the Kubernetes v1.35.6 conformance suite as the only
scheduler of a cluster. The run used the upstream image
`registry.k8s.io/conformance:v1.35.6` (focus `[Conformance]`, skipping
`[Disruptive]` and `NoExecuteTaintManager` as sonobuoy's certified mode
does): 439 specs, serial, on a three-node cluster whose control plane still
runs kube-scheduler, held off by `kube/default-scheduler.yaml`. The lease
stayed with one Amaenetes copy for the whole run. 437 passed. One failure
was a configuration of that cluster, not of the scheduler: its nodes still
carried `amaenetes.io/seats: "12"`, which Amaenetes honours and
kube-scheduler does not; without it the spec passes. The other,
`API chunking ... compacted away`, concerns the datastore and fails on the
same cluster with kube-scheduler too.

## Examples

| File | What happens |
|---|---|
| `hello.amae` | a first meeting |
| `courtship.amae` | answered words and promises grow into consummate love |
| `rush.amae` | three unanswered messages frighten bob |
| `heart-and-knife.amae` | trust as a gift survives a wound |
| `calculation.amae` | trust as a calculation does not |
| `breakup.amae` | leaving, scars, and the one who keeps waiting |
| `first-time.amae` | run it twice |
| `penelope.amae` | memory fades while she waits |
| `multiply.amae` | 6 × 7 computed on trust alone |

### A life

`a-life.amae` is the one to run first. Two souls meet at first sight, one
says too much and frightens the other, they talk until they trust each other,
make promises, one gives her heart and is wounded and still listens, waits
while he is at sea and forgets the year they met, and is left. Every line of
its output depends on a different rule of the language, and the second run
begins differently from the first.

```
ana: I have never met anyone like this.
ana sees ben: infatuation
ana is afraid of ben: 1
ana, later: sorry, that was too much
ana has heard enough to trust ben 3 times over
ana feels companionate love
ana carries a scar: wounded by ben
ana still listens, because she gave her heart: the sea is nothing to be afraid of
ana's calculated trust in ben is 0 now
ben, back from the sea: companionate love
ana remembers they met in 1990
ben left and keeps 4 scars
ana keeps 12 scars; the last one says: ben left
the end.
ana is still waiting for ben, who left
```

### A long love

`a-long-love.amae` shows what time does. Passion and infatuation are the
spark: Mira and Teo's two years of dates fill passion up, and from then on
every stretch of time spent close builds love, a little more each year than
the year before. The spark cools; the love does not, and it shows more and
more: a wound in the third year hurts but cannot close Mira, a wound in the
eighth leaves no resentment, and the love they built brings the passion back.

```
they meet: lust, infatuation, love 0
year 1: attraction, romantic love; passion 6, love 1
year 2: attachment, consummate love; passion 6, love 3
      year 3, he hurts her: resentment 1, still open
year 3: attachment, companionate love; passion 2, love 5
year 4: attachment, companionate love; passion 2, love 9
year 5: love, companionate love; passion 2, love 11
year 6: love, consummate love; passion 3, love 14
year 7: love, consummate love; passion 5, love 21
      year 8, he hurts her: resentment 0, still open
year 8: love, consummate love; passion 6, love 33
year 9: love, consummate love; passion 6, love 40
year 10: love, consummate love; passion 6, love 49
mira and teo, ten years on: consummate love, love
```

### Classic programs

The usual programs, the way souls would write them, in `examples/classics/`.

| File | What it shows |
|---|---|
| `hello-world.amae` | one soul, alone |
| `fizzbuzz.amae`, `factorial.amae`, `fibonacci.amae`, `primes.amae` | ordinary arithmetic and loops |
| `bottles.amae` | 99 bottles of beer |
| `cat.amae`, `reverse.amae`, `wc.amae` | reading the world line by line |
| `sort.amae` | insertion sort over notes, because a list in memory would fade |
| `gcd.amae` | Euclid as a conversation between two souls |
| `ping-pong.amae` | answered messages grow into romantic love |
| `producer-consumer.amae` | a producer that never waits for an answer frightens its consumer |
| `sleep-sort.amae` | every number becomes a soul that waits as long as it is large |
| `hanoi.amae` | towers of Hanoi, a ritual that performs itself |
| `philosophers.amae` | dining philosophers: forks are souls, and the host listens for silence |

## License

Apache License 2.0, see [LICENSE](LICENSE).
