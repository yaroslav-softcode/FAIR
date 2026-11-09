## What's new in Free AI Reader 1.7

**Split long texts into chunks**
- New "Split into chunks" switch in the AI MODEL card (next to CPU/GPU): choose 2 to 16 parts and the analysis processes the text part by part — handy for long articles.
- If the text does not fit the model, the warning now tells you exactly how many chunks to set.
- Chunks are split at sentence boundaries; a sentence with an emotion marker always finishes its chunk.

**Three analysis models to choose from**
- During setup you can now pick: QVikhr 3-4B (~2.5 GB, good emotion recognition), Gemma 4 E4B (~5 GB), or Gemma 4 12B (~7.4 GB, uncensored). The choice is available both in the first-run window and in the "model needed" dialog.
- Models are ticked with checkboxes: you can install one, two or all three (QVikhr is pre-selected; at least one is required).
- The last tick cannot be removed: at least one analysis model always stays selected; all captions are shown in full.
- Under the model you now see how much text fits: "8 192 tok. (≈13 306 characters) · VRAM …".

**Alsu voice now ships with emotions**
- The built-in Alsu voice comes with 8 recorded emotions out of the box (joyful, strict, angry, tender, cheerful, scared, commanding, whispering). They also arrive automatically for existing users.

**Vox**
- The regular engine is now simply "Vox" (the fast one is "Vox Turbo"); in setup Vox is marked "(recommended)".
- In the setup window Vox is now listed first and pre-selected; Vox Turbo is below it.
- Separate "Vox already installed" / "Vox Turbo already installed" lines were removed from the setup window — the tick shows the state.

**One-pass analysis**
- The second "volume fitting" model pass was removed: the model now runs exactly once in every mode (10–80%, translation, etc.).

**Fixes**
- The selected number of chunks is applied correctly (it used to always be 4).
- New screens and warnings are fully translated in both languages.

---

## Что нового в Free AI Reader 1.7

**Разбивка длинных текстов на части**
- В карточке «МОДЕЛЬ ИИ» (рядом с Процессор/Видеокарта) — тумблер «Разбить на чанки»: выбираете от 2 до 16 частей, и анализ идёт по частям — удобно для длинных статей.
- Если текст не влезает в модель, окно подскажет, сколько именно частей поставить.
- Части режутся по границам предложений; предложение с маркером эмоции всегда завершает свой чанк.

**Три модели анализа на выбор**
- При установке можно выбрать: QVikhr 3-4B (≈2,5 ГБ, хорошее распознавание эмоций), Gemma 4 E4B (≈5 ГБ) или Gemma 4 12B (≈7,4 ГБ, без цензуры). Выбор — и в окне первичной установки, и в окне «Нужна модель».
- Модели отмечаются галочками: можно поставить одну, две или все три (по умолчанию отмечен QVikhr; минимум одну).
- Последнюю галочку снять нельзя — минимум одна модель всегда остаётся отмеченной; подписи моделей показываются полностью.
- Под моделью теперь видно, сколько текста влезает: «8 192 ток. (≈13 306 знаков) · VRAM…».

**Голос Алсу — с эмоциями из коробки**
- Встроенный голос Алсу теперь идёт с 8 записанными эмоциями (радостный, строгий, гневный, нежный, весёлый, испуганный, командный, шёпотом). У существующих пользователей они появятся автоматически.

**Vox**
- Обычный движок теперь называется просто «Vox» (быстрый — «Vox Turbo»); в установке у Vox пометка «(рекомендуется)».
- В окне установки Vox теперь сверху и отмечен по умолчанию; Vox Turbo — ниже.
- Из окна установки убраны отдельные строки «Vox уже установлен» / «Vox Turbo уже установлен» — состояние видно по галочке.

**Анализ за один проход**
- Убрана «добивка» объёма вторым прогоном модели: теперь модель вызывается ровно один раз во всех режимах (10–80%, перевод и т. д.).

**Исправления**
- Выбранное число чанков применяется корректно (раньше всегда было 4).
- Новые окна и предупреждения полностью переводятся на оба языка.
