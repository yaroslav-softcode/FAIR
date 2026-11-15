# FAIR 1.11

## Book volume you can actually hear

- Volume for a line is now applied **after** loudness levelling and it is never baked into the cache. The cached audio of a book is clean; the voice, character and emotion levels are laid on top when you listen and when the book is assembled. Move a slider and the very next playback sounds different — no re-voicing, no waiting.
- The volume window shows the resulting level as a line: **"character −2 + emotion −3 = −5"**, and **"(limit)"** when the steps add up past the ±5 ceiling (−50 %…+50 %).
- Every gain is followed by a peak limiter, so a boosted line never clips.

## Emotions in books

- The emotion list used for markup is now the **union of the emotions recorded for all voices in the cast**, not just the voice currently selected in the combo box.
- If a character's voice has no sample for an emotion found in the text, the "(emotion)" bracket is **dropped** instead of being read aloud as a word. Numbers like "(2015)" and ordinary parentheses like "(улыбаясь)" are left alone.

## Emotion window

- The emotion column shows the **whole catalogue of 26 emotions at once**, with scrolling, plus one empty row at the bottom for your own emotion.
- Rows no longer jump around or move to another place after a recording is saved, and an empty row is always available.

## Stress for a character

- Right-click a word in the fragment list → **"Add a stress mark…"** → the usual stress window appears (the same one used for a single word). You pick the variant — and it is remembered as a **rule for that character**, not inserted into the text.
- The rule is used in **every line of that character**, survives restarts (stored in settings per book and character), and only that character's fragments are re-voiced in the cache.
- Letter case is preserved: ЗАМОК → ЗА́МОК, Замок → За́мок, замок → за́мок. A stress mark typed by hand in the text always wins over a rule.
- In the character panel the right-click menu now holds only "▶ Listen to the voice" and "This is not a character" — stress marks are set from the fragment list.

## Small things

- The cursor turns into a hand with a pointing finger over the ▶ buttons of voiced fragments.

---

# FAIR 1.11 (русский)

## Громкость книги, которую слышно

- Громкость реплики теперь накладывается **после** выравнивания громкости и никогда не запекается в кэш. В кэше книги лежит чистый звук, а уровни голоса, персонажа и эмоции накладываются при прослушивании и при сборке книги. Двинул ползунок — следующий же проигрыш звучит иначе, без повторной озвучки и ожидания.
- В окне громкости видно, что получилось: строкой **«персонаж −2 + эмоция −3 = −5»**, а при упоре в потолок — **«(предел)»** (±5 шагов = −50 %…+50 %).
- После усиления работает лимитер по пикам — громкая реплика не клиппует.

## Эмоции в книге

- Список эмоций для разметки — теперь **объединение эмоций, записанных для всех голосов каста**, а не только для голоса, выбранного в списке.
- Если у голоса персонажа нет образца для эмоции, которая встретилась в тексте, скобка «(эмоция)» **выбрасывается**, а не читается словом. Числа вроде «(2015)» и обычные пояснения вроде «(улыбаясь)» остаются как есть.

## Окно эмоций

- Колонка эмоций показывает **весь справочник из 26 эмоций сразу**, с прокруткой, и одну пустую строку внизу — для своей эмоции.
- Строки больше не переезжают и не меняют место после сохранения записи, а пустая строка всегда есть.

## Ударения для персонажа

- Правый клик по слову в списке фрагментов → **«Поставить ударение…»** → открывается обычное окно ударений (то же, что для отдельного слова). Выбираешь вариант — и он запоминается **правилом для этого персонажа**, а не вставляется в текст.
- Правило действует во **всех репликах этого персонажа**, сохраняется между запусками (в настройках по книге и персонажу), и в кэше переозвучиваются только его фрагменты.
- Регистр сохраняется: ЗАМОК → ЗА́МОК, Замок → За́мок, замок → за́мок. Ручная разметка ударения в тексте всегда главнее правила.
- В панели персонажей в правом клике теперь только «▶ Прослушать голос» и «Это не персонаж» — ударения ставятся из списка фрагментов.

## Мелочи

- Курсор над кнопками ▶ у озвученных фрагментов становится рукой с указательным пальцем.
