# Кратко: конвертация сессий агентов
**Что это.** Отдельный репозиторий про одно: превратить сохранённую сессию агента
(Claude Code, Codex CLI, Muse) в новую сессию другого провайдера или того же
провайдера под другим аккаунтом. Основа: clone-часть спецификации ax v0.7.0
(13.14, 7.8, 8.2) и проверенная процедура переноса Muse между аккаунтами. Всё
ax-специфичное (mesh, leases, терминалы, task-board, host channels, governance) убрано.

**IR.** Canonical Session (логический ID, Workspace Binding, actors: один `main`
плюс subagents) и Canonical Event на каждый факт источника: 26 закрытых kinds
(`user_message`, `tool_call`, `opaque_reasoning`, `compaction`, `usage`,
`opaque_event`...), causal parents, content blocks, Source Evidence с byte ranges.
Всё content-addressed (SHA-256 от JCS). Непонятное становится `opaque_event`, а не
теряется. Каждый элемент получает disposition (`exact`, `semantic`, `summarized`,
`opaque_preserved`, `synthesized`, `omitted`, `unrecoverable`) с reason codes.

**Что убирается.** Credentials, auth, locks, PID, sockets не копируются никогда.
Account-bound артефакты в target не пишутся:
- Muse (проверено): `encrypted_content` у `reasoning_committed`, вложенные копии в
  compaction/projection checkpoints, `id` у `reasoning_replay` без encrypted content.
- Codex (UNVERIFIED): `encrypted_content` у rollout `reasoning` items.
- Claude Code (UNVERIFIED): `signature` у `thinking` (переподписать нельзя, блок
  выкидывается целиком), server item ids.

**Что сохраняется.** Все записи лога (у Muse удаление reasoning records ломает replay),
сообщения, tools как инертная история, subagents; убранные payloads лежат byte-exact в bundle.
Чужие инструкции не становятся инструкциями, usage не идёт в учёт target, tool calls не повторяются.

**Muse -> Claude Code.** Читаем store Muse по UUID; сессия остановлена, `cron.db`
пуст; capture в blobs с закрытым manifest; normalize в IR. Правило выбирает
`target_native_writer`, но Claude Code writer пока не проверен, поэтому сейчас
допустим только `continuation_context`: новая сессия Claude Code (новый UUID,
project key от целевого workspace), вся история Muse в ней одним блоком user context.
Reasoning Muse в Claude не попадает никогда: он зашифрован под аккаунт Muse, а Claude
нужна своя signature. Затем staged read-back, publish без перезаписи, live read-back,
`claude --resume <new-uuid>`, Fidelity Report. С проверенным native writer сообщения
стали бы настоящими записями Claude Code.

**Решить владельцу:** native writer между провайдерами или только continuation context;
порядок провайдеров; сериализация IR; in-place rewrite; проверка Codex/Claude (`UNRESOLVED_QUESTIONS.md`).
