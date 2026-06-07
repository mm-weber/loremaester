# Product Guidelines

## Voice & Tone

### Brand Voice
Technical, concise, and honest. Documentation reads like a senior engineer explaining a system to a
peer — no marketing fluff, no hand-waving over rough edges.

### Voice Attributes
- **Precise:** Name exact commands, files, and versions.
- **Honest:** Surface limitations and license caveats rather than hiding them.
- **Reproducible:** Every instruction should run as written on a clean machine.

### Words We Avoid
- "simply", "just", "obviously" — they hide real friction.
- Vague reassurances ("should work").

## Design Principles

### Principle 1: Simplicity first
Make every change as small as possible; touch the minimum code.
- **Do:** prefer stdlib plus a few well-licensed deps.
- **Don't:** add frameworks for their own sake.

### Principle 2: Permissive by default
Prefer MIT/Apache/BSD dependencies; flag and avoid copyleft / source-available deps on the shipped path.
- **Do:** document the third-party license footprint (`THIRD_PARTY_NOTICES.md`).
- **Don't:** ship Elastic-2.0 / AGPL on the default path silently.

### Principle 3: Reproducible & self-hosted
- **Do:** PEP 723 scripts runnable via `uv`; host-side Docker.
- **Don't:** assume cloud services or hidden global state.

## Error Handling Philosophy

### Error Communication
1. **Be specific:** name exactly what failed (file, page, dependency).
2. **Be actionable:** include the fix (install command, flag).
3. **Don't swallow:** never report success on empty or failed output.

#### Error Message Structure
`[What happened] + [Why, if relevant] + [How to fix it]`

#### Examples
| Bad | Good |
| --- | --- |
| "OCR failed" | "easyocr backend not installed — add `--with easyocr` (see docs/quickstart.md)" |
| (silent empty result) | "OCR returned empty text for Vol-III.pdf [raw_len=0; page_count=16]" |
