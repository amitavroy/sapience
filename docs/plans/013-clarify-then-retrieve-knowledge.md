# Add clarify-then-retrieve knowledge search to FocalBot (GH-8)

## To-do

Each slice ends in a working, reviewable state with passing tests. Pause for review after each slice. Builds on GH-7 (plan 012): the conversation graph, the per-(space, user) queue and the stub `search_knowledge` tool.

| # | Slice | Step | Done |
|---|-------|------|------|
| 1 | Answers from the knowledge base | `app/core/config.py` + `.env.example`: `LLM_CLASSIFY_MODEL`; `app/agent/models.py`: `classify` role (Decision 12) | [x] |
| 1 | Answers from the knowledge base | Sender identity at the webhook: `users.google_chat_user_id` (nullable, unique) and nullable `password_hash`, one migration; `authenticate` rejects a user with no password; `GOOGLE_CHAT_ALLOWED_EMAIL_DOMAINS` in `config.py` + `.env.example`; `resolve_chat_user` in `app/services/user.py` (domain check, link, create); `get_chat_sender` dependency after `get_verified_chat_event`; a sender it rejects gets `NO_ACCESS_REPLY` and nothing is queued (Decision 4) | [ ] |
| 1 | Answers from the knowledge base | The resolved id travels instead of the email: `process_chat_event(chat, trace_id, app_user_id)`; `QueueItem.user_id` and `ConversationContext.user_id` replace the uncommitted `.email` fields (Decision 4) | [ ] |
| 1 | Answers from the knowledge base | `app/services/retrieval.py`: `RetrievedChunk`, `probe(db, user_id, vectors, k)` as one `UNION ALL` query, `deep_search(db, user_id, vector, doc_ids, k)`, membership by user id in the same query; the `KnowledgeSearch` protocol (Decisions 4, 5, 6) | [ ] |
| 1 | Answers from the knowledge base | `app/tasks/conversation.py`: `TaskKnowledgeSearch` (embeds, then opens `task_session()` per search); passed to the graph through `ConversationContext.search` (Decision 7) | [ ] |
| 1 | Answers from the knowledge base | Graph nodes `needs_kb` (classify), `rewrite` (chat, 2–3 queries), `probe`, `grade` (chat, structured), `deep_retrieve`; `knowledge` in state; the system prompt lists the retrieved chunks with their sources; `ambiguous` handled as `clear` until slice 2 (Decisions 1, 2, 3, 8) | [ ] |
| 1 | Answers from the knowledge base | `search_knowledge` tool: real deep search over the asker's collections, for follow-ups (Decision 9) | [ ] |
| 1 | Answers from the knowledge base | Tests: routing for small talk / no collections / no match / clear; grade output validated (unknown doc ids dropped); one `probe` call per turn with every query vector; chunks reach the agent prompt; tool uses the user id from context; failures in search end in the apology | [ ] |
| 1 | Answers from the knowledge base | Manual (pgvector): ingest two pages into a collection you are a member of; ask about one; the reply cites it; `EXPLAIN` the probe query uses the HNSW index; a Chat account with no app user is created on its first mention, gets the "couldn't find anything" reply, and cannot log in; an account outside the allowed domains gets the no-access reply | [ ] |
| 2 | Clarifying buttons | `GoogleChatClient.create_card_message` and `update_message`; `google_chat.send_card` / `edit_card` (Decision 14) | [ ] |
| 2 | Clarifying buttons | Graph: `grade` → `ask_clarification` (`interrupt(payload)`) → `resolve_choice` → `deep_retrieve`; `run_turn` returns `TurnResult` (reply text, or a card to post) (Decisions 10, 11) | [ ] |
| 2 | Clarifying buttons | Webhook: `buttonClickedPayload` + `commonEventObject.parameters` → enqueue a `choice` item; respond with an update that disables the buttons; clicks from anyone but the asker get no update (Decisions 13, 15) | [ ] |
| 2 | Clarifying buttons | Drain: a `choice` item resumes the thread with `Command(resume=...)` when the clarification id matches the pending pause, otherwise it is dropped; dedup key `{card_message_name}#click`; the card name is kept in Redis for 30 min (Decisions 11, 15, 16) | [ ] |
| 2 | Clarifying buttons | Conversation log: a click is recorded as a user message "Chose: <label>" (Decision 17) | [ ] |
| 2 | Clarifying buttons | Tests: ambiguous → card with ≤3 options + "None of these", thread paused, no reply text; click → deep search limited to that option's doc ids, answer posted; second click / stale id / other user → dropped, no model call; resume after a failed attempt forks from the paused checkpoint; "None of these" → pause ends, invitation reply | [ ] |
| 2 | Clarifying buttons | Manual: real button click in a space; check the event shape and that the webhook response disables the buttons; a second account clicking does nothing | [ ] |
| 3 | Typed replies while paused | Drain: a `message` item on a paused thread resumes with `{"text", "message_name"}` instead of starting a new run (Decision 11) | [ ] |
| 3 | Typed replies while paused | `resolve_choice`: number / exact label match without a model call; otherwise classify → `option`, `refinement`, `unrelated`, `none`; refinement adds the user's text to the deep-search query; unrelated adds the message to history and routes to `needs_kb` (Decision 18) | [ ] |
| 3 | Typed replies while paused | 30-minute expiry: an expired pause treats a typed message as new and answers a click with "That question has expired. Please ask again."; abandoned and expired cards are edited to say so (Decisions 16, 19) | [ ] |
| 3 | Typed replies while paused | Tests: "2", "the second one"-style label match, refinement, unrelated (handled as new, history has the message once), expired (both kinds), classifier error → apology, pause gone afterwards in every case; card edit failure never blocks the reply | [ ] |
| 3 | Typed replies while paused | Manual: ask an ambiguous question, then type "2"; repeat and type something unrelated; check the old card reads "This question was skipped" | [ ] |
| 4 | Docs | `docs/wiki/retrieval.md` (flow, when it asks, search queries, buttons, typed replies, expiry, settings, troubleshooting); `docs/wiki/conversation.md` and `docs/wiki/google-bot.md` updated; `docs/wiki/index.md` line | [ ] |
| 4 | Docs | `docs/architecture/adr.md`: ADR-002 "Ask a clarifying question only when retrieval is ambiguous" | [ ] |

