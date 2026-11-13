# FAIR 1.9

## Book by voices

- Voices per character for whole books: a fragment list on the right ("number · character │ phrase"), a character panel with voices on the left, a default voice on top that transfers to every character who used the previous one.
- Automatic split by characters with manual correction: change a character, edit a fragment, delete a fragment, or play any line from a chosen point.
- **AI split** button: the model marks speakers and always separates the author's words ("— заметила Озма") into their own line. The app double-checks the model's answer and splits author's words itself if the model skips them — including cases with a hyphen instead of a dash, indirect cases and epithets ("отвечал большой Страшила").
- Voices are remembered **per book**: switch to another book and back — your cast returns. Different books never mix.
- Only the loaded chapter is split: nested fb2 sections are unpacked, so 28 chapters of a single-section book are offered as 28 chapters.
- Stress marks right in the book: right-click a fragment → "Edit text" or the "Stress" button in the header — the word list opens in the same window.
- Play button next to every character: listen to that character's voice sample without leaving the book.
- Loudness levelling (EBU R128, −18 LUFS) with per-character gain, quiet emotions (whisper, sad, tired) keep their relative level, peak limiter at −1.5 dBFS. "Change volume…" in the right-click menu writes to the same emotion gain you see in the voice settings.

## Voice samples and emotions

- "✨ Synthesise all" in the emotions column: the whole emotion list is synthesised one after another on the Vox engine, one failure does not stop the queue.
- Recording button is now the standard accent colour.
- Ten new voice designs, animals speaking human words: Cat, Dog, Lion, Bear, Fox, Crow, Parrot, Frog, Mouse, Owl.

## Interface

- New warm palette from the redesign mock-up: paper `#FBF8F2`, ink `#211D18`, accent `#B4552B`.
- The book button is now the app accent colour; "Add emotions" sits next to it in the header.
- Default window width is 1240 px so the whole header fits without clipping.
- Fixed: "Save" and "Cancel" buttons were pushed out of the edit-text window.
- One instance only: launching FAIR twice brings the existing window to front instead of opening a second one.

---

# FAIR 1.9 (русский)

## Книга по голосам

- Голоса за каждым персонажем для целых книг: справа список фрагментов «номер · персонаж │ фраза», слева панель персонажей с голосами, сверху голос по умолчанию — при его смене меняются все, у кого стоял прежний.
- Автоматическая разметка по персонажам с ручной правкой: сменить персонажа, изменить текст, удалить фрагмент, озвучить с любого места.
- Кнопка **«✨ Разметить нейросетью»**: модель проставляет говорящих и всегда выносит слова автора («— заметила Озма») отдельной строкой. Программа проверяет ответ модели и разделяет слова автора сама, если модель их пропустила — в том числе с дефисом вместо тире, в косвенных падежах и по эпитетам («отвечал большой Страшила»).
- Голоса запоминаются **по книгам**: вернулись к прежней книге — прежний состав персонажей на месте. Разные книги не смешиваются.
- Размечается только загруженный участок: вложенные секции fb2 разворачиваются, поэтому книга с одной внешней секцией предлагает все 28 глав.
- Ударение прямо в книге: правый клик по фрагменту → «Изменить текст» или кнопка «Ударение» в шапке — список вариантов открывается в том же окне.
- Кнопка ▶ у каждого персонажа: прослушать образец его голоса, не выходя из книги.
- Выравнивание громкости (EBU R128, −18 LUFS) со сдвигом на персонажа: шёпот и грустные эмоции сохраняют относительную громкость, лимитер −1,5 dBFS. «Изменить громкость…» в правом клике пишет в тот же ползунок эмоции, что в настройках голоса.

## Образцы голоса и эмоции

- «✨ Синтезировать все» в колонке эмоций: весь список эмоций синтезируется подряд на движке Vox, сбой одной не останавливает очередь.
- Кнопка записи образца — стандартного акцентного цвета.
- Десять новых вариантов дизайна голоса — звери, говорящие по-человечески: Кот, Пёс, Лев, Медведь, Лиса, Ворона, Попугай, Лягушка, Мышонок, Сова.

## Интерфейс

- Новая тёплая палитра из макета: бумага `#FBF8F2`, тушь `#211D18`, акцент `#B4552B`.
- Кнопка книги — фирменного акцентного цвета; рядом в шапке «Добавить эмоции».
- Стандартная ширина окна 1240 px — шапка помещается целиком.
- Исправлено: кнопки «Сохранить» и «Отмена» уезжали за край окна правки текста.
- Одна копия приложения: повторный запуск поднимает уже открытое окно.
