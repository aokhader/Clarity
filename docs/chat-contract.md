# Chat contract (D49)

The "point and ask" chatbot. This file holds the interfaces that let pipeline, backend and ui-builder build at the same time. Written by the lead before any chat code (the D22 lesson). Backend owns the API shapes, and a change is announced in STATUS. Pipeline owns the `digest/chat.py` interface. Neither is changed without updating this file.

## Rules that never bend

1. **Firm-only.** No chat or search route sits under `/api/p`, and the provider page renders no handle, bar or panel.
2. **Every sentence is cited.**
   - An answer sentence must cite fact ids the model was shown.
   - The only uncited sentence allowed is one marked `not_in_file`, saying the file does not answer. It states no amount or date.
   - Everything else is dropped in code.
   - When a turn is served, a sentence citing a fact that can no longer be rendered is withdrawn, and its figures are checked against today's file like the brief's (D12).
3. **No model call on a GET or on page load.** `POST chat/ask` and `POST chat/turns/{id}/retry` start a background run (the call-notes pattern) and return at once. The UI polls.
4. **The client sends ids, never text, for attached items.** The server resolves each item inside the matter, labels it itself, and returns 422 for anything outside the matter.
5. **No case data** in code, prompts, starters or tests (`tests/no_literals.test.mjs`).
6. **Spend.**
   - **Cap:** `CHAT_DAILY_BUDGET_USD` per matter (default 2), summed from `llm_calls` with purpose `chat` since local midnight. Past it, `POST chat/ask` and `retry` answer 429 and create nothing.
   - **Accounting:** chat cost is reported apart from the digest's cost.
7. **Logs** carry counts and ids, never question or record text.

## API shapes

### Python (`backend/app/schemas.py`, a new section `# --- API: chat (D49) ---`)

```python
class AskFactsRef(BaseModel):
    kind: Literal["facts"] = "facts"
    fact_ids: list[int] = Field(min_length=1, max_length=50)

class AskSourceRef(BaseModel):
    kind: Literal["source"] = "source"
    source_id: int

class AskProviderRef(BaseModel):
    kind: Literal["provider"] = "provider"
    contact_id: int  # Clio contact id, as ProviderOut.contact_id

class AskCallRef(BaseModel):
    kind: Literal["call"] = "call"
    call_id: int

class AskKpiRef(BaseModel):
    kind: Literal["kpi"] = "kpi"
    name: Literal["case_value", "coverage", "medical_specials", "firm_spend"]  # KpiOut.name

class AskStageRef(BaseModel):
    kind: Literal["stage"] = "stage"

AskItemRef = Annotated[
    AskFactsRef | AskSourceRef | AskProviderRef | AskCallRef | AskKpiRef | AskStageRef,
    Field(discriminator="kind"),
]

class ChatAskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)  # stripped; blank is 422
    items: list[AskItemRef] = Field(default_factory=list, max_length=8)
    thread_id: int | None = None  # None starts a new thread

class AskItemOut(BaseModel):
    ref: AskItemRef
    label: str  # built by the server from generic words, the kind and a date, e.g. "Bill, Mar 3, 2025";
                # a provider item names the contact as Clio does ("Provider, <name>"), firm routes only (lead, D49)
    facts: list[FactRef]  # what the item resolved to, at most 50

ChatTurnStatus = Literal["running", "done", "failed", "no_model"]

class ChatSentenceOut(BaseModel):
    # A superset of BriefSentenceOut, so the brief's sentence component renders it.
    text: str
    facts: list[FactRef]  # empty only when not_in_file
    verdict: SentenceVerdict
    mentions: list[DraftMentionOut]
    not_in_file: bool

class ChatTurnOut(BaseModel):
    turn_id: int
    thread_id: int
    question: str
    items: list[AskItemOut]
    status: ChatTurnStatus
    sentences: list[ChatSentenceOut]  # empty unless done
    no_answer: bool  # the model found nothing in the file that answers
    withdrawn: int  # sentences hidden at serve time, since a cited fact is no longer renderable
    error: str | None  # failed: a short reason, never record text
    cost_micro_usd: int | None  # the answer's model call, None while running or when cached
    asked_by: str | None  # the stub user's name
    asked_at: datetime
    answered_at: datetime | None

class ChatThreadOut(BaseModel):
    thread_id: int
    title: str  # the first question, cut to 80 characters
    created_at: datetime
    updated_at: datetime
    turns: list[ChatTurnOut]  # oldest first

class ChatThreadSummaryOut(BaseModel):
    thread_id: int
    title: str
    updated_at: datetime
    turn_count: int
    last_status: ChatTurnStatus
    asked_by: str | None  # who started the thread

class ChatBudgetOut(BaseModel):
    spent_today_micro_usd: int
    cap_micro_usd: int
    resets_at: datetime  # the next local midnight, timezone-aware
    configured: bool  # CHAT_MODEL, the key and the chat prices are set
```

