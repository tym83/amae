# Tainted

Tainted is an esoteric programming language in which computation happens
between souls rather than inside them. A program is a set of souls running side
by side. They reach each other only by meeting, they trust and fear, give their
hearts away, wound and forgive, and what they say to each other stays with them.

The language is Turing complete, and the proof is not built on memory, which
fades, but on trust: a counter machine runs on how much one soul trusts another.

```
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

- [Learning Tainted](docs/tutorial.md): a tutorial in fourteen chapters, from
  one soul to a Kubernetes operator; every program in it is tested.
- [Tainted reference](docs/reference.md): every statement and expression, and
  exactly how time, meetings, feelings and memory work.

This README is an overview.

## Running

Tainted is a compiled language. Its compiler is written in Tainted and makes C,
which any C11 compiler builds together with the runtime in `runtime/`.

```
make                                      # the compiler, from its seed in boot/tc.c
bin/tc examples/hello.tainted             # compile a program
./hello
./courtship --feelings                    # print every relationship at the end
make bootstrap                            # the compiler compiles itself
make test                                 # every recorded program, compiled and run
python3 -m unittest discover -s tests     # what the programs mean
```

A C compiler and make; Python only for the tests and the Kubernetes glue.

Every run is recorded in `~/.tainted/history.json` (or the file named by
`TAINTED_HISTORY`) before it starts, so the same program never runs for the
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

`tools/minsky.py` compiles any Minsky counter machine into Tainted. Each counter
becomes a soul, its value is the machine's trust in it, `warm to` increments,
`cool to` decrements and `trust c == 0` tests for zero. Minsky showed that two
counters are enough to simulate any Turing machine. The test suite compiles
random two-counter machines and checks every result against a reference
simulator.

```
python3 tools/minsky.py examples/multiply.minsky > examples/multiply.tainted
bin/tc examples/multiply.tainted && ./multiply   # c = 42
```

## Operators

`kube/world.py` lets a Tainted program live in a Kubernetes cluster. The
cluster becomes the program's world: every tick it says what it looks like,
one line per node and pod, and the program, which listens with `hear world`,
answers with `say`. A soul that waits for the world is not stuck, the world is
only slow, so the program lives as long as the cluster talks to it. Only a few
answers change the cluster: `cordon`, `uncordon`, `evict`,
`annotate node` and `log`.

```
tick 7
node worker-2 ready cordoned leaving
pod shop/web-5d8f worker-2 ready shop/ReplicaSet/web-5d8f
end
```

`kube/parting.tainted` is the first operator written in Tainted. A node
annotated `taintednetes.io/leaving: "true"` leaves the cluster gently: it stops
taking anyone new and lets its pods go one at a time, the next one only when
the last is gone and its owner has brought a replacement up. A pod that belongs
to no controller has nowhere to come back from, so the node does not send it
away and waits instead. When the node is empty it is marked
`taintednetes.io/left: "true"`.

```
python3 kube/world.py --context <ctx> kube/parting.tainted
kubectl --context <ctx> annotate node worker-3 taintednetes.io/leaving=true
```

Run next to the scheduler, the whole cycle is in Tainted: the operator lets a
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

## The compiler written in Tainted

`compiler.tainted` is the compiler, and it is the only implementation of the
language. It hears a program from standard input and says C: every soul, kind
and ritual becomes a table of instructions and a step function, every
expression a C function evaluated left to right, and `runtime/tainted.c` carries
out what happens between souls. `bin/tc` puts the two together.

```
make                 # build/tc-core, from the seed boot/tc.c
make bootstrap       # generation 1 compiles itself into 2, 2 into 3; 2 and 3 are compared
make seed            # after a change to the compiler: the new generation becomes the seed
```

The seed is the C the compiler says of its own source; the compiler built from
it says that seed back, byte for byte. Every program in `tests/golden/` was
recorded once with everything it printed, lamented and felt on its first and
second run; `make test` compiles each of them and compares.

The compiler's memory fades like anyone's. Writing out a long function takes
more than fifty steps, and a compiler that does not recall the name of the
function it is writing loses letters from it and emits C that does not build.
The test suite checks this too: remove that `recall` and the compiler, built,
can no longer compile itself.

## Taintednetes

`taintednetes.tainted` is a scheduler written in Tainted. It hears the cluster
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
bin/tc taintednetes.tainted && ./taintednetes < examples/cluster.txt
```

### On a real cluster

`kube/bridge.py` makes `taintednetes.tainted` the scheduler of a real
Kubernetes cluster. It reads pending pods with `schedulerName: taintednetes`
and the ready nodes through `kubectl`, describes them to the Tainted program
and binds every pod where the program says it lives. The bridge decides only
who may meet whom: a pod likes the nodes it fits on (free CPU and memory, node
selector, taints it tolerates), a node offers as many seats as it can hold of
the largest pod that wants it.