## Context

FocalBot answers @mentions through a LangGraph agent (GH-7). Its `search_knowledge` tool is a stub, while ingestion and embeddings into `chunks` (pgvector, HNSW cosine index) already exist.

This ticket adds real retrieval. A plain "embed the question and search" often misses: questions are short and lean on the conversation, and a broad question can match several unrelated documents. The flow is therefore:

1. Decide whether the message needs the knowledge base at all.
2. Rewrite it, using the last few messages, into 2–3 broad search queries and run them together (the probe).
3. Grade what came back against the question.
4. If it is clear, search deeper and answer. If it matches nothing, say so. If it is ambiguous, ask the user what they meant using buttons built from the documents found, then search deeper within the chosen documents.

Decisions settled in the design discussion:
- Ask only when the probe is ambiguous; a clear result never triggers a question.
- Options come from what the probe found, decided by a grading node.
- Searches run as a single `UNION ALL` query; keep queries to a minimum.
- Buttons in a Chat card, with a "None of these" button.
- The graph pauses with `interrupt()` and resumes on the click or on the next typed message.
- An unrelated typed reply abandons the question and is handled as a new message.
- Only the asker can answer. A question expires after 30 minutes.
- Search all collections the asker is a member of. A Chat user is linked to an app user by their Chat user id, stored on `users`; the verified email is used once, at first contact, to link an existing user or create one with no password. Only emails in the domains listed in `GOOGLE_CHAT_ALLOWED_EMAIL_DOMAINS` are accepted. This is resolved at the webhook, right after the event is verified; only the app user id travels on, never the email.
- Classification uses Jev (`typesafe/jev-router`) on OpenRouter through a new model role, with no other backend.
- Out of scope: adding members to collections (CLI or API) is a later ticket; until then, membership rows are added by hand.

## Decisions

1. **Ask only when the probe is ambiguous.** The point of asking is precision, but every question costs the user a round trip. So the grader decides, and only `ambiguous` produces a card. A focused result goes straight to the deep search, and a result with nothing relevant gets "I couldn't find anything about that in your knowledge base." Recorded as ADR-002 in slice 4.

2. **Graph shape.**

        START → route
          paused (resume) → resolve_choice ─ option/refinement → deep_retrieve → agent → finalize → END
                                           ├ none → finalize (invitation reply) → END
                                           └ unrelated/expired → needs_kb
          new message → needs_kb ─ no → agent → finalize → END
                          └ yes → rewrite → probe → grade ─ no_match → agent (told nothing was found) → finalize → END
                                                          ├ clear → deep_retrieve → agent → finalize → END
                                                          └ ambiguous → ask_clarification (interrupt) ⏸

   - `route` is not a node with logic of its own: a resumed run starts inside `ask_clarification`, which is where `interrupt()` returns. "Resume" in the diagram is that return path.
   - `ask_clarification` does only one thing: build the payload and call `interrupt()`. LangGraph reruns a paused node from its start on resume, so the probe and the grade must sit in earlier nodes or they would run again on every click.
   - Slice 1 has no `ask_clarification`: `ambiguous` takes the `clear` path, with the probe's top documents.
   - The agent still runs the reply (it writes the answer from the chunks in its prompt), so the summarization middleware and the tool loop stay as they are.

3. **State additions.**

   ```python
   class RetrievedChunk(TypedDict):
       chunk_id: int
       document_id: int
       title: str
       source_uri: str | None
       content: str
       distance: float


   class ConversationState(TypedDict):
       messages: Annotated[list[AnyMessage], add_messages]
       reply: str
       queries: list[str]  # the rewrite's output for this turn
       probe: list[RetrievedChunk]
       knowledge: list[RetrievedChunk]  # what the agent answers from
       search_outcome: str  # "skipped" | "no_match" | "found"
       pending: dict | None  # slice 2: the interrupt payload grade built (Decision 10)
       choice: dict | None  # slice 2: the resume value ask_clarification received
   ```

   - `needs_kb` resets `queries`, `probe`, `knowledge` and `search_outcome` at the start of every new turn, so last turn's chunks never leak into the next answer.
   - Chunks are kept in state (and so in the checkpoint) for one turn only. They are small: the deep search returns at most 8.

