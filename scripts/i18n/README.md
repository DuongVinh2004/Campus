# Moving a screen's text into lib/i18n (B4.4)

Method used for the rooms and timetable screens (2026-11-20). Run from `apps/web`; Vietnamese stays the default, so existing tests keep passing, and `tsc` plus the vitest suite are the safety net.

1. `python ../../scripts/i18n/extract.py src/features/X/Screen.tsx > extract.json` lists three kinds of Vietnamese text: `literals` (JSX text on one line, quoted strings), `lines` (JSX text that fills a whole line) and `mixed` (lines that mix text and expressions, comments excluded by hand).
2. Write a mapping file `{ "Vietnamese": "English", ... }` for literals and lines, and run `python ../../scripts/i18n/apply_literals.py src/features/X/Screen.tsx mapping.json <prefix>`. It replaces the text by `t("<prefix>.N")` and appends the keys to `lib/i18n/vi.ts` and `en.ts`.
3. For mixed lines write `{ "exact original line": ["new line using t(\"key\", {params})", "English with {params}", "Vietnamese with {params}"] }` and run `apply_mixed.py`. Each key must be named in the new line; a line using two keys needs the second added by hand.
4. Add `const t = useT();` to each component that uses it. Module-level label maps become maps of keys (`MessageKey`) translated where shown. Run `npx tsc --noEmit -p .` until it is clean, then the screen's tests, and add one English test (cookie `lang=en`, see `RoomFinder.i18n.test.tsx`).
5. Text that comes from the server or from documents is not translated (`lang.sourceNote`).

Do not translate values used as data keys (for example weekday names used to group items): translate only what is displayed.
