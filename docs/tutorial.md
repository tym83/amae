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

Tainted remembers every program it has run (see [chapter 22](#22-the-second-time)),
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
- [13. Lists and maps](#13-lists-and-maps)
- [14. Asking the world](#14-asking-the-world)
- [15. Enduring](#15-enduring)
- [16. Learning](#16-learning)
- [17. Feelings that happen](#17-feelings-that-happen)
- [18. Together](#18-together)
- [19. Ways of loving](#19-ways-of-loving)
- [20. Before souls meet](#20-before-souls-meet)
- [21. A long love](#21-a-long-love)
- [22. The second time](#22-the-second-time)
- [23. An operator](#23-an-operator)
- [Where to go next](#where-to-go-next)

## 1. A soul

```tainted
written by "tainted"

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

A program begins by saying who wrote it. Compiling is a date: the compiler
does not translate a program that has not agreed to it, and `written by` is
how a program agrees. The compiler remembers its authors, and the programs of
an author it does not know yet it reads more carefully.

## 2. Two souls

```tainted
written by "tainted"

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
written by "tainted"

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
then `i = i + 1`), numbers and strings (lists and maps come in [chapter 13](#13-lists-and-maps)), `if … else … end` and
`while … end`. `+` joins strings, and a number joined to a string becomes
text. There are no booleans: a comparison is `1` or `0`, and `and`, `or`,
`not` work on them.

## 4. Too many words

```tainted
written by "tainted"

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
written by "tainted"

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
written by "tainted"

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
    knowingly wound alice
    tell alice "I did not mean it"
end

soul carol
    meet alice
    wait
    wait
    knowingly wound alice
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
written by "tainted"

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
    knowingly leave ana
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
written by "tainted"

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
written by "tainted"

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
written by "tainted"

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

written by "tainted"
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
written by "tainted"

soul reader
    let heard = 0
    let longest = ""
    hear world into line
    while line != 0
        heard = heard + 1
        if length of line > length of longest
            longest = line
        end
        hear world into line
    end
    say heard + " lines; the longest: " + longest
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

## 13. Lists and maps

```tainted
written by "tainted"

soul librarian
    let shelf = ["Ada", "Oberon"]
    put "Modula-2" into shelf
    shelf[1] = "Ada 83"
    say shelf
    say length of shelf + " books, the second is " + shelf[2]

    let years = {"Ada 83": 1983, "Oberon": 1987}
    years["Modula-2"] = 1978
    remove "Oberon" from years
    say years
    say keys of years
    say place of "Modula-2" in years

    let average = (years["Ada 83"] + years["Modula-2"]) / 2.0
    say "on average " + average + ", or " + whole of average
    say json of {"shelf": shelf, "count": length of shelf}
    let order = meaning of "{\"title\": \"Oberon\", \"copies\": [1, 2]}"
    say order["title"] + " in " + length of order["copies"] + " copies"
end
```

```output
["Ada 83", "Oberon", "Modula-2"]
3 books, the second is Oberon
{"Ada 83": 1983, "Modula-2": 1978}
["Ada 83", "Modula-2"]
2
on average 1980.5, or 1980
{"shelf": ["Ada 83", "Oberon", "Modula-2"], "count": 3}
Oberon in 2 copies
```

Besides numbers and words, a soul can keep decimals, lists and maps. A list is
written in brackets and counted from one; a map is written in braces, and its
keys are words kept in the order they were first written. `put` adds to the
end of a list, `remove` takes an item out of a list or a key out of a map, and
`x[i] = …` changes what is inside, however deep. `length of` counts items,
`keys of` lists the keys, and `place of` finds where something is, or gives 0.

A decimal comes from a number with a point, or from any calculation with one:
`/ 2.0` divides as decimals do, while `/ 2` between whole numbers still rounds
down. `whole of` takes the whole part back. `json of` writes any value as JSON
and `meaning of` reads JSON into lists, maps, numbers and words.

What a soul keeps is its own: storing a list into another variable, telling
it to another soul or writing it in a note copies it, so nobody can change a
list behind its owner's back. Lists and maps fade like everything else, losing
their last items first.

## 14. Asking the world

```tainted
written by "tainted"

soul clerk
    ask world "date -u +%Y" into year
    say "the world says it is " + (number of year >= 2026)
    ask world "sort" telling "pear\napple\nfig" into sorted
    say lines of sorted
    write "a letter\n" to file "letter.txt"
    append "and a postscript\n" to file "letter.txt"
    read file "letter.txt" into letter
    say length of lines of letter + " lines in the letter"
    listen to world "echo one; sleep 0.1; echo two"
    hear world into first_word
    hear world into second_word
    say first_word + " then " + second_word
end
```

```output
the world says it is 1
["apple", "fig", "pear"]
2 lines in the letter
one then two
```

`ask world` runs a command and waits for its answer, everything it printed,
without the last line ending. `telling` gives the command something to read.
A command that ends with an error is a [pain](#15-enduring) the soul can
endure.

`write` and `append` put text into a file, `read file` takes a whole file back,
and `lines of` cuts text into a list of its lines. `listen to world` starts a
command that keeps talking: every line it says comes to `hear world`, together
with the lines of standard input. While a soul waits for the world, the world
is slow, not silent, and the program goes on living.

`world "NAME"` is the value of an environment variable, `now` is the time in
seconds, `wait 5 seconds` lets the other souls live while this one sleeps, and
`fate 6` throws a die with six sides, from 0 to 5.

## 15. Enduring

```tainted
written by "tainted"

ritual open_door name
    let doors = {"front": "open"}
    give back doors[name]
end

soul guest
    perform open_door with "front" into state
    say "the front door is " + state
    endure
        perform open_door with "back" into state
        say "this is never said"
    when it hurts as pain
        say "it hurts: " + pain
    end
    endure
        ask world "exit 2" into nothing
    when it hurts as pain
        say "the world refused"
    end
    say "and the guest goes on"
end
```

```output
the front door is open
it hurts: there is nothing under back
the world refused
and the guest goes on
```

A mistake ends the program, unless the soul that makes it is enduring.
`endure` begins what may hurt; `when it hurts as pain` says what to do instead,
with the reason in `pain`. Whatever went wrong inside, however deep in rituals,
the soul comes back to where it endured, and the rituals it was in are let go.

## 16. Learning

```tainted
# words.tainted: a few rituals to learn from.

written by "tainted"
ritual shout text
    ask world "tr a-z A-Z" telling text into loud
    give back loud
end

ritual initials list
    let made = ""
    let i = 1
    while i <= length of list
        made = made + part 1 1 of list[i]
        i = i + 1
    end
    give back made
end
```

```tainted
written by "tainted"

learn "words.tainted"

soul poet
    perform shout with "tainted love" into loud
    say loud
    perform initials with ["soft", "cell"] into short
    say short
end
```

```output
TAINTED LOVE
sc
```

`learn "words.tainted"` at the top of a program brings in the kinds and
rituals of another file, as if they were written in the program. The file is
looked for next to the program, then in the library, `lib/`. A file learned
twice is learned once, and a mistake in it is reported with its own name:
`tainted: line 3 of words.tainted: expected 'of'`.

## 17. Feelings that happen

```tainted
written by "tainted"

soul ana
    meet ben
    let year = 1999
    hear ben into n
    let i = 0
    while i < 20
        i = i + 1
    end
    say "ana remembers " + year
    give heart to ben
    tell ben "ready"
    hear ben into first_words
    say "resentment toward ben: " + resentment toward ben
    tell ben "why?"
    hear ben into sorry
    say "after the apology: " + resentment toward ben + ", trust " + trust ben + ", scars " + scars of ben
    say scar 2 of ben
    hear ben into soft
    say "intimacy after tenderness: " + intimacy ben
    receive from ben into letter
    say "a letter: " + letter
end

soul ben
    meet ana
    tell ana 47
    hear ana into ready
    knowingly wound ana
    say "ben is ashamed: " + ashamed before ana
    tell ana "that hurt, I know"
    hear ana into why
    apologize to ana for scar 1
    say "ben is ashamed: " + ashamed before ana
    tell ana "I am sorry"
    thank ana
    tell ana "always" tenderly
    send ana "from far away"
end
```

```output
ana remembers 1997
ben is ashamed: 1
resentment toward ben: 1
ben is ashamed: 0
after the apology: 0, trust 1, scars 2
ben apologized for: wounded by ben
intimacy after tenderness: 4
a letter: from far away
```

Feelings are not declared; they happen in a relationship and change it. A wound
leaves resentment, and while it lasts answers no longer bring two souls closer.
A soul that wounds someone who gave it their heart is ashamed. An apology has
to name the wound, `apologize to ana for scar 1`: an apology for everything at
once does not compile. It takes away the resentment and the shame and leaves
one more scar beside the wound, because the wound stays.

`thank` strengthens the one who thanks, `tell … tenderly` says a word that puts
no pressure on the listener, and `send` writes a letter that arrives in its own
time, to be read with `receive`. Letters from souls that are gone cannot be
stopped, only read; whatever is left unread stays as scars.

Remembering rewrites. Ana remembered 1999, and the last thing she heard before
the year faded was 47: she now remembers 1997. Souls also drift apart while
nothing passes between them, and words from far away take longer to arrive;
every meeting brings them closer again.

## 18. Together

```tainted
# Two moves together, then one of them withdraws halfway through the second.

written by "tainted"
soul ana
    meet ben
    consent to ben
    together with ben
        tell ben "one, two"
        hear ben into reply
        say "ana: " + reply
    apart
        say "ana: we went apart"
    end
    say "ana: the first dance is done"
    together with ben
        tell ben "three"
        hear ben into reply
        say "ana never hears: " + reply
    apart
        say "ana: ben withdrew, so we both stopped"
    end
end

soul ben
    meet ana
    consent to ana
    together with ana
        hear ana into steps
        tell ana steps + ", three"
    apart
        say "ben: we went apart"
    end
    together with ana
        hear ana into steps
        withdraw consent from ana
        say "ben never says this"
    apart
        say "ben: I withdrew"
    end
end
```

```output
ana: one, two, three
ana: the first dance is done
ana: ben withdrew, so we both stopped
ben: I withdrew
```

What two souls do together needs the consent of both. `together with ben` waits
until Ben is at `together with ana` and both have said `consent to`; inside,
each goes its own way, and at the `end` each waits for the other, so what is
done together is done by both or by neither. Either may withdraw consent at
any moment, even halfway: then both stop where they are and go to `apart`.

```tainted
# Some things anyone trusted may read; some only a heart given lets you near.

written by "tainted"
soul ana
    meet ben
    meet cal
    note "song" = "Tainted Love"
    note "fear" = "the sea"
    guard "fear"
    warm to ben
    warm to cal
    give heart to ben
    tell ben "go on"
    tell cal "go on"
end

soul ben
    meet ana
    hear ana into go
    say "ben reads ana's song: " + note "song" of ana
    say "ben crosses ana's boundary: " + note "fear" of ana
    say "crossings with ana: " + crossings with ana
end

soul cal
    meet ana
    hear ana into go
    say "cal reads ana's song: " + note "song" of ana
    endure
        say note "fear" of ana
    when it hurts as pain
        say "cal: " + pain
    end
end
```

```output
ben reads ana's song: Tainted Love
cal reads ana's song: Tainted Love
ben crosses ana's boundary: the sea
crossings with ana: 1
cal: ana keeps fear behind a boundary cal may not cross
```

`note k of S` reads another soul's note. A note in the open needs the owner's
trust; a note behind its boundary, `guard "fear"`, opens only to someone the
owner gave its heart to, and every crossing is counted on both sides.

## 19. Ways of loving

```tainted
# The same meeting, lived by souls who love in different ways.

written by "tainted"
soul erin is eros
    meet luca
    say "erin at first sight: passion " + passion luca
    promise luca
    say "erin promised: commitment " + commitment luca
    hear luca into promise_words
end

soul luca is ludus
    meet erin
    promise erin
    promise erin
    say "luca promised twice: commitment " + commitment erin
    tell erin "forever"
    meet stella
    tell stella "see you"
end

soul stella is storge
    meet luca
    warm to luca
    warm to luca
    warm to luca
    warm to luca
    cool to luca
    say "stella warmed four times and cooled once: trust " + trust luca
    hear luca into bye
    meet prue
    warm to prue
    warm to prue
    warm to prue
    warm to prue
    hear prue into brace
    wait
    wait
    say "stella, wounded, still trusts prue " + trust prue + " and resents it: " + resentment toward prue
end

soul prue is pragma
    meet stella
    warm to stella
    endure
        give heart to stella
    when it hurts as pain
        say pain
    end
    tell stella "brace yourself"
    knowingly wound stella
    meet aga
    knowingly wound aga
    tell aga "and you"
end

soul aga is agape
    meet prue
    hear prue into heard_words
    say "aga, wounded, still hears: " + heard_words + ", resentment " + resentment toward prue
end
```

```output
erin at first sight: passion 5
luca promised twice: commitment 0
erin promised: commitment 1
stella warmed four times and cooled once: trust 2
prue gives its heart only where it trusts, and trusts stella only 1
stella, wounded, still trusts prue 1 and resents it: 1
aga, wounded, still hears: and you, resentment 0
```

`soul erin is eros` says how a soul loves. The attachment styles, `anxious`,
`avoidant` and `secure`, are ways of waiting: an anxious soul spends steps
asking whether the other is still there, an avoidant one comes late even when
it is ready. The styles of John Alan Lee are ways of feeling: eros burns at
first sight and cools fast, ludus promises nothing, storge is slow to trust and
slow to lose it, pragma gives its heart only where it trusts, mania is jealous
of every word, agape is not closed by a wound. A kind passes its style to the
souls it brings to life.

## 20. Before souls meet

Some lives the compiler refuses to begin.

```
soul alice
    meet bob
    tell bob "hello"
end

soul bob
    meet alice
    tell alice "hi"
end
```

```
tainted: line 3: alice and bob cannot get along: here alice tells bob, but at line 8 bob tells alice
```

When two souls name each other, the compiler reads what each will do with the
other, in order, and the two must fit: words told answer words heard, a
meeting answers a meeting. Two souls who both speak first, or both wait to
hear, cannot get along, and the program does not compile. What happens after
a wound or a leaving is not compared: from there it is the souls' story.

A confession, a wound and a leaving cannot be undone, so they are only done
knowingly: `knowingly wound bob`. Without the word, the program does not
compile. And a heart is given to one at a time: code that gives it to two by
name without `take back heart from` the first does not compile either; if it
happens anyway, through a name computed while the program runs, the heart
moves and both the one who lost it and the one who gave it keep the scar.

## 21. A long love

```tainted
# A long love: passion is only the spark; love is built, and grows stronger
# every year.
#
# Mira and Teo meet. For two years every day is a date, and passion is full:
# that is the spark, and from then on every stretch of time they spend close
# builds love, and the more love there is, the more each stretch builds. They
# marry, and keep talking every day without running to meet. Twice Teo hurts
# Mira. In the third year it still hurts, and he apologizes; in the eighth,
# love is stronger than the hurt. Every year Mira says where they are.

written by "tainted"

ritual season of_whom, year
    let who = of_whom
    give back "year " + year + ": " + phase with soul named who + ", " + bond with soul named who + "; passion " + passion soul named who + ", love " + love for soul named who
end

soul mira
    meet teo
    say "they meet: " + phase with teo + ", " + bond with teo + ", love " + love for teo
    note "year" = 1
    while note "year" <= 10
        note "day" = 1
        while note "day" <= 30
            if note "year" <= 2
                meet teo
            end
            tell teo "how was your day?"
            hear teo into answer
            wait
            wait
            note "day" = note "day" + 1
        end
        if note "year" == 2
            promise teo
            promise teo
            promise teo
        end
        if note "year" == 3 or note "year" == 8
            hear teo into hurtful
            say "      year " + note "year" + ", he hurts her: resentment " + resentment toward teo + ", still open"
            tell teo "that hurt"
            hear teo into sorry
        end
        perform season with "teo", note "year" into said
        say said
        note "year" = note "year" + 1
    end
    say "mira and teo, ten years on: " + bond with teo + ", " + phase with teo
end

soul teo
    meet mira
    note "her scars" = 0
    note "year" = 1
    while note "year" <= 10
        note "day" = 1
        while note "day" <= 30
            if note "year" <= 2
                meet mira
            end
            hear mira into question
            tell mira "better now that you ask"
            wait
            wait
            note "day" = note "day" + 1
        end
        if note "year" == 2
            promise mira
            promise mira
            promise mira
        end
        if note "year" == 3 or note "year" == 8
            note "her scars" = note "her scars" + 1
            knowingly wound mira
            tell mira "I said what I should not have"
            hear mira into how_it_felt
            apologize to mira for scar note "her scars"
            note "her scars" = note "her scars" + 1
            tell mira "I am sorry"
        end
        note "year" = note "year" + 1
    end
end
```

```output
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

Passion and infatuation are only the spark. First sight is lust, two years of
dates fill passion up, and from the moment it is full, every stretch of time
the two spend close builds love, which `love for` shows. Each stretch builds a
little more than the last, because the more love there is, the faster it
grows.

When the dates stop, the spark cools, and for a while their bond is only
companionate. Love does not cool with it: it goes on being built, and it shows
more and more. In the third year a wound still hurts, but cannot close Mira,
and the apology adds to what they have; by the eighth year the same wound
leaves no resentment at all. Built love brings back the fire, too: from the
sixth year their passion is warm again, and what they have is consummate love,
stronger every year.

## 22. The second time

```tainted
written by "tainted"

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
From the second life on there is chemistry too: at their first meeting, a pair
gets a little more or a little less passion than the rules say, and nobody can
work out which from the code. Two souls who did everything right may not fall
in love this time. A program that starts with the line `deterministic` lives
the same life every run; infrastructure does.

## 23. An operator

```tainted
# watchman: cordons a node that stops being ready and lets it work again
# once it is back, but only the nodes it cordoned itself.

written by "tainted"

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

The watchman above is a complete operator. It remembers in a note which nodes
it cordoned, so that it never uncordons one an administrator closed, and uses
a ritual to take a name out of that list. Here it hears the cluster as lines,
which is how it is tested. To look after a real cluster, it reads the cluster
itself: `learn "kube.tainted"` brings in rituals that ask kubectl (in the
context named by `KUBE_CONTEXT`) and read what it says, and `listen to world`
on `kubectl get nodes --watch-only` wakes the watchman whenever a node changes:

```tainted
# watchman.tainted: the watchman, looking after a cluster itself.

written by "tainted"

learn "kube.tainted"

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
    listen to world "while :; do kubectl --context '" + world "KUBE_CONTEXT" + "' get nodes --watch-only -o name; sleep 1; done"
    hear world into change
    while change != 0
        perform get_all with "nodes" into nodes
        let i = 1
        while i <= length of nodes
            let name = nodes[i]["metadata"]["name"]
            perform field with nodes[i]["spec"], "unschedulable", 0 into cordoned
            let ready = 0
            let conditions = nodes[i]["status"]["conditions"]
            let k = 1
            while k <= length of conditions
                if conditions[k]["type"] == "Ready"
                    ready = conditions[k]["status"] == "True"
                end
                k = k + 1
            end
            if not ready and not cordoned
                perform kubectl with "cordon " + name into said
                say name + " is not ready; nobody new goes there"
                note "mine" = note "mine" + " " + name
            end
            if ready and cordoned and place of name in note "mine" > 0
                perform kubectl with "uncordon " + name into said
                say name + " is back"
                perform without with name, note "mine" into rest
                note "mine" = rest
            end
            recall nodes
            i = i + 1
        end
        hear world into change
    end
end
```

```
bin/tc watchman.tainted && KUBE_CONTEXT=<context> ./watchman --patience=0
```

`--patience=0` lets it live as long as the cluster does.

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