4. **Who the asker is, and which collections they search.** Collections belong to app users through `collection_members`; a Chat sender is `users/123` with an optional `email`. Both come from the event Google signs (the webhook verifies its system ID token), never from the model or the message text, the same rule as the space in GH-7. The Chat user id is the stable key: an email can change or be missing, the id does not.
   - **Schema.** `users.google_chat_user_id: str | None`, unique and indexed. `users.password_hash` becomes nullable: a user created from Chat has no password, and `authenticate` rejects a user with no hash the same way as a wrong password. One migration for both.
   - **Resolution.** `resolve_chat_user(db, chat_user_id, email, display_name) -> int | None` in `app/services/user.py`:
     1. A user with that `google_chat_user_id`: their id if active and their stored email is in an allowed domain, else `None`.
     2. Otherwise, if the event's email is in an allowed domain, a user with that email (case-insensitive) and no Chat id yet: the Chat id is saved on them, and their id is returned (if active). A user with that email already linked to a different Chat id is not relinked: `None`, logged as a warning.
     3. Otherwise, if the event's email is in an allowed domain: a new user (`name=display_name`, the email, `password_hash=None`, the Chat id). A unique violation from a concurrent first message rolls back and reads the row again.
     4. No link, and no email or one outside the allowed domains: `None`, and nothing is created.
   - **Allowed email domains.** `GOOGLE_CHAT_ALLOWED_EMAIL_DOMAINS` (comma-separated, e.g. `gmail.com` or `example.com,example.org`) in `config.py` and `.env.example`. Matching is exact on the part after the last `@`, case-insensitive, with no subdomains.
     - Checked on every event, against the stored email for a linked user, so narrowing the setting cuts off users already linked from other domains on their next message.
     - Empty means no Chat user is accepted, the same fail-closed rule as `GOOGLE_CHAT_AUDIENCE`. API logins are unaffected: the setting only gates Chat.
     - It limits who gets an app user, not who can message the bot; that is set by the Chat app's visibility in the Google console. With `gmail.com`, any Gmail account that can reach the bot gets a user with no collections.
   - **Where it runs: a dependency right after verification.** `get_chat_sender(event: VerifiedChatEvent, db: DbSession) -> int | None` in `app/core/deps.py` calls `resolve_chat_user` with `event.chat.user` (the top-level user, present on messages, commands and, in slice 2, clicks). It is a FastAPI dependency, not ASGI middleware: middleware runs before the route verifies the token and would have to parse the body a second time. Persistence stays in the service; the dependency only owns the request's session, like `get_current_user`.
     - It resolves only events the webhook queues (a message or a command); others (e.g. added to a space) return `None` without a lookup and the route answers `{}` as today.
     - The route, for a queued kind with no resolved sender: answers `reply(NO_ACCESS_REPLY)` ("Sorry, your account can't use this bot.") and queues nothing. The log line has the Chat user id and the email's domain.
     - Cost on the webhook: one indexed select, plus one insert on first contact. Google's deadline for an add-on response is far above that.
   - **What travels.** The router passes `app_user_id` to `process_chat_event(chat, trace_id, app_user_id)` next to the chat payload. `_handle_mention` and `_handle_command` put `user_id` on the `QueueItem`, and `process_item` builds `ConversationContext(user_id=...)`. No email is queued or kept in the context or the graph state. The Chat user id (`users/123`) stays the conversation key, as in GH-7.
   - **Between webhook and drain.** A user deactivated after their message was queued still finds nothing: the search's membership filter checks `users.is_active` (below). `user_id` is never `None` in the worker, so there is no "no user" path in the graph.
   - **Searches.** The probe and the deep search filter on `chunks.collection_id IN (select collection_id from collection_members join users on users.id = collection_members.user_id where users.id = :user_id and users.is_active)`, inside the same query, so membership costs no extra round trip.
   - A newly created user is a member of nothing, so their probe is empty and they get the `no_match` reply until someone adds them to a collection.
   - Logs show the resolved user id, and `created` / `linked` on the first contact; never chunk content at info level.