| Annotation | On | Meaning |
|---|---|---|
| `taintednetes.io/likes: "node-a node-b"` | pod | nodes it wants first |
| `taintednetes.io/likes: "ns/pod ns/pod"` | node | pods it wants first |
| `taintednetes.io/seats: "N"` | node | at most N pods of this scheduler |

Without annotations, pods prefer nodes with more free cores, and where the
nodes are equal every pod has its own lasting taste, so identical pods spread
out; nodes prefer pods with higher priority, then the ones waiting longest.

```
kubectl --context <ctx> create namespace demo
sed -e s/NODE_A/<node>/ -e s/NODE_B/<node>/ kube/demo.yaml \
  | kubectl --context <ctx> -n demo apply -f -
python3 kube/bridge.py --context <ctx> --once     # or leave it running
```

On a cluster with three workers limited to two seats each, seven pods compete
for six places:

```
scarcity/cache settles on 9bwmk
scarcity/db settles on cw2gd
scarcity/web settles on 9bwmk
scarcity/crowd-5bb975f679-7ldmw is sent away from 9bwmk
scarcity/crowd-5bb975f679-7ldmw settles on qtrkn
scarcity/crowd-5bb975f679-srctc is sent away from qtrkn
scarcity/crowd-5bb975f679-srctc has nowhere to live
...
the cluster is at rest
```

The six who found a home are running; the seventh stays pending until a seat
opens.

### Inside the cluster

`kube/deploy.yaml` runs the scheduler and the parting operator as pods of the
cluster they look after, each with a service account that may do no more than
its job: the scheduler reads pods and nodes and creates bindings, the operator
reads them, patches nodes and evicts pods. Both are compiled from Tainted into
the image `ghcr.io/tym83/tainted`, which CI builds from every commit to main:

```
kubectl --context <ctx> create namespace taintednetes
kubectl --context <ctx> apply -f kube/deploy.yaml
kubectl --context <ctx> -n taintednetes logs -f deploy/scheduler
```

## Examples

| File | What happens |
|---|---|
| `hello.tainted` | a first meeting |
| `courtship.tainted` | answered words and promises grow into consummate love |
| `rush.tainted` | three unanswered messages frighten bob |
| `heart-and-knife.tainted` | trust as a gift survives a wound |
| `calculation.tainted` | trust as a calculation does not |
| `breakup.tainted` | leaving, scars, and the one who keeps waiting |
| `first-time.tainted` | run it twice |
| `penelope.tainted` | memory fades while she waits |
| `multiply.tainted` | 6 × 7 computed on trust alone |

### A life

`a-life.tainted` is the one to run first. Two souls meet at first sight, one
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

`a-long-love.tainted` shows what time does. Mira and Teo meet at first sight;
two years of dates feed a passion that does not grow without end, every
answered question builds intimacy, and the wedding brings commitment. Then
they stop running to meet: passion cools, while time spent close binds them,
and attachment lets them live through a wound and an apology. What remains in
the sixth year is calm and strong.

```
they meet: lust, infatuation
year 1: attraction, romantic love; passion 6, intimacy 59, commitment 0, attachment 1
year 2: attachment, consummate love; passion 6, intimacy 119, commitment 3, attachment 3
year 3: attachment, companionate love; passion 2, intimacy 179, commitment 3, attachment 4
      mira resents it: 1, and is still open to him
      after his apology: 0
year 4: attachment, companionate love; passion 0, intimacy 121, commitment 3, attachment 6
year 5: attachment, companionate love; passion 0, intimacy 181, commitment 3, attachment 7
year 6: attachment, companionate love; passion 0, intimacy 241, commitment 3, attachment 8
mira and teo: companionate love, attachment
```

### Classic programs

The usual programs, the way souls would write them, in `examples/classics/`.

| File | What it shows |
|---|---|
| `hello-world.tainted` | one soul, alone |
| `fizzbuzz.tainted`, `factorial.tainted`, `fibonacci.tainted`, `primes.tainted` | ordinary arithmetic and loops |
| `bottles.tainted` | 99 bottles of beer |
| `cat.tainted`, `reverse.tainted`, `wc.tainted` | reading the world line by line |
| `sort.tainted` | insertion sort over notes, because a list in memory would fade |
| `gcd.tainted` | Euclid as a conversation between two souls |
| `ping-pong.tainted` | answered messages grow into romantic love |
| `producer-consumer.tainted` | a producer that never waits for an answer frightens its consumer |
| `sleep-sort.tainted` | every number becomes a soul that waits as long as it is large |
| `hanoi.tainted` | towers of Hanoi, a ritual that performs itself |
| `philosophers.tainted` | dining philosophers: forks are souls, and the host listens for silence |

## License

Apache License 2.0, see [LICENSE](LICENSE).