**Additive change to `CostOut`:** add `chat_calls: int` and `chat_cost_micro_usd: int`. The existing fields go on counting the digest only (every purpose but `chat`).

### TypeScript (`frontend/src/api/types.ts`, the same commit as `schemas.py`)

```ts
export type AskItemRef =
  | { kind: 'facts'; fact_ids: number[] }
  | { kind: 'source'; source_id: number }
  | { kind: 'provider'; contact_id: number }
  | { kind: 'call'; call_id: number }
  | { kind: 'kpi'; name: KpiOut['name'] }
  | { kind: 'stage' }

export interface ChatAskIn {
  question: string
  items: AskItemRef[]
  thread_id: number | null
}

export interface AskItemOut {
  ref: AskItemRef
  label: string
  facts: FactRef[]
}

export type ChatTurnStatus = 'running' | 'done' | 'failed' | 'no_model'

export interface ChatSentenceOut {
  text: string
  facts: FactRef[]
  verdict: SentenceVerdict
  mentions: DraftMentionOut[]
  not_in_file: boolean
}

export interface ChatTurnOut {
  turn_id: number
  thread_id: number
  question: string
  items: AskItemOut[]
  status: ChatTurnStatus
  sentences: ChatSentenceOut[]
  no_answer: boolean
  withdrawn: number
  error: string | null
  cost_micro_usd: number | null
  asked_by: string | null
  asked_at: string
  answered_at: string | null
}

export interface ChatThreadOut {
  thread_id: number
  title: string
  created_at: string
  updated_at: string
  turns: ChatTurnOut[]
}

export interface ChatThreadSummaryOut {
  thread_id: number
  title: string
  updated_at: string
  turn_count: number
  last_status: ChatTurnStatus
  asked_by: string | null
}

export interface ChatBudgetOut {
  spent_today_micro_usd: number
  cap_micro_usd: number
  resets_at: string
  configured: boolean
}
```

`CostOut` gains `chat_calls: number` and `chat_cost_micro_usd: number`.

## Routes (`backend/app/api/chat.py`, mounted in `main.py`)

All firm routes go under `/api/matters/{matter_id}`. An unknown matter returns 404. Routes that act take the stub user from `X-User-Id` (the `CurrentUser` dependency).

| Method and path | Body / query | Answer |
|---|---|---|
| `POST /chat/ask` | `ChatAskIn` | 202 `ChatTurnOut` (status running, or no_model when chat is not configured). 404 when the thread is in another matter. 409 when the thread already has a running turn. 422 when an item does not resolve in this matter. 429 over the daily cap. |
| `GET /chat/threads` | | `ChatThreadSummaryOut[]`: not archived, newest first |
| `GET /chat/threads/{thread_id}` | | `ChatThreadOut`, or 404 when the thread is in another matter |
| `POST /chat/turns/{turn_id}/retry` | | 202 `ChatTurnOut`. 409 unless the turn is failed or no_model. 404 when the turn is in another matter. 429 over the cap. |
| `POST /chat/threads/{thread_id}/archive` | | 204 |
| `GET /chat/budget` | | `ChatBudgetOut` |
| `GET /search` | `q` (2–200 characters), `limit` (1–20, default 12) | `FactOut[]`: renderable facts matching `q` at word starts, ranked by the chat ranker, one row per restatement group (restated_by filled), no model call |

## Pipeline interface (`backend/app/digest/chat.py`, owned by pipeline)

Backend's `services/chat_context.py` builds a `ChatInput`, and `services/chat.py` calls `answer_question` from the background thread.

```python
@dataclass
class PageExcerpt:
    source_id: int
    page_no: int | None
    text: str            # already cut to CHAT_PAGE_CHARS by the caller
    fact_ids: list[int]  # renderable facts read from this page; the only ids the model may cite for it

@dataclass
class AttachedItem:
    label: str           # AskItemOut.label
    facts: list[Fact]    # renderable facts, restatements included, at most 50
    pages: list[PageExcerpt]

@dataclass
class PriorTurn:
    question: str
    answer: str          # the shown sentences of a done turn, joined; "" for a failed turn

@dataclass
class ChatInput:
    overview: list[Fact]                          # stage, incident, KPI and brief facts
    brief_sentences: list[tuple[str, list[int]]]  # the stored brief's sentences and their ids
    attached: list[AttachedItem]
    retrieved: list[Fact]                         # ranked for the question, CHAT_CONTEXT_FACTS at most
    pages: list[PageExcerpt]                      # for retrieved facts, CHAT_CONTEXT_PAGES at most
    history: list[PriorTurn]                      # the thread's last CHAT_HISTORY_TURNS, oldest first

@dataclass
class ChatAnswerSentence:
    text: str
    fact_ids: list[int]  # empty only when not_in_file
    not_in_file: bool

@dataclass
class ChatAnswer:
    sentences: list[ChatAnswerSentence]  # after the code checks
    no_answer: bool
    dropped: int                         # sentences the code checks removed
    llm_call_id: int | None              # the llm_calls row for this answer
    error: str | None                    # set when the call failed; sentences then empty

def answer_question(
    session: Session, *, matter_id: int, question: str, chat_input: ChatInput
) -> ChatAnswer: ...
```

