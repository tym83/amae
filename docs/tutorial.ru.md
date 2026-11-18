> Основная версия этого документа — английская: [tutorial.md](tutorial.md).

# Учимся Tainted

Этот учебник ведёт от программы, которая печатает одну строку, до оператора,
который присматривает за кластером Kubernetes. Каждую программу в нём
проверяют тесты: под каждой показано ровно то, что она печатает. Точные
правила, на которых стоит каждая глава, собраны в [справочнике](reference.ru.md).

Программу запускают так:

```
python3 tainted.py program.tainted
```

Tainted помнит каждую программу, которую когда-либо выполнял (см. [главу 13](#13-во-второй-раз)),
поэтому первый запуск программы может отличаться от последующих. Здесь
показан вывод первых запусков.

- [1. Душа](#1-душа)
- [2. Две души](#2-две-души)
- [3. Наедине с собой](#3-наедине-с-собой)
- [4. Слишком много слов](#4-слишком-много-слов)
- [5. Доверие, обещания и узы](#5-доверие-обещания-и-узы)
- [6. Сердце и нож](#6-сердце-и-нож)
- [7. Уход](#7-уход)
- [8. Память выцветает](#8-память-выцветает)
- [9. Много душ](#9-много-душ)
- [10. Ритуалы](#10-ритуалы)
- [11. Тишина](#11-тишина)
- [12. Мир](#12-мир)
- [13. Во второй раз](#13-во-второй-раз)
- [14. Оператор](#14-оператор)
- [Куда двигаться дальше](#куда-двигаться-дальше)

## 1. Душа

```tainted
soul alice
    say "hello, world"
end
```

```output
hello, world
```

Программа состоит из душ. Душу записывают так: `soul <имя>`, затем по строке
на каждое её действие и в конце `end`. `say` печатает значение. Когда каждая
душа доходит до своего `end`, программа завершается с кодом выхода 0.

## 2. Две души

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

Души живут бок о бок и ничего не делят между собой. Передать другой душе
значение можно, только сказав его, а прежде двоим нужно встретиться.
`meet bob` ждёт, пока bob не встретит alice; `tell bob "hello"` ждёт, пока bob
не дойдёт до `hear alice into …`; после этого обе идут дальше вместе, а
значение оказывается в переменной bob.

Ожидание — сердце языка. Душа, которая говорит с тем, кто никогда не слушает,
будет ждать вечно; если во всём мире никто больше не может сдвинуться с места,
программа завершается с кодом выхода 2 и сообщает в стандартный поток ошибок,
кто кого ждал.

## 3. Наедине с собой

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

Внутри души Tainted — обычный маленький язык: переменные (`let i = 1`, а
потом `i = i + 1`), целые числа и строки, `if … else … end` и `while … end`.
`+` склеивает строки, а число, приклеенное к строке, становится текстом.
Логического типа нет: сравнение даёт `1` или `0`, и с ними работают `and`,
`or` и `not`.

## 4. Слишком много слов

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

Ben говорит три фразы подряд, и ana не отвечает ни на одну. На третьей ana
начинает его бояться: какое-то время она его не слышит, а её страсть к нему
убывает на единицу. Ben не застрял, его лишь придержали: четвёртая фраза ждёт,
пока страх у ana не пройдёт, и она слышит её позже.

Всё дело в ответах. Каждое слово, которое одна душа говорит другой, ничего не
услышав в ответ, усиливает давление; когда оно превышает близость слушающего с
говорящим больше чем на два, слушающий пугается. Между незнакомцами это
случается на третьем слове. Ответ снимает давление и копит ту близость, благодаря
которой следующий разговор может быть длиннее.

## 5. Доверие, обещания и узы

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

Каждая душа хранит собственный взгляд на всякую душу, с которой встречалась,
и два взгляда на одни и те же отношения не совпадают. Складываются они из
четырёх величин:

- **страсть**: три с первого взгляда (когда две души встречаются впервые и
  пришли на встречу в один и тот же миг), по одной за каждую следующую встречу;
  в разлуке страсть остывает;
- **близость**: по одной с обеих сторон за каждый ответ;
- **обязательство**: по одному за каждое `promise`;
- **доверие**: его душа отсчитывает сама, через `warm to` и `cool to`.

`bond with` называет отношения по треугольнику любви Стернберга — смотря по
тому, какие из трёх величин, близость, страсть и обязательство, дошли до трёх.
Bob ответил трижды и ничего не обещал: это романтическая любовь
(`romantic love`). Alice к тому же дала обещания: совершенная любовь
(`consummate love`).

## 6. Сердце и нож

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

`wound` ранит другую душу: её доверие к вам падает до нуля, близость
уменьшается вдвое, и у неё остаётся шрам с именем того, кто ранил. Если она
не отдавала вам сердца, она ещё и закрывается: не станет ни слушать вас, ни
встречаться с вами, пока не простит.

Alice отдала сердце carol, но не bob. Оба её ранят, и оба потом что-то
говорят. Carol она слышит сразу, а слова bob ждут, пока она его не простит.
Отданное сердце — вот что позволяет отношениям пережить рану. Без него не
обходится и `confide`: довериться душа может только тому, кому отдала сердце.

## 7. Уход

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

`leave` окончательно для обоих. Всё, что каждый слышал от другого,
становится шрамом, а у того, кого оставили, есть ещё один: кто ушёл. Больше
ни один из них не сможет дотянуться до другого. Шрамы нумеруются с единицы:
`scars of ben` их считает, `scar i of ben` читает один из них.

## 8. Память выцветает

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

Переменные выцветают вместе с собственной жизнью души. Каждые пятьдесят
шагов, что переменную никто не трогает, число теряет последнюю цифру, а
строка — последнюю букву. Прочитать переменную значит её тронуть; то же делает
и `recall`, который ради этого только и существует.

В первом цикле `year` и `name` целый месяц шагов никто не трогает, и обе
что-то теряют. Во втором цикле `recall year` сберегает год, а имя, которого
по-прежнему никто не касается, выцветает дальше. `note` же записывает
значение в заметку: заметки не выцветают никогда. Программы, которым приходится много
ждать, хранят самое важное в заметках.

## 9. Много душ

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

`kind` — это душа, которая ещё не родилась. `bring worker named …` приводит
такую душу в мир под именем, вычисленным во время работы, а `soul named …`
находит душу по такому имени. Новая душа никого не знает: `meet anyone as boss`
встречает того, кто её ищет, и запоминает его имя. `hear anyone into result from who`
слышит того, кто заговорит первым, и сообщает, кто это был.

## 10. Ритуалы

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

Ритуал — это подпрограмма. Он выполняется от лица души, которая его
совершает, но со своей собственной памятью, где лежат только его параметры;
`give back` завершает ритуал и возвращает значение, а `into` называет
переменную, которая его получит. Ритуалы могут совершать другие ритуалы, в том
числе самих себя.

Пока идёт ритуал, переменные совершившей его души не выцветают: сколько бы
ритуал ни длился, душа возвращается такой же, какой уходила.

## 11. Тишина

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

Слух проходит через пять душ, и каждая приводит в мир следующую. Никто не
считает, далеко ли он ушёл. `wait for silence` ждёт, пока ни одна душа уже
ничего не сможет сделать, и тогда все, кто ждал тишины, идут дальше вместе.

По тишине Tainted и узнаёт, что вычисление, разошедшееся по многим душам,
закончено. Так устроен Taintednetes, планировщик, написанный на Tainted: поды
и ноды спорят, пока никому больше нечего сказать, и эта тишина и есть
устойчивое паросочетание.

## 12. Мир

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

`hear world` читает строку со стандартного ввода. Когда ввод кончается, он
отдаёт число `0`. Блок `input` выше — то, что получила эта программа.

## 13. Во второй раз

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

И если запустить ещё раз:

```
Runs before this one: 1
```

Tainted считает, сколько раз выполнялась каждая программа; `runs` — это число,
а `first time` срабатывает только в первый раз. Счёт привязан к точному тексту
программы, так что стоит изменить в ней хоть один символ, и это уже программа,
которая ни разу не запускалась. Порядок, в котором души делают свои шаги,
сдвигается на одну с каждым запуском, поэтому программа из нескольких душ
всякий раз проживает чуть-чуть другую жизнь.

## 14. Оператор

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

`kube/world.py` делает кластер Kubernetes миром программы на Tainted. На
каждом такте он описывает кластер, по строке на каждую ноду и каждый под, и
заканчивает описание словом `end`:

```
node NAME ready|notready schedulable|cordoned staying|leaving|left
pod NAMESPACE/NAME NODE ready|waiting NAMESPACE/KIND/OWNER|none
```

Всё, что говорит программа, исполняется, если это одна из команд
`cordon NODE`, `uncordon NODE`, `evict NAMESPACE/POD`,
`annotate node NODE KEY=VALUE` или `log TEXT`, а иначе просто печатается.
`done` завершает ответ программы на такт.

Сторож (`watchman`) выше — настоящий оператор, законченный целиком. В заметке он
помнит, какие ноды закрыл сам, чтобы никогда не открыть ту, которую закрыл
администратор, а чтобы вычеркнуть имя из этого списка, совершает ритуал. Чтобы
он присматривал за кластером, запустите:

```
python3 kube/world.py --context <context> watchman.tainted
```

`kube/parting.tainted` — оператор побольше: он бережно отпускает ноду из
кластера, по одному поду за раз, дожидаясь замены каждого.

## Куда двигаться дальше

- [Справочник](reference.ru.md): каждая инструкция, каждое правило чувств,
  памяти и времени, со всей точностью.
- `examples/classics`: FizzBuzz, простые числа, сортировка, Ханойские башни,
  обедающие философы и многое другое.
- `examples/a-life.tainted`: одна программа, в которой каждое правило языка
  меняет ход истории.
- `taintednetes.tainted` и `kube/parting.tainted`: планировщик и оператор,
  написанные на Tainted, а в [README](../README.ru.md) рассказано, как
  запустить их в кластере.