5. **The probe: one embedding call, one SQL query.**
   - `rewrite` (chat model, structured output `{"queries": [str, ...]}`, 2–3 items) sees the new message and the 3 messages before it. It writes broader, self-contained queries ("it" resolved from context).
   - `TaskKnowledgeSearch.probe(user_id, queries)` embeds all queries in one `embedder.embed(queries)` call, then runs one statement:

     ```sql
     (select c.id, c.document_id, d.title, d.source_uri, c.content,
             c.embedding <=> :q0 as distance, 0 as q
        from chunks c join documents d on d.id = c.document_id
       where c.collection_id in (<member collections>) and c.embedding is not null
       order by c.embedding <=> :q0 limit :k)
     union all
     (... :q1 ... 1 as q ...)
     union all
     (... :q2 ... 2 as q ...)
     ```

     Each branch keeps its own `order by … limit` (parenthesised), so each query uses the HNSW index. `k = 5` per query. Results are de-duplicated by chunk id, keeping the smallest distance.
   - Built with SQLAlchemy Core (`union_all` of selects using `Chunk.embedding.cosine_distance(vector)`), not raw text, so the vector binding stays typed.
   - This cannot run under SQLite. It is flagged and verified by hand (Verification), as CLAUDE.md requires; unit tests use a fake `KnowledgeSearch`.

6. **The deep search: one more query, no new embedding on the clear path.**
   - Clear path: reuses the first probe query's vector (kept in memory by `TaskKnowledgeSearch` for the turn, keyed by query text) and searches the documents the grader marked relevant, `k = 8`.
   - Option path (slice 2): embeds `"{original question} — {option label}"` once and searches only that option's `doc_ids`, `k = 8`.
   - Refinement path (slice 3): the same as the option path, with the user's text appended.
   - `deep_search(db, user_id, vector, doc_ids, k)` applies the membership filter as well as the doc ids, so a doc id in a stale checkpoint can never reach a collection the user has since left.

7. **Persistence stays in services; the graph gets a protocol.** Graph nodes are not entry points, so they never open a session.
   - `app/services/retrieval.py` defines `RetrievedChunk`, the query functions taking an `AsyncSession` first, and a `KnowledgeSearch` protocol: `probe(user_id, queries) -> list[RetrievedChunk]` and `deep_search(user_id, query, doc_ids) -> list[RetrievedChunk]`.
   - `TaskKnowledgeSearch` in `app/tasks/conversation.py` implements it, like `TaskConversationLog`: it calls the embedder first and opens `task_session()` only after, for one query each. No session is held during the embedding call or any LLM call.
   - It reaches nodes and the tool through `ConversationContext.search` (runtime context, not state: it is not serializable and the model must not control it). Tests pass a fake.

8. **Grading.** `grade` (chat model, structured output) sees the question, the rewritten queries and the probe chunks (title + the first 300 characters of each), and returns:

   ```python
   class Grade(BaseModel):
       verdict: Literal["clear", "ambiguous", "no_match"]
       relevant_doc_ids: list[int]  # for clear
       options: list[Option]  # for ambiguous, 2–3 items


   class Option(BaseModel):
       label: str  # ≤ 60 chars, shown on the button
       doc_ids: list[int]
   ```

   - The output is checked against the probe: doc ids that were not in the probe are dropped. An option left with no doc ids is dropped. `ambiguous` with fewer than 2 valid options becomes `clear` with the remaining ids, and `clear` with no valid ids becomes `no_match`.
   - An empty probe skips the grader: `no_match` without a model call.
   - Grading stays on the chat model, because it writes the labels and Jev does not generate text.

9. **`search_knowledge` becomes real.** The agent keeps it for follow-ups inside a turn ("and what about X?"). It calls `KnowledgeSearch.deep_search(user_id, query, doc_ids=None)` and returns the chunks formatted with their titles. It reads the user id and the search from runtime context; its schema still has only `query`.

10. **The pause is a LangGraph `interrupt()`.** Buttons make the answer explicit, so pausing the graph and resuming it is the natural model.
    - `ask_clarification` calls `interrupt({"clarification_id": uuid4().hex, "question": str, "options": [...], "asked_at": time.time(), "query": original question})`. The turn ends, and `ainvoke` returns the state with `__interrupt__`.
    - The question text is fixed in code: "Which of these did you mean?" with the options as buttons. No extra model call.
    - The node also adds an `AIMessage` with the question and the option labels as text, so history reads correctly for the agent later.
    - The checkpoint of a paused thread stays the same until resumed, so retries can fork from it as today (GH-7 Decision 11).

11. **Every event on a paused thread resumes it.** `run_turn` reads `graph.aget_state(config)`. If it has a pending interrupt, the turn is `graph.ainvoke(Command(resume=value), config, context=ctx)`; otherwise it starts as today with the `HumanMessage`.
    - A click resumes with `{"kind": "choice", "clarification_id", "option": int | "none", "message_name"}`.
    - A typed message resumes with `{"kind": "text", "text", "message_name"}` (slice 3).
    - Before resuming a click, the service checks that its `clarification_id` matches the pending interrupt. A mismatch (a stale card, a pause already used up) drops the click without running the graph. In slice 2, a typed message on a paused thread is still sent as a resume, and `resolve_choice` treats any text as `unrelated` until slice 3 adds the matching.
    - The service never sends fresh input to a paused thread, so no pause is ever orphaned.
    - `run_turn` returns `TurnResult(reply: str | None, card: ClarificationCard | None)`; the drain posts a card or a text reply.