- **One model call.**
  - It goes through `llm.call` with `purpose="chat"`, `role="chat"` and `prompt=load_prompt("chat_answer")`, inside `llm.retrying_failed_calls()`.
  - The model input is JSON built like the brief's: rows from `brief.fact_row` (made public from `_row`), the computed `key_figures` with their fact ids, page excerpts with their source labelled, and the history.
  - The attached items come first and are marked as what the user pointed at.
- **Citable ids:** every fact id in the input, plus the ids behind `key_figures`.
- **Checks in code:**
  - Drop a sentence citing any id outside the citable set.
  - Drop a sentence with no ids unless it is `not_in_file`.
  - Drop a `not_in_file` sentence that states an amount or date.
- **Unconfigured chat:** raises `llm.ModelsNotConfigured` (backend turns this into `no_model`).

## Settings (`backend/app/config.py`; names in `.env` / `.env.example`)

| Variable | Default | Meaning |
|---|---|---|
| `CHAT_MODEL` | none | e.g. `claude-sonnet-5-5` |
| `CHAT_PRICE_IN`, `CHAT_PRICE_OUT` | none | USD per million tokens (2 and 10 for Sonnet 5.5) |
| `CHAT_FALLBACK_PRICE_IN`, `CHAT_FALLBACK_PRICE_OUT` | 5, 25 | Price used when the server-side refusal fallback answered with another model |
| `CHAT_MAX_OUTPUT_TOKENS` | 16000 | The model thinks before answering, and thinking counts against this |
| `CHAT_EFFORT` | `medium` | `low`, `medium`, `high`, `xhigh` or `max`; sent as `output_config.effort` |
| `CHAT_RPM` | 0 | 0 means no pacing of its own. The same model as merge shares its limiter (D36) |
| `CHAT_DAILY_BUDGET_USD` | 2 | Per matter, from local midnight |
| `CHAT_CONTEXT_FACTS` | 40 | Retrieved facts per question (D50; was 60) |
| `CHAT_ITEM_FACTS` | 25 | Rows sent for each item pointed at, its most significant first (D50) |
| `CHAT_CONTEXT_PAGES` | 6 | Page excerpts per question, attached items' pages included |
| `CHAT_PAGE_CHARS` | 3000 | Characters per page excerpt |
| `CHAT_HISTORY_TURNS` | 4 | Earlier turns of the thread sent with a follow-up |

`settings.chat_configured` is true when the key, `CHAT_MODEL` and both chat prices are set.

## Tables (`backend/app/models.py`, new tables only, so no `cli reset`)

- **`chat_threads`:** `id`, `matter_id` (index), `created_by` (FK users), `title`, `created_at`, `updated_at`, `archived_at`.
- **`chat_turns`:**
  - `id`, `thread_id` (FK, cascade, index), `matter_id` (index), `asked_by` (FK users).
  - `question`, `items_json` (the refs as sent).
  - `status`, `answer_json` (`{sentences:[{text, fact_ids, not_in_file}], no_answer, dropped}`), `context_fact_ids_json`.
  - `llm_call_id` (FK `llm_calls`, set null), `error`, `created_at`, `finished_at`.
- **No verdicts are stored.** They are computed each time a turn is served.

## Frontend names (ui-builder)

- **`src/api/chat.ts`:**
  - `useAsk(matterId)` and `useRetryTurn(matterId)` are mutations that invalidate the thread and the budget.
  - `useChatThreads(matterId)`, `useChatThread(matterId, threadId)` (polls every 1.5 s while any turn is running), `useChatBudget(matterId)`.
  - `useAskSearch(matterId, q)`: debounced, enabled from 2 characters.
- **`src/lib/askContext.tsx`:** `AskProvider` and `useAsk…` context, holding whether the panel is open, the thread, the draft, the items and pick mode. It is mounted in `MatterPage` only.
- **`src/lib/useAskTarget.ts`:** `useAskTarget(ref: AskItemRef | null, starter: StarterKind)` returns the props that mark an element as a target. Outside `AskProvider` it returns `{}`.
- **`src/lib/askStarters.ts`:** `StarterKind` is `'bill' | 'deadline' | 'event' | 'injury' | 'kpi' | 'provider' | 'call' | 'document' | 'stage' | 'fact'`, with 2–3 generic questions each.
- **`src/components/ask/`:** `AskBar`, `AskHandle`, `AskItemChip`, `ChatPanel`, `ChatTurn`, `AskView`.
