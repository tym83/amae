> Основная версия этого документа — английская: [tutorial.md](tutorial.md).

# Учимся Tainted

Этот учебник ведёт от программы, которая печатает одну строку, до оператора,
который присматривает за кластером Kubernetes. Каждую программу в нём
проверяют тесты: под каждой показано ровно то, что она печатает. Точные
правила, на которых стоит каждая глава, собраны в [справочнике](reference.ru.md).

Компилятор собирают один раз командой `make`, а потом программу компилируют
и запускают:

```
bin/tc program.tainted
./program
```

Tainted помнит каждую программу, которую когда-либо выполнял (см. [главу 22](#22-во-второй-раз)),
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
- [13. Списки и словари](#13-списки-и-словари)
- [14. Вопросы к миру](#14-вопросы-к-миру)
- [15. Перетерпеть боль](#15-перетерпеть-боль)
- [16. Изучить файл](#16-изучить-файл)
- [17. Чувства случаются](#17-чувства-случаются)
- [18. Вместе](#18-вместе)
- [19. Как любят](#19-как-любят)
- [20. Прежде чем души встретятся](#20-прежде-чем-души-встретятся)
- [21. Долгая любовь](#21-долгая-любовь)
- [22. Во второй раз](#22-во-второй-раз)
- [23. Оператор](#23-оператор)
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
потом `i = i + 1`), числа и строки (списки и словари — в [главе 13](#13-списки-и-словари)), `if … else … end` и `while … end`.
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

`hear world` читает строку со стандартного ввода. Когда ввод кончается, он
отдаёт число `0`. Блок `input` выше — то, что получила эта программа.

## 13. Списки и словари

```tainted
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

Кроме чисел и слов, душа может хранить дроби, списки и словари. Список пишут
в квадратных скобках и считают с единицы; словарь пишут в фигурных скобках, и
ключи в нём — слова, которые хранятся в том порядке, в каком их впервые
записали. `put` добавляет в конец списка, `remove` вынимает элемент из списка
или ключ из словаря, а `x[i] = …` меняет то, что лежит внутри, на любой
глубине. `length of` считает элементы, `keys of` перечисляет ключи, а
`place of` находит, где что лежит, или даёт 0.

Дробь получается из числа с точкой или из всякого вычисления, в котором такое
число участвует: `/ 2.0` делит так, как делят дроби, а `/ 2` между целыми
числами по-прежнему округляет вниз. `whole of` возвращает целую часть. `json of`
записывает любое значение в JSON, а `meaning of` читает JSON и превращает его в
списки, словари, числа и слова.

Что душа хранит, то принадлежит ей одной: если положить список в другую
переменную, сказать его другой душе или записать в заметку, он скопируется, и
никто не изменит список за спиной у хозяина. Списки и словари выцветают, как и
всё остальное, и первыми теряют свои последние элементы.

## 14. Вопросы к миру

```tainted
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

`ask world` запускает команду и ждёт её ответа — всего, что она напечатала,
без последнего перевода строки. `telling` даёт команде, что прочесть. Команда,
которая кончилась ошибкой, — это [боль](#15-перетерпеть-боль), и душа может её
перетерпеть.

`write` и `append` записывают текст в файл, `read file` забирает весь файл
обратно, а `lines of` разрезает текст на список строк. `listen to world`
запускает команду, которая не умолкает: каждая сказанная ею строка приходит к
`hear world` вместе со строками стандартного ввода. Пока душа ждёт мира, мир
медлит, но не молчит, и программа продолжает жить.

`world "NAME"` — это значение переменной окружения, `now` — время в секундах,
`wait 5 seconds` даёт остальным душам жить, пока эта спит, а `fate 6` бросает
шестигранную кость: выпадает от 0 до 5.

## 15. Перетерпеть боль

```tainted
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

Ошибка обрывает программу, если только душа, которая её совершила, не терпит.
`endure` начинает то, что может причинить боль; `when it hurts as pain`
говорит, что делать вместо этого, а причина лежит в `pain`. Что бы ни пошло не
так внутри, как бы глубоко в ритуалах это ни случилось, душа возвращается
туда, где начала терпеть, а ритуалы, в которых она побывала по дороге,
обрываются.

## 16. Изучить файл

```tainted
# words.tainted: a few rituals to learn from.
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

`learn "words.tainted"` в начале программы приносит в неё роды и ритуалы
другого файла, будто они были написаны в самой программе. Файл ищут рядом с
программой, потом в библиотеке, `lib/`. Файл, изученный дважды, изучается
один раз, а об ошибке в нём сообщают под его собственным именем:
`tainted: line 3 of words.tainted: expected 'of'`.

## 17. Чувства случаются

```tainted
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

Чувства не объявляют: они случаются в отношениях и меняют их. Рана оставляет
обиду, и пока обида держится, ответы больше не сближают двух душ. Душа,
ранившая того, кто отдал ей сердце, стыдится. Извинение должно назвать рану,
`apologize to ana for scar 1`: извинение за всё сразу не компилируется. Оно
снимает обиду и стыд и оставляет рядом с раной ещё один шрам, потому что рана
остаётся.

`thank` укрепляет того, кто благодарит, `tell … tenderly` говорит слово, которое
не давит на слушающего, а `send` пишет письмо: оно придёт в свой срок, и
прочтут его через `receive`. Письма от ушедших душ нельзя остановить, можно
только прочесть; всё непрочитанное остаётся шрамами.

Воспоминание переписывает. Ana помнила 1999 год, а последним, что она
услышала, прежде чем год выцвел, было 47: теперь она помнит 1997. Кроме того,
души отдаляются друг от друга, пока между ними ничего не происходит, и слова
издалека идут дольше; каждая встреча снова их сближает.

## 18. Вместе

```tainted
# Two moves together, then one of them withdraws halfway through the second.
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

Что две души делают вместе, требует согласия обеих. `together with ben` ждёт,
пока Ben не дойдёт до `together with ana` и обе не скажут `consent to`; внутри
каждая идёт своей дорогой, а на `end` каждая ждёт другую, так что общее дело
делают либо обе, либо ни одна. Любая из двух может отозвать согласие в любой
миг, даже на полпути: тогда обе останавливаются там, где были, и переходят к
`apart`.

```tainted
# Some things anyone trusted may read; some only a heart given lets you near.
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

`note k of S` читает заметку другой души. Для открытой заметки нужно доверие
владельца; заметка за границей, `guard "fear"`, открывается только тому, кому
владелец отдал сердце, и каждое пересечение границы засчитывается с обеих
сторон.

## 19. Как любят

```tainted
# The same meeting, lived by souls who love in different ways.
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

`soul erin is eros` говорит, как душа любит. Стили привязанности, `anxious`,
`avoidant` и `secure` (тревожный, избегающий и надёжный), — это способы ждать:
тревожная душа тратит шаги на то, чтобы спросить, здесь ли ещё другая, а
избегающая опаздывает, даже когда готова. Стили Джона Алана Ли — способы
чувствовать: эрос вспыхивает с первого взгляда и быстро остывает, у людуса
обещания ничего не стоят, сторге медленно начинает доверять и медленно
перестаёт, прагма отдаёт сердце только там, где доверяет, мания ревнует к
каждому слову, а агапе рана не закрывает. Род передаёт свой стиль душам,
которых призывает к жизни.

## 20. Прежде чем души встретятся

Некоторые жизни компилятор отказывается начинать.

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

Когда две души называют друг друга, компилятор по порядку читает, что каждая
будет делать с другой, и одно должно отвечать другому: сказанные слова —
услышанным, встреча — встрече. Две души, которые обе заговаривают первыми или
обе ждут, когда заговорит другая, не уживутся, и программа не компилируется.
То, что случается после раны или ухода, не сравнивается: дальше это история
самих душ.

Признание, рану и уход не отменишь, поэтому их совершают только сознательно:
`knowingly wound bob`. Без этого слова программа не компилируется. И сердце
отдают одной душе за раз: код, который отдаёт его двум по имени, не забрав у
первой через `take back heart from`, тоже не компилируется; если это
всё-таки случается, через имя, вычисленное во время работы, сердце переходит к
другой, и шрам остаётся и у той, что его потеряла, и у той, что его отдала.

## 21. Долгая любовь

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

Страсть и влюблённость — только искра. С первого взгляда — влечение (`lust`),
два года свиданий наполняют страсть, и с той минуты, как она наполнилась,
каждый срок, который двое проводят рядом, строит любовь; её и показывает
`love for`. Каждый срок строит чуть больше прежнего, потому что чем больше
любви, тем быстрее она растёт.

Когда свидания кончаются, искра остывает, и какое-то время их связь только
дружеская. Любовь вместе с ней не остывает: она строится дальше и проявляется
всё сильнее. На третий год рана ещё причиняет боль, но закрыть Миру уже не
может, а извинение прибавляет к тому, что у них есть; к восьмому году та же
рана не оставляет никакой обиды. Построенная любовь возвращает и огонь: с
шестого года страсть снова теплеет, и между ними совершенная любовь, с каждым
годом всё крепче.

## 22. Во второй раз

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
Начиная со второй жизни, есть ещё и химия: на первой встрече пара получает
чуть больше или чуть меньше страсти, чем велят правила, и по коду никто не
угадает, в какую сторону. Двое, сделавшие всё как следует, на этот раз могут и
не полюбить друг друга. Программа, которая начинается строкой `deterministic`,
при каждом запуске проживает одну и ту же жизнь; так живёт инфраструктура.

## 23. Оператор

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