12. **`classify` model role for Jev.**
    - `Role = Literal["chat", "summary", "classify"]`; `LLM_CLASSIFY_MODEL` in `config.py` and `.env.example`, example value `typesafe/jev-router`. Empty means the chat model, the same rule as `LLM_SUMMARY_MODEL`. It is a config default, not a runtime fallback: a failed classify call is a failed turn.
    - Same OpenRouter endpoint and key (`LLM_BASE_URL`, `LLM_API_KEY`), so no new provider settings.
    - Used only for choice-style calls, always through `with_structured_output(Model)`: `needs_kb` (`{"needs_kb": bool}`) and, in slice 3, `resolve_choice` (`{"kind": "option" | "refinement" | "unrelated" | "none", "option": int | None}`).
    - Jev does not generate free text, so `rewrite`, `grade` and the reply stay on `chat`.
    - A classify error is handled like any other model error: retryable errors retry in the drain, anything else ends in the apology.

13. **Button clicks on the webhook.** Clicks arrive as a third event kind, `chat.buttonClickedPayload` (with `space`, `message`, and the clicker in `chat.user`). The button's parameters are in `commonEventObject.parameters`, outside the `chat` part that is enqueued today.
    - `ChatPayload` gains `button_clicked_payload`. The router adds `commonEventObject.parameters` to the task payload as `action_parameters`, so the worker sees them. The ID token is still never enqueued.
    - `handle_event` routes a click to `_handle_click`, which enqueues `QueueItem(kind="choice", space, user=clicker, message_name=f"{card_message_name}#click", text=label, ...)` with `clarification_id` and `option` from the parameters, then dispatches the drain.
    - The webhook's synchronous response to a click from the asker is an add-on `updateMessageAction` that replaces the buttons with "Looking into: <label>…". That stops a second click and gives instant feedback. The label and the asker id are in the button parameters, so the webhook needs no lookup.
    - A click from anyone else gets `{}` and no queue item. The worker would drop it anyway (Decision 15), but stopping it at the edge keeps it out of the asker's queue.
    - The exact event shape and the accepted response are checked by hand in slice 2 before the code is final: the docs for HTTP add-ons in Chat are the source, and our fixtures are copied from a real captured event.

14. **Cards on the Chat client.**
    - `GoogleChatClient.create_card_message(space, text, cards_v2) -> str` (`POST spaces/*/messages` with `cardsV2`) and `update_message(name, text, cards_v2 | None)` (`PATCH {name}?updateMask=text,cardsV2`), with the same token refresh as `create_message`.
    - `google_chat.send_card(client, space, card)` builds one card: the question as a text paragraph, then a button list of up to 3 options plus "None of these". Each button's `onClick.action` carries `parameters`: `clarification_id`, `option` (index or `none`), `label`, `asker` (the Chat user id).
    - `google_chat.edit_card(client, name, note)` replaces the card with a single line: "This question was skipped." or "This question has expired."
    - A failed edit is logged and never blocks the reply; the stale-click check (Decision 15) keeps an old card harmless anyway.

15. **Only the asker, only once, only the current question.**
    - Threads are per (space, user), and a click is resumed on the thread of the clicker. Another user's thread never has a pause with that `clarification_id`, so their click is dropped even if it got past the webhook.
    - The click dedup key `{card_message_name}#click` uses the existing `seen` key (24 h), so double clicks and Google retries enqueue once.
    - A click whose `clarification_id` is not the pending one is dropped with a log line and no reply.

16. **Card name kept in Redis.** The card's Chat message name is only known after posting, and the pause is already in the checkpoint by then. The drain stores it at `chat:card:{clarification_id}` with `EX 1800` (the expiry), so a later abandon or expiry can edit the card. Missing key (expired, Redis flushed): skip the edit.

17. **Conversation log.** A click is logged as a user message, `text = "Chose: <label>"`, `external_id = {card_message_name}#click`. The card turn's assistant row holds the question text with the card's Chat message name. Everything else follows GH-7 Decision 19 unchanged.

18. **Typed replies to a pending question (slice 3).** `resolve_choice` decides what the text means:
    - Matches `^\s*([1-3])\s*$` or equals an option label (case- and whitespace-insensitive): that option. No model call.
    - Otherwise one classify call with the question, the labels and the text: `option` (with its index), `refinement` (with its index), `none`, or `unrelated`.
    - **option**: the same path as a click.
    - **refinement**: the option's doc ids, with the user's text added to the deep-search query (Decision 6). Jev only picks the option; the text is used as typed.
    - **none**: the same as "None of these": the pause ends and the reply is "No problem. Tell me what you're looking for."
    - **unrelated**: the pause is abandoned, the card is edited to "skipped", and the message is handled as a new one through `needs_kb`.
    - On every resume with text, the node adds `HumanMessage(text, id=message_name)` itself: a resumed message is not graph input, so nothing else would put it in history. The id keeps it from being added twice on a retry.

