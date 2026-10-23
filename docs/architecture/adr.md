# Architecture decision records

## ADR-001: Cap outgoing Google Chat text at 8000 characters

**Status:** accepted (GH-7)

### Context

FocalBot posts LLM replies into Google Chat spaces. Google's documented limit is on the whole message, not on the `text` field: "The maximum message size (including any text or cards) is 32,000 bytes", and a Chat app that goes over must send several messages. No separate character limit for `text` is documented, and the docs do not distinguish human senders from apps.

We cap the text ourselves anyway: `SendMessageRequest` (GH-6) rejects longer text with 422, and the agent's `finalize` step (GH-7) trims replies to fit, so a long answer never fails at the send step and burns retries on an error that cannot succeed.

### Decision

- The cap is **8000 characters**, set in two places that must stay equal: `SendMessageRequest.text` (`app/schemas/google_chat.py`) and `MAX_REPLY_CHARS` (`app/agent/graph.py`).
- 8000 characters is at most 32,000 bytes even if every character takes 4 bytes in UTF-8 (worst case, e.g. emoji), so it stays inside Google's limit for any text.
- Replies over the cap are truncated and end with "… (truncated)". They are not split into several messages.

### Consequences

- Typical English text could go to about 32,000 characters, so the cap is conservative. A single Chat message above 8000 characters is also hard to read, and the system prompt already asks for concise replies.
- Truncation keeps the FIFO queue simple: one turn gives one message, so ordering and retries stay straightforward.
- If long answers become common, splitting a reply into several messages is the next step. It would change the drain, since each part is a separate post that can fail on its own.
- The 4000 we used before was our own number, not Google's. This ADR replaces it.

### Sources

- Google Chat API, [Create messages](https://developers.google.com/workspace/chat/create-messages) and [`spaces.messages.create`](https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create): 32,000 bytes per message.
- [`spaces.messages` reference](https://developers.google.com/workspace/chat/reference/rest/v1/spaces.messages): the `text` field states no size limit.
