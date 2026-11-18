# Learning Tainted

This tutorial goes from a program that prints one line to an operator that
looks after a Kubernetes cluster. Every program in it is checked by the test
suite: what you see under each one is exactly what it prints. The
[reference](reference.md) has the precise rules behind every chapter.

Build the compiler once with `make`, then compile a program and run it:

```
bin/tc program.tainted
./program
```

Tainted remembers every program it has run (see [chapter 13](#13-the-second-time)),
so the first run of a program can differ from the ones after it. The outputs
here are of first runs.

- [1. A soul](#1-a-soul)
- [2. Two souls](#2-two-souls)
- [3. Thinking alone](#3-thinking-alone)
- [4. Too many words](#4-too-many-words)
- [5. Trust, promises and bonds](#5-trust-promises-and-bonds)
- [6. The heart and the knife](#6-the-heart-and-the-knife)
- [7. Leaving](#7-leaving)
- [8. Memory fades](#8-memory-fades)
- [9. Many souls](#9-many-souls)
- [10. Rituals](#10-rituals)
- [11. Silence](#11-silence)
- [12. The world](#12-the-world)
- [13. The second time](#13-the-second-time)
- [14. An operator](#14-an-operator)
- [Where to go next](#where-to-go-next)

## 1. A soul

```tainted
soul alice
    say "hello, world"
end
```

```output
hello, world
```

A program is made of souls. A soul is written as `soul <name>`, the things it
does one per line, and `end`. `say` prints a value. When every soul reaches its
`end`, the program ends with exit code 0.

## 2. Two souls

```tainted
soul alice
    meet bob
    tell bob "hello"
    hear bob into reply
    say "alice heard: " + reply
end

soul bob
    meet alice
    hear alice into greeting
    say "bob heard: " + greeting
    tell alice greeting + " to you"
end
```

```output
bob heard: hello
alice heard: hello to you
```

Souls run side by side and share nothing. The only way to give another soul a
value is to tell it, and before that the two have to meet. `meet bob` waits
until bob meets alice; `tell bob "hello"` waits until bob is at
`hear alice into …`; then both go on together, and the value lands in bob's
variable.

Waiting is the heart of the language. A soul that tells someone who never
listens waits forever; if nobody in the world can move any more, the program
ends with exit code 2 and says on standard error who was waiting for whom.

## 3. Thinking alone

```tainted
soul counter
    let i = 1
    while i <= 15
        if i % 15 == 0
            say "FizzBuzz"
        else
            if i % 3 == 0
                say "Fizz"
            else
                if i % 5 == 0
                    say "Buzz"
                else
                    say i
                end
            end
        end
        i = i + 1
    end
end
```

```output
1
2
Fizz
4
Buzz
Fizz
7
8
Fizz
Buzz
11
Fizz
13
14
FizzBuzz
```

Inside a soul, Tainted is an ordinary small language: variables (`let i = 1`,
then `i = i + 1`), whole numbers and strings, `if … else … end` and
`while … end`. `+` joins strings, and a number joined to a string becomes
text. There are no booleans: a comparison is `1` or `0`, and `and`, `or`,
`not` work on them.

## 4. Too many words

```tainted
soul ben
    meet ana
    tell ana "I saw you and forgot my own name"
    tell ana "I will write you a song"
    tell ana "I already told my mother about you"
    tell ana "sorry, that was too much"
end

soul ana
    meet ben
    hear ben into a
    hear ben into b
    hear ben into c
    say "afraid of ben: " + afraid of ben
    say "passion for ben: " + passion ben
    hear ben into d
    say "later, ana hears: " + d
end
```

```output
afraid of ben: 1
passion for ben: 2
later, ana hears: sorry, that was too much
```

Ben says three things in a row and ana answers none of them. On the third,
ana becomes afraid of ben: she stops hearing him for a while, and her passion
for him falls by one. Ben is not stuck, only slowed down: his fourth sentence
waits until her fear passes, and she hears it later.

The rule is about answers. Each word one soul says to another without hearing
anything back adds to the pressure; when it goes beyond the listener's
intimacy with the speaker plus two, the listener is frightened. Between
strangers that is the third word. Answering takes the pressure away and builds
the intimacy that lets the next conversation be longer.

## 5. Trust, promises and bonds

```tainted
soul alice
    meet bob
    let n = 0
    while n < 3
        tell bob "how was your day?"
        hear bob into answer
        warm to bob
        n = n + 1
    end
    promise bob
    promise bob
    promise bob
    say "alice trusts bob " + trust bob + " times over"
    say "alice feels " + bond with bob
end

soul bob
    meet alice
    let n = 0
    while n < 3
        hear alice into question
        tell alice "long, but better now"
        n = n + 1
    end
    say "bob feels " + bond with alice
end
```

```output
bob feels romantic love
alice trusts bob 3 times over
alice feels consummate love
```

Every soul keeps its own view of every soul it has met, and the two views of
one relationship are not the same. They are made of:

- **passion**: three at first sight (two souls meeting for the first time,
  having come to the meeting in the same moment), one for every later meeting,
  cooling while they are apart;
- **intimacy**: one on both sides for every answer;
- **commitment**: one for every `promise`;
- **trust**: counted by the soul itself, `warm to` and `cool to`.

`bond with` names the relationship after Sternberg's triangle of love, by
which of intimacy, passion and commitment have reached three. Bob answered
three times and made no promises: romantic love. Alice also promised:
consummate love.

## 6. The heart and the knife

```tainted
soul alice
    meet bob
    meet carol
    give heart to carol
    hear carol into reply
    say "alice hears carol: " + reply
    say "alice's scar from carol: " + scar 1 of carol
    say "alice's scar from bob: " + scar 1 of bob
    forgive bob
    hear bob into reply
    say "alice forgives bob and hears: " + reply
end

soul bob
    meet alice
    wound alice
    tell alice "I did not mean it"
end

soul carol
    meet alice
    wait
    wait
    wound alice
    tell alice "I am sorry"
end
```

```output
alice hears carol: I am sorry
alice's scar from carol: wounded by carol
alice's scar from bob: wounded by bob
alice forgives bob and hears: I did not mean it
```

`wound` hurts the other soul: its trust in you drops to zero, its intimacy is
halved, and it keeps a scar that says who did it. If it had not given you its
heart, it also closes: it will not hear you or meet you until it forgives.

Alice gave her heart to carol and not to bob. Both wound her and both say
something. She hears carol at once; bob's words wait until she forgives him.
The heart given is what lets a relationship survive a wound. It is also what
`confide` needs: a soul can confide only in someone it gave its heart to.

## 7. Leaving

```tainted
soul ana
    meet ben
    tell ben "stay"
    hear ben into answer
    say "ben's answer: " + answer
    say "ana keeps " + scars of ben + " scars:"
    let i = 1
    while i <= scars of ben
        say "  " + scar i of ben
        i = i + 1
    end
end

soul ben
    meet ana
    hear ana into plea
    tell ana "I met someone at the port"
    leave ana
    say "ben keeps " + scars of ana + " scar: " + scar 1 of ana
end
```

```output
ben's answer: I met someone at the port
ben keeps 1 scar: stay
ana keeps 2 scars:
  I met someone at the port
  ben left
```

`leave` is final for both. Everything each of them heard from the other
becomes a scar, and the one who was left keeps one more: who left. Neither can
reach the other again. Scars are numbered from one: `scars of ben` counts them,
`scar i of ben` reads one.

## 8. Memory fades

```tainted
soul penelope
    let year = 1999
    let name = "Odysseus"
    let days = 0
    while days < 30
        days = days + 1
    end
    say "she remembers the year " + year + " and the name " + name

    let weaving = 0
    while weaving < 60
        weaving = weaving + 1
        recall year
    end
    say "she recalled the year: " + year + "; the name faded: " + name

    note "who" = "Odysseus"
    wait
    say "what she wrote down does not fade: " + note "who"
end
```

```output
she remembers the year 1990 and the name Odysseu
she recalled the year: 1990; the name faded: Ody
what she wrote down does not fade: Odysseus
```

Variables fade with the soul's own life. Every fifty steps a variable is left
untouched, a number loses its last digit and a string its last letter. Reading
a variable touches it, and so does `recall`, which exists only for that.

In the first loop nothing touches `year` and `name` for a month of steps, and
both lose something. In the second loop `recall year` keeps the year, and the
name, still untouched, goes on fading. `note` writes something down instead:
notes never fade. Programs that wait a lot keep what matters in notes.

## 9. Many souls

```tainted
kind worker
    meet anyone as boss
    hear soul named boss into task
    tell soul named boss task + " squared is " + task * task
end

soul boss
    let i = 1
    while i <= 3
        bring worker named "worker " + i
        i = i + 1
    end
    i = 1
    while i <= 3
        meet soul named ("worker " + i)
        tell soul named ("worker " + i) i + 1
        i = i + 1
    end
    i = 1
    while i <= 3
        hear anyone into result from who
        say who + ": " + result
        i = i + 1
    end
end
```

```output
worker 1: 2 squared is 4
worker 2: 3 squared is 9
worker 3: 4 squared is 16
```

A `kind` is a soul that is not born yet. `bring worker named …` brings one to
life under a name computed at run time, and `soul named …` reaches a soul by
such a name. A new soul knows nobody: `meet anyone as boss` meets whoever is
looking for it and remembers their name. `hear anyone into result from who`
hears whoever speaks first and says who it was.

## 10. Rituals

```tainted
ritual gcd a, b
    while b != 0
        let r = a % b
        a = b
        b = r
    end
    give back a
end

ritual factorial n
    if n <= 1
        give back 1
    end
    perform factorial with n - 1 into smaller
    give back n * smaller
end

soul mathematician
    perform gcd with 1071, 462 into g
    say "gcd: " + g
    perform factorial with 20 into f
    say "20! = " + f
end
```

```output
gcd: 21
20! = 2432902008176640000
```

A ritual is a subroutine. It runs as the soul that performs it, with a memory
of its own that holds only its parameters; `give back` ends it with a value,
and `into` names the variable that receives it. Rituals may perform rituals,
themselves included.

While a ritual runs, the variables of the soul that performed it do not fade:
whatever the ritual takes, the soul comes back as it left.

## 11. Silence

```tainted
# A rumour passes from soul to soul. Nobody knows how far it went
# until everyone falls silent.
kind gossip
    meet anyone as teller
    hear soul named teller into rumour
    note "heard" = rumour
    let next = number of part 7 (length of me) of me + 1
    if next <= 5
        bring gossip named "gossip" + next
        meet soul named ("gossip" + next)
        tell soul named ("gossip" + next) rumour + "!"
    end
    wait for silence
    say me + " heard: " + note "heard"
end

soul town
    bring gossip named "gossip1"
    meet soul named "gossip1"
    tell soul named "gossip1" "the miller is rich"
    wait for silence
    say "the town is quiet"
end
```

```output
the town is quiet
gossip1 heard: the miller is rich
gossip2 heard: the miller is rich!
gossip3 heard: the miller is rich!!
gossip4 heard: the miller is rich!!!
gossip5 heard: the miller is rich!!!!
```

The rumour travels five souls far, each one bringing the next to life. Nobody
counts how far it went. `wait for silence` waits until no soul can do anything
any more, and then everyone who waited for silence goes on together.

Silence is how Tainted knows that a computation spread over many souls is
finished. Taintednetes, the scheduler written in Tainted, works this way: pods
and nodes argue until nobody has anything to say, and that silence is a
stable matching.

## 12. The world

```tainted
soul reader
    let lines = 0
    let longest = ""
    hear world into line
    while line != 0
        lines = lines + 1
        if length of line > length of longest
            longest = line
        end
        hear world into line
    end
    say lines + " lines; the longest: " + longest
end
```

```input
to be
or not to be
that is
```

```output
3 lines; the longest: or not to be
```

`hear world` reads a line of standard input. At the end of the input it gives
the number `0`. The `input` above is what this program was given.

## 13. The second time

```tainted
soul stranger
    first time
        say "I have never been here before."
    end
    if runs > 0
        say "Runs before this one: " + runs
    end
end
```

```output
I have never been here before.
```

And run again:

```
Runs before this one: 1
```

Tainted counts how many times every program has run; `runs` is that number
and `first time` runs only the first time. The count belongs to the exact text
of the program, so changing a single character makes it a program that has
never run. The order in which souls take their steps turns by one with every
run, so a program of several souls lives a slightly different life each time.

## 14. An operator

```tainted
# watchman: cordons a node that stops being ready and lets it work again
# once it is back, but only the nodes it cordoned itself.

ritual without name, list
    let rest = ""
    let i = 1
    while i <= words of list
        if word i of list != name
            rest = rest + " " + word i of list
        end
        i = i + 1
    end
    give back rest
end

soul watchman
    note "mine" = ""
    hear world into line
    while line != 0
        if word 1 of line == "node"
            let name = word 2 of line
            let ready = word 3 of line == "ready"
            let open = word 4 of line == "schedulable"
            if not ready and open
                say "cordon " + name
                say "log " + name + " is not ready; nobody new goes there"
                note "mine" = note "mine" + " " + name
            end
            if ready and not open and place of name in note "mine" > 0
                say "uncordon " + name
                say "log " + name + " is back"
                perform without with name, note "mine" into rest
                note "mine" = rest
            end
        end
        if line == "end"
            say "done"
        end
        hear world into line
    end
end
```

```input
tick 1
node w1 ready schedulable staying
node w2 notready schedulable staying
node w3 ready cordoned staying
end
tick 2
node w1 ready schedulable staying
node w2 ready cordoned staying
node w3 ready cordoned staying
end
```

```output
cordon w2
log w2 is not ready; nobody new goes there
done
uncordon w2
log w2 is back
done
```

`kube/world.py` makes a Kubernetes cluster the world of a Tainted program. On
every tick it describes the cluster, a line per node and pod, and ends with
`end`:

```
node NAME ready|notready schedulable|cordoned staying|leaving|left
pod NAMESPACE/NAME NODE ready|waiting NAMESPACE/KIND/OWNER|none
```

Whatever the program says is carried out if it is one of `cordon NODE`,
`uncordon NODE`, `evict NAMESPACE/POD`, `annotate node NODE KEY=VALUE` or
`log TEXT`, and printed otherwise. `done` ends the program's answer to the
tick.

The watchman above is a complete operator. It remembers in a note which nodes
it cordoned, so that it never uncordons one an administrator closed, and uses
a ritual to take a name out of that list. To let it look after a cluster:

```
python3 kube/world.py --context <context> watchman.tainted
```

`kube/parting.tainted` is a larger one: it lets a node leave the cluster
gently, one pod at a time, waiting for each replacement.

## Where to go next

- The [reference](reference.md): every statement, every rule of feeling,
  memory and time, exactly.
- `examples/classics`: FizzBuzz, primes, sorting, the towers of Hanoi, the
  dining philosophers and more.
- `examples/a-life.tainted`: one program in which every rule of the language
  changes the story.
- `taintednetes.tainted` and `kube/parting.tainted`: a scheduler and an
  operator written in Tainted, and the README on running them in a cluster.