19. **Expiry: 30 minutes.** `CLARIFICATION_TTL = 1800` seconds, a constant in `graph.py` like the summary thresholds. `resolve_choice` compares `asked_at` with now:
    - A typed message to an expired question is handled as new (as `unrelated`, without the classify call).
    - A click on an expired question ends the pause and replies "That question has expired. Please ask again."
    - Both edit the card to "expired".
    - The queue's own 15-minute TTL on items (GH-7) is separate and unchanged.

20. **Failure while resuming.** A failed resumed turn goes through the existing retries from the paused checkpoint. On final failure `record_failure` writes the apology from that checkpoint as `finalize`, which ends the pause. A later click on that card is then stale and dropped.

## Code sketches

`app/agent/models.py`

```python
Role = Literal["chat", "summary", "classify"]

_ROLE_MODEL = {
    "summary": lambda: settings.llm_summary_model,
    "classify": lambda: settings.llm_classify_model,
}


def get_model(role: Role) -> BaseChatModel:
    model = _ROLE_MODEL.get(role, lambda: "")() or settings.llm_chat_model
    ...  # unchanged
```

`app/services/retrieval.py`

```python
class KnowledgeSearch(Protocol):
    async def probe(self, user_id: int, queries: list[str]) -> list[RetrievedChunk]: ...
    async def deep_search(
        self, user_id: int, query: str, doc_ids: list[int] | None
    ) -> list[RetrievedChunk]: ...


def _member_collections(user_id: int):
    return (
        select(CollectionMember.collection_id)
        .join(User, User.id == CollectionMember.user_id)
        .where(User.id == user_id, User.is_active)
    )


async def probe(
    db: AsyncSession, user_id: int, vectors: list[list[float]], k: int = PROBE_K
) -> list[RetrievedChunk]:
    """Every query's nearest chunks in one round trip; each branch keeps its own index scan."""
    branches = [
        select(
            Chunk.id,
            Chunk.document_id,
            Document.title,
            Document.source_uri,
            Chunk.content,
            Chunk.embedding.cosine_distance(v).label("distance"),
        )
        .join(Document)
        .where(Chunk.collection_id.in_(_member_collections(user_id)), Chunk.embedding.is_not(None))
        .order_by(Chunk.embedding.cosine_distance(v))
        .limit(k)
        .subquery()
        .select()  # parenthesised, so each limit applies to its own branch
        for v in vectors
    ]
    rows = (await db.execute(union_all(*branches))).all()
    return _dedup(rows)
```

`app/services/user.py`

```python
async def resolve_chat_user(
    db: AsyncSession, chat_user_id: str, email: str | None, display_name: str
) -> int | None:
    """The app user behind a Chat sender: linked by Chat id, else by email once, else created."""
    user = await _by_chat_id(db, chat_user_id)
    if user is None and email and _domain_allowed(email):
        user = await _by_email(db, email)
        if user is not None and user.google_chat_user_id not in (None, chat_user_id):
            logger.warning(f"email already linked to another chat user user_id={user.id}")
            return None
        try:
            if user is None:
                user = User(name=display_name, email=email.lower(), password_hash=None)
                db.add(user)
            user.google_chat_user_id = chat_user_id
            await db.commit()
        except IntegrityError:  # a concurrent first message linked or created it
            await db.rollback()
            user = await _by_chat_id(db, chat_user_id)
    if user is None or not user.is_active or not _domain_allowed(user.email):
        return None
    return user.id


def _domain_allowed(email: str) -> bool:
    # exact match on the part after the last "@"; no subdomains; empty setting = nobody
    domain = email.rpartition("@")[2].lower()
    return domain in _allowed_domains()  # parsed from GOOGLE_CHAT_ALLOWED_EMAIL_DOMAINS
```

`app/agent/graph.py` (shape)

```python
graph.add_node("needs_kb", needs_kb)  # classify
graph.add_node("rewrite", rewrite)  # chat, structured
graph.add_node("probe", probe)  # KnowledgeSearch.probe
graph.add_node("grade", grade)  # chat, structured, validated
graph.add_node("ask_clarification", ask_clarification)  # interrupt()
graph.add_node("resolve_choice", resolve_choice)
graph.add_node("deep_retrieve", deep_retrieve)
graph.add_node("agent", run_agent)
graph.add_node("finalize", finalize)
graph.add_edge(START, "needs_kb")
graph.add_conditional_edges("needs_kb", after_needs_kb, ["rewrite", "agent"])
graph.add_edge("rewrite", "probe")
graph.add_edge("probe", "grade")
graph.add_conditional_edges("grade", after_grade, ["ask_clarification", "deep_retrieve", "agent"])
graph.add_edge("ask_clarification", "resolve_choice")
graph.add_conditional_edges(
    "resolve_choice", after_choice, ["deep_retrieve", "finalize", "needs_kb"]
)
graph.add_edge("deep_retrieve", "agent")
graph.add_edge("agent", "finalize")
graph.add_edge("finalize", END)


def ask_clarification(state: ConversationState) -> dict:
    # only builds the payload: on resume LangGraph reruns this node from the top
    answer = interrupt(state["pending"])
    return {"choice": answer}
```

`app/services/conversation.py`

