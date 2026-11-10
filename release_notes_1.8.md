## What's new in Free AI Reader 1.8

**Voice design for Vox (new)**
- New "✨ Design voice" button in the Vox card — same place as in Qwen. Describe the timbre in words, type a test phrase, listen to the generated voice and keep it if you like it.
- 30 ready descriptions as buttons (5 per row): a click puts the wording into the field, your own text stays and gets extended, choosing another preset replaces the previous one.
- The chip label is Russian, the model receives the English wording — Vox follows English descriptions far more accurately.
- A saved design voice becomes a normal Vox voice: a WAV reference (voices/design_vox_*.wav) that can be cloned and used with emotions.

**Qwen voice design: English wording, Russian labels**
- The dialog now says it openly: describe the timbre in English. The language of the spoken text is picked automatically, so English description + Russian phrase is normal.
- Same 30 preset chips as in Vox (Russian label, English wording sent to the model).
- Your existing Russian voice "passports" are translated by a built-in phrasebook right before the model sees them — the line under the voice shows the wording that actually goes to the model.

**Vox voice list: a fly-out palette**
- Click the voice field and a palette of chips opens: names instead of numbers, rows filled by width, no scrolling. Click a chip to choose; Esc, a click outside or a second click on the field close it.
- Under the field you now see "name — description", like Qwen voices.
- Under a saved Vox sample the card shows the full English description the voice was made from (older entries with a short Russian label are upgraded to the full wording).

**Per-emotion volume**
- Every emotion line got a volume slider next to "▶": 11 positions, the middle one is the recorded level, one step is 10%. It affects both the preview and the narration in that emotion.

**Books and long texts**
- "By chapters" switch: FB2/EPUB chapter markers are detected, the app narrates chapter by chapter and warns when a part does not fit.
- Chapter titles are no longer spoken twice.
- The chunk count field no longer insists on 2–16: enter what you need.
- The speech model is unloaded before the analysis model loads, and loads back automatically ("⏳ Loading voice…").

**Fixes**
- Switching Vox → Qwen no longer breaks the layout: Qwen could keep showing Vox voices and the palette.
- Clicking a voice in the palette did not select it — the palette closed before the click finished.
- Emotion list scrolling fixed (only the first four rows were reachable); the mouse wheel over the volume slider no longer blocks scrolling the list.
- "🎙 Voice sample" button moved right after the design buttons — order: Design / Settings, Sample, voice field, Speed.
- Error in Vox emotion synthesis fixed.

---

## Что нового в Free AI Reader 1.8

**Дизайн голоса для Vox (новое)**
- В карточке Vox появилась кнопка «✨ Дизайн голоса» — на том же месте, что и у Qwen. Описываешь тембр словами, вводишь фразу прослушки, слушаешь получившийся голос и сохраняешь, если нравится.
- 30 готовых формулировками кнопками (рядами по 5): клик вставляет формулировку в поле, свой текст остаётся и дополняется, а выбор другого пресета заменяет прежний.
- Подпись кнопки по-русски, а в модель уходит английская формулировка — так Vox попадает в тембр заметно точнее.
- Сохранённый дизайн-голос работает как обычный голос Vox: WAV-эталон (voices/design_vox_*.wav), который клонируется и дружит с эмоциями.

**Дизайн голоса Qwen: английские формулировки, русские подписи**
- В окне прямо сказано: тембр описывай по-английски. Язык речи модель берёт из текста, поэтому «английское описание + русская фраза» — это норма.
- Те же 30 чипов-пресетов, что у Vox (подпись по-русски, в модель — английская формулировка).
- Уже сохранённые русские «паспорта» голосов переводятся встроенным учебником фраз прямо перед тем, как попасть в модель; строка под голосом показывает то, что реально уходит в модель.

**Список голосов Vox — вылетающая палитра**
- Клик по полю голоса открывает палитру чипов: имена вместо номеров, ряды заполняются по ширине, без прокрутки. Клик по чипу выбирает, Esc / клик мимо / второй клик по полю закрывают.
- Под полем видно «имя — описание», как у голосов Qwen.
- Под сохранённым образцом Vox показывается полное английское описание, по которому голос создавался (старые записи с короткой русской меткой обновляются на полную формулировку).

**Громкость эмоций**
- У каждой строки эмоции появился ползунок громкости рядом с «▶»: 11 положений, середина — записанный уровень, один шаг — 10 %. Влияет и на прослушку, и на озвучку этой эмоцией.

**Книги и длинные тексты**
- Галочка «по главам»: метки глав из FB2/EPUB распознаются, озвучка идёт глава за главой, с предупреждениями, если часть не влезает.
- Название главы больше не читается дважды.
- Поле числа чанков больше не заставляет держать 2–16: ставь сколько нужно.
- Модель озвучки выгружается перед загрузкой модели анализа и возвращается сама («⏳ Загрузка голоса…»).

**Исправления**
- Переключение Vox → Qwen больше не ломает карточку: на Qwen могли оставаться голоса и палитра Vox.
- Клик по голосу в палитре не выбирал его — палитра закрывалась раньше, чем клик завершался.
- Починен прокрутка списка эмоций (было доступно только четыре первые строки); колесо мыши над ползунком громкости больше не мешает прокручивать список.
- Кнопка «🎙 Образец голоса» переехала сразу после кнопок дизайна — порядок: Дизайн / Настройки, Образец, поле голоса, Скорость.
- Исправлена ошибка при синтезе эмоции у Vox.
