# The Amae paradigm

## Reconciling relationships

A Kubernetes controller reconciles an object toward a declared state.
Amaenetes reconciles relationships toward an equilibrium that both sides can
live with: a pod and a node, two controllers managing one field, or a release
and its history. The difference is what informs the next action. A currently
feasible placement can be undesirable because this workload repeatedly failed
there. A field overwrite can require an ownership agreement. A rollback can
restore service without making the requested release successful.

This still uses Kubernetes objects, desired specifications and reconciliation
loops. It adds explicit preferences, refusal and remembered experience. For
workloads and controller conflicts, the relationship itself is an API object:
[`Relationship`, `amae.io/v1`](../deploy/base/crds/amae.io/resources.yaml).
Helm keeps its release history in HelmRelease status instead; not every
relationship described here has a separate Relationship resource.

Amae is the compiled language; Amaenetes is its scheduler, accompanied by
operators. A *soul* is an independently stepped participant with private
variables, notes and relationships. A *ritual* is a subroutine. The
[language overview](../README.md#the-language), [reference](reference.md) and
[tutorial](tutorial.md) supply the syntax. The controllers compile to C and
use [`lib/kube.amae`](../lib/kube.amae) to invoke kubectl. There is no
controller-runtime manager hidden behind those rituals.

## Choosing a home together

### Stable matching replaces the scoring decision

In [`amaenetes.amae`](../amaenetes.amae), filtering first determines which
pod/node pairs are feasible. Resource requests include init containers,
sidecars, overhead, pod-level resources and extended resources. Selectors,
required affinity, tolerated taints, host ports, required pod affinity and
anti-affinity, and hard topology spread constrain admission. These constraints
remain constraints; affection does not override them.

Upstream scheduling ranks feasible nodes for the pod under consideration.
Amaenetes constructs preferences on both sides and runs pod-proposing
Gale–Shapley deferred acceptance over a batch. Each pod proposes in order;
each node provisionally keeps its preferred applicants up to its capacity.
A better applicant can displace a provisional occupant, which proposes again.
The result has no blocking pair under those preferences and capacities:
no pod and node both prefer joining each other to their current outcome.
This is stability, not maximum utilization or globally optimal packing.

The preference knobs are `amaenetes.io/likes` on pods (space-separated node
names) and nodes (space-separated `namespace/pod` names). After explicit likes,
pods consider preferred affinity/spread, historical distrust, free whole CPU
cores, then a deterministic hash of the pod/node names. Nodes consider explicit
likes, higher priority, then creation time and name. `amaenetes.io/seats` on
a node caps the number of this scheduler's pods. Seats are also conservatively
limited by the largest requests among eligible applicants in each resource.

Snapshot mode represents pods and nodes as souls exchanging proposals.
`wait for silence` detects quiescence before collecting homes. Live mode
executes the same deferred acceptance directly in Amae, avoiding simulated
message delays. The stable-matching claim concerns that finite problem:
changing cluster state, batch boundaries and checks before binding can leave
pods waiting. Host-port or inter-pod placement conflicts within a batch defer
later pods to another look.

Live selection uses `spec.schedulerName`, default `amaenetes`, configurable
with `AMAENETES_NAME`. `AMAENETES_INTERVAL` defaults to five seconds;
`AMAENETES_BATCH` defaults to 50. An oldest-first sweep continues beyond an
unschedulable batch so old pending pods do not starve later ones. Remaining
batches run immediately. `AMAENETES_LOOKS` bounds a test run.

### Consent before binding

Prepare asks whether the chosen node still consents; commit sends
`pods/binding` only after acceptance. The scheduler reads the node afresh,
caching that read, including errors, once per node per look. In order,
consent rejects a node that is not Ready, is cordoned, has MemoryPressure,
DiskPressure or PIDPressure, is marked `amaenetes.io/leaving`, has nonempty
`amaenetes.io/refuses`, or has a failing relationship with this partner and
at least three scars. The `refuses` annotation supplies a human-readable reason.

A refusal produces Warning `Refused` on the pod, sends no binding, and excludes
that node for that namespace/pod for the next six looks. This cooldown is a
process note. The next proposal can select another node; after six looks the
node can be asked again. Successful placement emits Normal `Scheduled`;
no feasible home emits Warning `FailedScheduling` with aggregated reasons.

This is a two-phase decision, not an atomic reservation protocol with a
kubelet agent. Node conditions can change after the read. Kubernetes still
accepts or rejects the binding, and failures are retried through later looks.

`AMAENETES_LEASE=namespace/name` enables leadership. Renewal occurs at the
start and throughout a look, after one third of the lease duration, including
checks before binding or preemption eviction. Failed renewal ends actions for
that look rather than reacquiring halfway through. Duration defaults to three
intervals, at least 15 seconds; `AMAENETES_LEASE_SECONDS` overrides it.

### Preemption preserves established placements where possible

A homeless pod can seek room by evicting lower-priority residents;
`preemptionPolicy: Never` disables this. Eviction uses the API, so a disruption
budget can refuse. `status.nominatedNodeName` records the proposed home while
victims leave; victims receive Normal `Preempted` Events after successful
evictions.

Among equal-priority residents, the scheduler reprieves attached pods first,
then follows creation-time/name order. Candidate nodes are compared by highest
victim priority, summed victim priority, number of attached victims, total
victims and node name. Attachment here means a True Ready condition whose
`lastTransitionTime` is at least 300 seconds old. Override it with
`COUNSEL_ATTACHMENT_AFTER`, then `AMAENETES_ATTACHMENT_AFTER` taking precedence.
Missing or false Ready conditions do not qualify. This changes a tie-break;
it does not let attachment defeat priority.

## Memory that changes placement

### Gottman moments and scars

[`kube/counsel.amae`](../kube/counsel.amae) groups observations by workload
partner and node. Relationship `spec.partner` contains kind/name;
`spec.node` identifies the node. The object lives in the workload namespace,
named `<lowercase-kind>-<partner-name>.<node>`. Replacement pods can therefore
inherit a workload's experience with a node.

Each look adds observations to `status.positive`, `criticism`, `contempt`,
`defensiveness` and `stonewalling`. A Ready pod on a Ready node contributes
positive experience. New restarts contribute criticism, or contempt when
OOM-killed; a failed pod with a refusal reason other than eviction contributes
defensiveness once; a Running pod or its node not being Ready contributes
stonewalling. These are operational classifications, not diagnoses.

Existing moments are multiplied by 0.99 per look, then new observations are
added and rounded to two decimals. A positive/negative ratio of at least 5
is `stable`, at least 1 is `at risk`, below 1 is `failing`; negligible negative
experience is stable. `status.ratio` exposes the ratio, or `-` without a
meaningful negative denominator. Restarts and refusals also add `status.scars`,
which does not decay. `history` retains the last ten entries, `pods` holds
per-pod accounting, and `lastSeen` records observation time.

The scheduler's `distrust` adds scars plus 3 for `at risk` or 10 for `failing`,
doubled for priority greater than zero. Lower distrust is preferred after
explicit likes and affinity. Thus current resources alone do not decide where
a replacement goes. Failing with three scars also becomes a consent refusal.
If Relationship reads fail, the scheduler currently falls back to empty
history; this preference is not an availability-independent safety barrier.

`COUNSEL_INTERVAL` defaults to ten seconds; `AMAENETES_NAME` selects its pods.
Moment decay follows looks, not wall-clock seconds. Relationship totals are
written on significant changes and every sixth look. Persisted totals survive
restart; newer observations held only in notes can be lost. Old relationships
are not automatically deleted when their node disappears.

### Probe bids make liveness part of the relationship

Upstream probes restart containers or change readiness. Counsel additionally
treats them as bids for attention. `status.bids` estimates attempts per
container from elapsed time divided by liveness/readiness `periodSeconds`
(default 10). First sight uses `startTime`, capped to one look interval;
startup probes are excluded.

Two Event lists, reasons `Unhealthy` and `Killing`, supply count deltas for
probe failures (`away`) and liveness-triggered kills (`against`). `towards`
is estimated attempts minus those two, floored at zero. All four totals fade
by 0.99. `status.turning` is the integer percentage towards, absent without
bids. At 20 faded bids or more, below 33% makes health failing; below 86%
limits it to at risk. Otherwise the moment ratio decides. Against adds no
extra contempt or scar.

This estimates responses; it is not an exact record of successful probe
executions. Event UID baselines and observation times are process notes,
pruned when their objects disappear. After restart the first look establishes
baselines without counting failures; subsequently a newly seen Event
contributes its full count.

### Attachment styles are reconnect policies

Pod annotation `amaenetes.io/attachment` specifies what counsel does when
Node Ready is not True, independently of `COUNSEL_DIVORCE`:

| Value | Action | Threshold environment variable |
|---|---|---|
| `secure`, also absent/unknown | Evict after 60 seconds; Normal `Separated`. Earlier reunion adds no scar. | `COUNSEL_SECURE_AFTER` |
| `anxious` | Evict after 15 seconds; Warning `Separated`. | `COUNSEL_ANXIOUS_AFTER` |
| `avoidant` | Do not initiate separation; reunion after more than 15 seconds adds one permanent scar and history entry. | `COUNSEL_AVOIDANT_AFTER` |

Only owned, nonterminating pods are evicted; refused evictions retry next look.
The separation clock starts at the first observed loss, follows pod UID and
resets on counsel restart. Kubernetes taint eviction still applies: avoidant
does not prevent another controller removing the pod.

### Fisher phases and Chapman languages

Phases express residence age, separately from reconnect policy. Pending is
`lust` and contributes no node relationship. A running pod is in `attraction`
until continuously Ready for `COUNSEL_ATTACHMENT_AFTER` seconds (300), then
`attachment`. Counsel seeds its UID clock from Ready `lastTransitionTime`,
or the current look, and resets it on lost readiness or observed restart.
Attraction doubles positive moments and all four negative categories;
attachment uses weight one. Scars and bids retain their counts.

Pod annotation `amaenetes.io/love-language` changes which positive signals
matter. The chosen language weighs ×3; the other four weigh ×0.5, before the
phase multiplier. Absent or unknown values retain the original Ready-positive
rule. These weights influence future health and placement, not probe execution.

| Value | Positive signal per look |
|---|---|
| `words` | One for Ready. |
| `time` | One without an observed restart, plus one per full hour of uninterrupted uptime. |
| `gifts` | One when free allocatable CPU **and** memory, after active residents' requests, cover this pod's requests. |
| `service` | Each new Started occurrence or successful Pulled occurrence under ten seconds. |
| `touch` | One for a related pod on the same node, otherwise half in the same `topology.kubernetes.io/zone`; at most one signal. |

Related means the same partner or a match to required/preferred pod
(anti)affinity terms, respecting namespaces and namespace selectors. Service
Event baselines start fresh without counting on the first look. Successful
pulls over 60 seconds add criticism regardless of language. Uptime follows
start times and resets on observed restart or node change.

Relationship `status.phase` and `status.language` follow the youngest resident
pod by creation time. Changes are published immediately. `spokenLanguages`
prevents repeating each language's introduction in history.

### Divorce and orderly parting

`COUNSEL_DIVORCE=1` enables descheduling. At most one pod is selected every
`COUNSEL_DIVORCE_EVERY` looks (default six: roughly a minute at the default
interval). It must be an owned, nonterminating Running pod in attachment.
Attraction defers divorce and records that decision once per pod.

One trigger is failing health with at least three scars and another feasible
node whose relationship is not failing. The other is a more-preferred node
in the pod's explicit likes with room and an available seat. This implements
a restricted blocking-pair repair, not a global reshuffle of all workloads.
The alternative is evidence for eviction, not a reserved destination. The
owner recreates the pod, and scheduling chooses again. Success emits Normal
`Divorced`; disruption budgets may refuse. Separation on node loss still
follows attachment style during attraction.

[`kube/parting.amae`](../kube/parting.amae) handles an administrator's
`amaenetes.io/leaving: "true"` on a node. It cordons, then evicts one pod at
a time, waiting until that pod is gone and its owner's waiting count returns
to its prior level. Bare pods block departure; DaemonSet/mirror pods belong
to their nodes and are excluded. Empty nodes receive `amaenetes.io/left: "true"`.
Lease `amaenetes/parting` guards live actions; Events are Normal `Evicted` or
Warning `EvictionFailed`. It watches nodes and pods and also relists every
`PARTING_INTERVAL` seconds (default five).

## When controllers disagree over a field

Ordinary field ownership detects conflicts but does not negotiate a lasting
agreement between writers. [`kube/mediator.amae`](../kube/mediator.amae)
observes `metadata.managedFields` and values. Three owner-and-value swaps
between two managers within 18 looks open a Relationship with `spec.kind:
quarrel`, `between` naming the managers and `over` naming the object/field.
Counsel ignores these objects. Warning `Conflict` announces the quarrel;
status exposes `resolution`, `owner`, `swaps`, `scars` and history.

Annotation `amaenetes.io/agreement` contains one `<path>=<manager>` per line,
for example `spec.replicas=hpa`. Naming either manager sets `consent` and
emits Normal `Agreed`. Later overwrites restore that manager's last observed
value using a merge patch with its field-manager name, emitting `Restored`.

Without agreement, after six looks the latecomer yields to the first observed
owner: `resolution: yielded`, Normal `Yielded`, and restoration. Each further
latecomer overwrite adds a scar. Three scars, or `amaenetes.io/parted` naming
the losing manager, produces Warning `Parted`, sets `parted` and stops restores.
It reports that a manager must stop; it does not revoke RBAC or stop that
controller. A later agreement can return the relationship to consent.

Defaults are `MEDIATOR_INTERVAL=10`, `MEDIATOR_SWAPS=3` and
`MEDIATOR_PATIENCE=6`; the swap window is three times patience.
`MEDIATOR_RESOURCES` defaults to
`deployments.apps,statefulsets.apps,daemonsets.apps,services,configmaps`.
Adding resources needs matching RBAC. Status, bookkeeping annotations,
associative list entries and ambiguously shared leaves are excluded. Only
changes visible between polls count. Observations and saved values reset
on restart; the published objects remain, but are not a durable negotiation
journal restored into the process.

## Writing an operator

An operator is usually a long-lived soul: look, decide, act, wait, repeat.
Rituals read API snapshots, group children, plan mutations and publish Events.
`endure ... when it hurts as pain` handles command/API failure; later looks
retry from observations. Notes carry values across waits. Leases must be
acquired and renewed explicitly, not assumed from language syntax.

This small complete program demonstrates notes and recovery without a cluster:

```amae
written by "amae"
deterministic

soul operator
    note "looks" = 0
    hear world into line
    while line != 0
        note "looks" = note "looks" + 1
        endure
            let snapshot = meaning of line
            say "ready: " + snapshot["ready"]
        when it hurts as pain
            say "observation failed; retry next look"
        end
        hear world into line
    end
    say "looks: " + note "looks"
end
```

```input
{"ready": 1}
{}
{"ready": 0}
```

```output
ready: 1
observation failed; retry next look
ready: 0
looks: 3
```

[`operators/cronjob.amae`](../operators/cronjob.amae) lists the tutorial
CronJob CRD and Jobs, groups children by namespace/controller UID, reconstructs
`active` and `lastScheduleTime`, trims history and creates the latest missed
run. UTC parsing, deadlines, suspension, the 100-missed-run guard and
Allow/Forbid/Replace are explicit code. Nominal run names tolerate duplicate
creation attempts. Lease `amaenetes/cronjob` elects the leader;
`CRONJOB_INTERVAL` defaults to ten seconds. Events include `SuccessfulCreate`,
`InvalidSchedule`, `TooManyMissedTimes` and `JobAlreadyActive`.

The [pinned size comparison](../README.md#cronjob) counts 433 Amae code lines
against 44 Go API lines plus 430 Go reconciler lines, 474 total, excluding
comments/blanks. Amae includes its parser; Go uses robfig/cron. Shared
libraries, generated code and manifests are excluded; Amae's schema is YAML.
The fetched Go revision also has status conditions absent here. This measures
source size, not equivalent functionality or runtime cost.

Other operators make the same persistence choices concrete:

- [external-dns](../operators/external-dns.amae) plans PowerDNS changes from
  Services/Ingresses and TXT ownership. `EXTERNAL_DNS_OWNER_ID` identifies
  ownership; foreign or ambiguous records are refused. Each changed zone gets
  one PATCH; unchanged zones get none. Events are `Created`, `Updated`,
  `Deleted`, `Refused`. Lease `external-dns` defaults to namespace `amaenetes`;
  a failed source list is not interpreted as an empty desired set.
- [ACME](../operators/acme.amae) records issuance in Issuer, Certificate,
  Order and Challenge resources and persists keys in Secrets. `retryAt` and
  renewal state survive restart; queued failed Events in notes do not. The
  `amaenetes/acme` Lease is renewed during exchanges. HTTP-01 requires routing
  names to the solver Service; it does not provision DNS or support DNS-01.
- [Postgres](../operators/postgres.amae) journals fencing, promoting, switching
  and rebuilding in Cluster status. `targetPrimary` and target UID survive
  lost replies. An unreachable existing primary blocks promotion: removing
  its routing label is insufficient fencing. `PG_FAILOVER_DELAY` defaults to
  ten seconds; a 120-second Lease guards mutations. Planned
  `postgres.amae.io/switchover-to` requires a replayed WAL barrier. Asynchronous
  failover may lose writes, and this implementation uses emptyDir, not durable
  database storage.

### Helm: history is evidence, and status must agree with it

[`operators/helm.amae`](../operators/helm.amae) runs real Helm commands.
Each failed install attempts uninstall; each failed upgrade attempts rollback
to a revision selected before the batch. Exhaustion still means `Ready=False`
with `InstallStalled` or `UpgradeStalled`, even after successful rollback.
`Released` describes the request; `Remediated` describes recovery. Status
retains ten observed revisions, failed-batch and cumulative attempt counters.

Install/upgrade `remediation.retries` bounds each batch to `1 + retries`.
A stall survives restart. A changed spec or new
`reconcile.fluxcd.io/requestedAt` value enables another batch;
`lastHandledReconcileAt` prevents reusing the same trigger. The finalizer
`finalizers.helm.amae.io` remains until uninstall succeeds. Deployment uses
one replica and Recreate; there is no distributed lock around blocking Helm
operations. Chart permissions require explicit target-namespace bindings.

The [README's fluxcd/pkg#934 analysis](../README.md#helm-releases-and-fluxcdpkg934)
concerns a GitRepository, not a Helm-controller incident. Its reported
intermediate resourceVersion exposed new success conditions with the old
artifact. The pinned helper patches conditions separately from the rest of
status; optimistic locking of the conditions patch does not make those
writes atomic. Local tests model that ordering and a stale concurrent Ready
writer; they do not execute the upstream Go helper.

Amae's controller performs at most one successful whole-status replacement
per reconciliation, using a fresh `metadata.resourceVersion`. Up to five
attempts reread both the CR and Helm and rebuild the status; changed UID,
generation, deletion or request token abandons the old operation result.
Conditions and failure evidence therefore cannot split across this
controller's own successful writes. This does not transact Helm with Kubernetes,
prevent another writer changing status afterward, or guarantee freshness when
all writes fail. A stalled controller does not continuously repair foreign
writes. The retry annotation is a separate policy, not the upstream issue's fix.

## Language properties that matter for infrastructure

Variables fade after 50 untouched soul steps: numbers lose digits, strings
characters, collections trailing entries. Waiting counts. Reading refreshes
the already-faded value; `recall` must happen before information is lost.
This forces attention to the small working set of a loop. Notes explicitly
retain values across waits, but neither notes nor fading automatically bound
memory or provide durable storage. Maps still need pruning.

Rituals share their caller's notes but have their own variables; suspended
caller variables do not age during the ritual. `deterministic` disables
chemistry for infrastructure. The runtime still rotates soul order using the
run count; clocks, API responses and command results remain external inputs.
Tests supply isolated run history, controlled inputs and fake commands where
needed. Amae JSON maps true/false/null to
1/0/empty string, so operators preserve typed templates and values as raw JSON
through jq when exact API types matter.

`meet`, `tell` and `hear` are rendezvous, not buffered channels. `consent to`
and `together` coordinate entry and completion; withdrawal transfers both
participants to `apart`. This complete example shows a cooperative exchange:

```amae
written by "amae"
deterministic

soul pod
    meet node
    consent to node
    together with node
        tell node "prepare"
        hear node into reply
        say reply
    apart
        say "pod stopped"
    end
end

soul node
    meet pod
    consent to pod
    together with pod
        hear pod into request
        tell pod "accepted"
    apart
        say "node stopped"
    end
end
```

```output
accepted
```

This language construct does not roll back external effects. Live node consent
is implemented by explicit checks, not by placing kubelet inside this block.
Likewise, runtime scars and counsel's API scar counters are different storage
mechanisms. The compiler checks statically evident dialogue mismatches and
requires `knowingly` for wounds, leaving and confession; it is not a proof of
arbitrary distributed controller safety.

The [compiler](../compiler.amae) itself uses notes for long-lived tables and
`recall` inside long loops. It has no byte-for-byte bootstrap fixed point:
each generation embeds its ancestors and its own lineage. `--lineage` exposes
that history. Recognition compares compiler output after stripping lineage, rather than
proving semantic equivalence for every possible input. `make bootstrap` checks
generations against recorded programs and the compiler.
`core` requires `--give-heart` to rebuild; failed rebuilds leave wounds in
`AMAE_MEMORY`, and `--forgive` allows rebuilding while retaining scars in
lineage. `make ddc` implements the repository's seed/living-generation variant
of diverse double-compiling. Lineage is inspectable provenance, not by itself
a proof that a toolchain is trustworthy. See the
[compiler overview](../README.md#the-compiler-written-in-amae).

## Deployment and evidence boundaries

From the repository root, the existing minimal overlay installs scheduler,
counsel, their namespace/configuration and the Relationship CRD:

```sh
kubectl apply -k deploy/overlays/minimal
kubectl -n amaenetes logs deployment/scheduler
kubectl get relationships.amae.io -A
```

The [counsel manifest](../deploy/base/counsel/resources.yaml) enables divorce
with `COUNSEL_DIVORCE: '1'`; the bare program requires the environment setting.
The [default overlay](../deploy/overlays/default/kustomization.yaml) adds the
other operators. Neither overlay removes kube-scheduler. The
[default-scheduler deployment](../deploy/default-scheduler/resources.yaml)
answers `default-scheduler` and uses Lease `kube-system/kube-scheduler` with
120 seconds. Taking over an existing cluster requires the explicit
[lease handover](../README.md#on-a-real-cluster), not merely installing it.

The recorded [conformance run](../README.md#conformance) used Kubernetes
v1.35.6, 439 serial specs, excluding Disruptive and NoExecuteTaintManager.
Amaenetes was the only active scheduler: kube-scheduler remained a candidate,
while Amaenetes held its Lease throughout. **437 passed out of 439.** One
failure came from leftover `amaenetes.io/seats: "12"`, a configuration limit
Amaenetes honors; the spec passed without it. The other, API chunking with
compacted-away data, also failed on that cluster with kube-scheduler. Neither
was evidence of a scheduling-algorithm failure. This records a scoped run,
not an assertion that every feature or disruptive scenario passed.

Scheduler, counsel, mediator and the five operators poll snapshots rather
than maintaining informer caches. Parting combines watch wakeups with polling.
API lists and subprocesses have costs and can miss intermediate changes.
Relationship status, release history and failover journals persist; refusal
cooldowns, probe baselines, reconnect clocks and Event suppression notes do not.

Unit tests, including tests using fake kubectl, exercise attachment-aware
preemption tie-breaks; they should not be read as proof of that tie-break on
a live cluster. Node-loss experiments
on the small shared stand consume real worker capacity, can strand workloads
behind disruption budgets and can require node replacement and recovery:
on the stand an orphaned disruption budget blocked a drain and a worker had
to be replaced. Budget disruption and recovery time separately; a
documentation test must not stop a worker to substantiate an example.

Every complete Amae block above is compiled and its output compared by the
same [Documentation test](../tests/test_amae.py) used for the tutorial.
Deployment tests check these commands against rendered local manifests,
without applying them. `make`, `make test` and unittest discovery validate
this checkout; they do not rerun the historical cluster conformance experiment.