```python
@dataclass(frozen=True)
class TurnResult:
    reply: str | None
    card: ClarificationCard | None


async def run_turn(graph, ctx, item: QueueItem, from_checkpoint: str | None) -> TurnResult:
    config = _config(ctx, from_checkpoint)
    snapshot = await graph.aget_state(config)
    if snapshot.interrupts:
        pending = snapshot.interrupts[0].value
        if item.kind == "choice" and item.clarification_id != pending["clarification_id"]:
            raise StaleChoiceError  # dropped by process_item, no reply
        state = await graph.ainvoke(Command(resume=_resume_value(item)), config, context=ctx)
    elif item.kind == "choice":
        raise StaleChoiceError
    else:
        state = await graph.ainvoke(
            {"messages": [HumanMessage(item.text, id=item.message_name)]}, config, context=ctx
        )
    if "__interrupt__" in state:
        return TurnResult(
            reply=None, card=ClarificationCard.from_payload(state["__interrupt__"][0].value)
        )
    return TurnResult(reply=state["reply"], card=None)
```

`.env.example` (addition)

```
# Model for yes/no and pick-one decisions (does a message need the knowledge base, which
# option a reply means); empty = same as LLM_CHAT_MODEL. Jev on OpenRouter: typesafe/jev-router
LLM_CLASSIFY_MODEL=
```

## Files to create/modify

| File | Slice | Purpose |
|------|-------|---------|
| `app/core/config.py`, `.env.example` | 1 | `LLM_CLASSIFY_MODEL`, `GOOGLE_CHAT_ALLOWED_EMAIL_DOMAINS` |
| `app/agent/models.py` | 1 | `classify` role |
| `app/models/user.py`, `alembic/versions/` | 1 | `google_chat_user_id`, nullable `password_hash` |
| `app/services/user.py` | 1 | `resolve_chat_user`; `authenticate` rejects a user with no password |
| `app/agent/state.py` | 1, 2 | Retrieval fields, `ConversationContext.user_id` (replacing `.email`) and `.search` (1); pending clarification (2) |
| `app/agent/graph.py` | 1, 2, 3 | Retrieval nodes (1); `ask_clarification`, `resolve_choice` for clicks (2); typed replies, expiry (3) |
| `app/agent/nodes/retrieval.py` | 1, 2, 3 | Node functions and their structured-output models, kept out of `graph.py` |
| `app/agent/prompts.py` | 1 | Retrieved chunks and the search outcome in the system prompt |
| `app/agent/tools/knowledge.py` | 1 | Real `search_knowledge` |
| `app/services/retrieval.py` | 1 | `RetrievedChunk`, `probe`, `deep_search`, `KnowledgeSearch` |
| `app/core/deps.py` | 1 | `get_chat_sender` (`VerifiedChatSender`) |
| `app/services/conversation_queue.py` | 1, 2 | `QueueItem.user_id` (1); `kind="choice"`, `clarification_id`, `option` (2) |
| `app/services/conversation.py` | 1, 2, 3 | `ConversationContext.user_id` from the item (1); `TurnResult`, resume logic, card post, card name in Redis (2); typed resume, card edits (3) |
| `app/tasks/google_chat.py` | 1 | `process_chat_event` takes `app_user_id` |
| `app/tasks/conversation.py` | 1 | `TaskKnowledgeSearch` |
| `app/core/google_chat_client.py` | 2 | `create_card_message`, `update_message` |
| `app/services/google_chat.py` | 1, 2 | `user_id` on the item, `NO_ACCESS_REPLY` (1); `_handle_click`, `send_card`, `edit_card`, click response (2) |
| `app/schemas/google_chat.py` | 2 | `ButtonClickedPayload`, `action_parameters` |
| `app/routers/ingest.py` | 1, 2 | Sender dependency, no-access reply, `app_user_id` to the task (1); click events queued with their parameters, click response (2) |
| `tests/agent_helpers.py` | 1 | Fake `KnowledgeSearch`, scripted structured outputs for the fake models |
| `tests/unit/test_retrieval_graph.py` | 1, 2, 3 | Graph routing, grading validation, pause / resume |
| `tests/unit/test_chat_identity.py` | 1 | `resolve_chat_user` under SQLite; login refused with no password |
| `tests/integration/test_google_chat_webhook.py` | 1 | Sender dependency: no-access reply and nothing queued; `app_user_id` reaches the task |
| `tests/unit/test_retrieval_service.py` | 1 | Membership lookup under SQLite (the vector query itself is manual) |
| `tests/unit/test_google_chat_task.py`, `tests/integration/test_google_chat_webhook.py` | 2 | Click intake, asker check, response shape |
| `tests/fixtures/` | 2 | A captured `buttonClickedPayload` event (scrubbed) |
| `docs/wiki/retrieval.md`, `docs/wiki/conversation.md`, `docs/wiki/google-bot.md`, `docs/wiki/index.md` | 4 | Docs |
| `docs/architecture/adr.md` | 4 | ADR-002 |

## Testing plan

