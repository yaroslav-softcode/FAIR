# FAIR 1.10

## Voicing one fragment at a time

- Every voiced fragment keeps its audio in a per-book cache: a ▶ appears in the left column, click it to hear exactly that fragment — no synthesis.
- Right-click a fragment → **"Voice this fragment"**: only this line is synthesised, the rest of the book is left untouched. The book is re-assembled from the ready pieces right away.
- Right-click → **"Assemble book from voiced"**: glue the whole book from cached fragments without synthesising anything.
- The main **"Voice"** button now synthesises only what is missing or outdated. Already voiced fragments are reused from the cache; if everything is ready, no synthesis happens at all and the book plays immediately.
- A fragment whose text or voice changed loses its ▶ — the audio is marked stale automatically.
- Re-assembly after a single fragment no longer shows a "fragments still missing" dialog; the status bar tells you what is going on.

## Volume of the whole voice

- The voice sample window now has a **"Voice volume"** slider (−5…+5, one step = 10%) instead of the "Press and speak for 5–15 seconds" caption. It applies to every line of that voice: in books, in plain speech mode and in sample playback.
- Raising the volume is protected by a peak limiter, so the sound never clips. The setting survives re-recording the sample.
- "Change volume…" on a fragment with an emotion now finds that emotion by the character's **voice** (it used to look it up by the character name and reported "no emotion"). If a sample for that emotion is missing, the window says so honestly and edits the character's overall level.

## Character detection

- Names with an address form are recognised: "дядя Нанди", "тётя Марья", "мистер Пибоди", "старый дядя Нанди", "доктор Смит", "король Гудвин" and about fifty more titles.
- An "Name: — phrase" label at the start of a paragraph also gives the speaker, including titled names.
- The model can no longer invent a character from the first word of a phrase. A name has to be confirmed by the text itself (it must appear inside a sentence, not only as the first word of a phrase). False names like "Надо", "Кого", "Куда", "Пора" fall away.
- Right-click a name in the character panel → **"This is not a character"**. The word is remembered **for the whole book**: its fragments become the author's words, and on every following split — rules or AI — it is never a character again, even when capitalised. Books without a title are kept apart by a text fingerprint.
- Splitting the same chapter again no longer brings back fragments you deleted: the model receives the current fragment list, not the original text.
- The panel button is renamed to **"✨ Mark up voices with AI"**.

---

# FAIR 1.10 (русский)

## Озвучка по фрагментам

- У каждого озвученного фрагмента звук лежит в кэше книги: слева появляется ▶ — нажатие проигрывает именно этот фрагмент, без синтеза.
- Правый клик → **«Озвучить этот фрагмент»**: синтезируется только эта строка, остальная книга не трогается. Книга сразу пересобирается из готовых кусков.
- Правый клик → **«Собрать книгу из озвученного»**: склеить всю книгу из кэша, ничего не синтезируя.
- Общая кнопка **«Озвучить»** синтезирует только недостающее и устаревшее. Уже озвученные фрагменты берутся из кэша; если готово всё — синтеза нет вообще, книга сразу играет.
- Если текст фрагмента или его голос изменились, ▶ у него исчезает — звук помечается устаревшим автоматически.
- Пересборка после озвучки одного фрагмента больше не показывает окно «нужно озвучить ещё сегменты» — всё видно в строке состояния.

## Громкость всего голоса

- В окне образца голоса вместо подписи «Нажмите и говорите 5–15 секунд» — ползунок **«Громкость голоса»** (−5…+5, один шаг = 10%). Он действует на все реплики этого голоса: в книге, в обычной озвучке и при прослушивании образца.
- При повышении громкости работает лимитер — звук не клиппует. Значение сохраняется при перезаписи образца.
- «Изменить громкость…» на реплике с эмоцией теперь находит эту эмоцию по **голосу** персонажа (раньше искалась по имени персонажа и писала «Без эмоции»). Если образца для эмоции нет, окно честно предупреждает и правит общий уровень персонажа.

## Определение персонажей

- Распознаются имена с обращением: «дядя Нанди», «тётя Марья», «мистер Пибоди», «старый дядя Нанди», «доктор Смит», «король Гудвин» и ещё около пятидесяти обращений.
- Метка «Имя: — реплика» в начале абзаца тоже даёт говорящего, в том числе с обращением.
- Модель больше не может придумать персонажа из первого слова реплики. Имя должно подтверждаться самим текстом (встречаться внутри фразы, а не только первым словом). Ложные имена вроде «Надо», «Кого», «Куда», «Пора» отсекаются.
- Правый клик по имени в панели персонажей → **«Это не персонаж»**. Слово запоминается **для всей книги**: его фрагменты становятся словами автора, и при любой следующей разметке — правила или нейросеть — оно больше не персонаж, даже написанное с большой буквы. Книги без названия различаются по отпечатку текста.
- Повторная разметка того же участка не возвращает удалённые фрагменты: модель получает текущий список фрагментов, а не исходный текст.
- Кнопка в панели переименована в **«✨ Разметить голоса нейросетью»**.