No test calls an LLM, Google, Redis, or pgvector.
- Models: the existing fake model, extended to answer `with_structured_output` with scripted objects per role, so a test can script `needs_kb`, `rewrite`, `grade` and `resolve_choice` separately and assert which role was called.
- Search: a fake `KnowledgeSearch` that records its calls and returns fixed chunks.
- Checkpointer: `InMemorySaver`, which supports `interrupt()` and `Command(resume=...)`.
- Chat: the existing recorder, extended with cards and edits.

**Slice 1**
- Small talk (`needs_kb=false`): no rewrite, no search, the agent answers.
- `resolve_chat_user` under SQLite: a linked Chat id returns its user; first contact with a known email (any case) links it and saves the Chat id; an unknown email creates a user with no password, who then cannot log in; an email linked to another Chat id returns `None` and is not relinked; an inactive user returns `None`; no link and no email returns `None` and creates nothing; a second call for the same sender creates no second user.
- Allowed domains: an email outside them (including a subdomain, and with the setting empty) creates and links nothing; matching ignores case; a linked user whose domain is later removed from the setting returns `None`; a comma list with spaces parses.
- Webhook: a mention or command from an accepted sender dispatches `process_chat_event` with their `app_user_id`; from a rejected sender (outside the domains, inactive, no email and not linked) it answers `NO_ACCESS_REPLY` and dispatches nothing; an event with nothing to queue does no lookup and answers `{}`; the email is not in the task payload's top level and not on the queue item.
- `process_item`: the item's `user_id` reaches the context.
- Empty probe: no grade call, the "couldn't find anything" reply.
- `clear`: one probe call carrying every rewritten query, one deep search on the graded doc ids, the chunks are in the agent's system prompt, the reply is posted.
- `ambiguous` (slice 1 only): handled as `clear`.
- Grade output with an unknown doc id: the id is dropped; `clear` left with no ids becomes `no_match`.
- The next turn starts with empty `knowledge`.
- `search_knowledge` passes the user id from context, never one from the model; its schema has only `query`.
- A search error (embedder or DB) ends in the apology, and the retry path is the same as for model errors.
- `_member_collections` under SQLite: a member sees their collections, a non-member does not, an inactive user matches nothing.

**Slice 2**
- `ambiguous` with 2 options: the drain posts a card with 2 buttons plus "None of these", the thread has a pending interrupt, and there is no text reply.
- A click with the matching id: the deep search gets that option's doc ids, the answer is posted, and the thread is no longer paused.
- The same click twice: one queue item.
- A click with a stale id, or on a thread that is not paused: no model call, no reply.
- A click on another user's card (the clicker's thread is not paused): dropped.
- The webhook: a click from the asker returns the update response and enqueues; from anyone else returns `{}` and enqueues nothing.
- "None of these": the pause ends and the invitation is posted.
- A retryable error during the resumed turn, then success: one answer, history holds one "Chose: …" message.

**Slice 3**
- "2": option 2, no classify call.
- An exact label typed with different case: that option, no classify call.
- A classify `refinement`: the deep-search query contains the user's text.
- A classify `unrelated`: the card is edited to "skipped", the message is answered as new, and it appears once in history.
- Expired, typed: handled as new without a classify call; the card is edited to "expired".
- Expired, click: the "expired" reply.
- A classify error: apology, and the pause is gone.
- In every case above, the thread has no pending interrupt afterwards.
- A failed card edit: logged, and the reply is still posted.

## Verification

- `uv run ruff check . && uv run ruff format --check . && uv run pytest`
- Manual, with `make dev` + `make worker` behind the tunnel, Postgres with pgvector, and `LLM_CLASSIFY_MODEL=typesafe/jev-router`:
  1. Ingest two unrelated pages into a collection whose member has your Chat account's email. Ask about one of them. The reply cites it, no card appears, and `users.google_chat_user_id` is now set for that user.
  2. In psql, `EXPLAIN` the probe statement from the worker's debug log. Each `UNION ALL` branch uses `ix_chunks_embedding_hnsw`.
  3. Ask "hi". The worker log shows `needs_kb=false` and no search.
  4. A Chat account whose email is not a user: its first mention creates a user with no password and gets "I couldn't find anything about that in your knowledge base." `POST /auth/login` with that email fails. Deactivate the user and ask again: "Sorry, your account can't use this bot.", and nothing is queued.
  5. Set `GOOGLE_CHAT_ALLOWED_EMAIL_DOMAINS` to a domain your account is not in and restart the API. Ask again: the same no-access reply, and no new row in `users`.
  6. Ingest two pages on related topics and ask a broad question. A card with 2–3 buttons appears. Click one: the buttons change to "Looking into: …", and the answer comes from that page.
  7. A second account clicks a button on the first account's card. Nothing happens.
  8. Ask an ambiguous question and type "2". Then repeat and type something unrelated: it is answered as new, and the old card reads "This question was skipped."
  9. Ask an ambiguous question, wait 30 minutes and click. The bot replies that the question has expired.
  10. Capture a real `buttonClickedPayload` event (from the worker log at debug level), scrub it, and compare it with the test fixture.
