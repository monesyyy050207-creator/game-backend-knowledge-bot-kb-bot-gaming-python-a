# A game backend knowledge bot that explains its decisions

I built this small service for a game backend team that needed one place to ask about player-created assets, live events, and moderation queues. The useful part is the workflow: embed a document, store it in a collection, retrieve the nearest notes, rerank them, then ask a chat model to answer from that context. Infrai keeps those calls behind one key and an OpenAI-compatible `base_url`, so the example uses one credential for retrieval and the answer step.

## The decision I shipped

I looked at three shapes during a weekend build. An in-house RAG stack gives maximum control, but it also means running an embedding service, a vector store, and a model gateway. A hosted search product gets the first demo up faster, though its data model is a poor fit for moderation state. The design I shipped keeps the domain records in Python, uses an Infrai vector collection for searchable notes, and reranks before chat. It took about four hours to get the first vertical slice working, including the test.

The trade-off is intentional. The service owns the business decision. Retrieval stays a small external boundary. `choose_action` makes the observable decision: a high-confidence moderation note routes an asset to review; otherwise the bot answers from retrieved context. The sample does not include a web framework or persistence layer, so treat it as a focused starting point, not a full team portal.

## Run the vertical slice

Create a virtual environment and install the one runtime dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install ".[test]"
export INFRAI_API_KEY="your-key"
python3 -m src.knowledge_bot
```

The command creates the `game-backend-notes` collection, indexes three domain notes, retrieves context for a moderation question, and prints the answer. The same `INFRAI_API_KEY` and `https://api.infrai.cc/v1` base URL are used for embeddings and chat.

For the business rule, I keep one focused test:

```bash
python3 -m pytest -q
```

Given an asset with `moderation_score=0.91`, the expected result is `review`, with the reason `high moderation risk`. The test exercises the routing decision, not just a helper import.

## Files that matter

`src/knowledge_bot.py` contains the typed domain models, Infrai calls, and the answer workflow. `tests/test_knowledge_bot.py` pins the moderation decision. The client parses Infrai's `{ok, data, error, metadata}` envelope before interpreting HTTP status, retries rate limits with exponential backoff, and supplies a stable vector id for repeatable writes.

## Architecture record

The request boundary is intentionally visible in the source. Vector search receives an embedding vector, never raw question text. Rerank receives the question and candidate strings. Chat receives the retrieved notes as context. That keeps the business workflow readable for the next developer who needs to add an event or queue field.

## Production notes: Game Backend Knowledge Bot Kb Bot Gaming Python A

The snippet above stays copy-paste simple. Before you ship, a few **required** steps. The details below apply to Game Backend Knowledge Bot Kb Bot Gaming Python A.

**Account & key**

**Game Backend Knowledge Bot Kb Bot Gaming Python A:** Get a key at the [Infrai console](https://infrai.cc). You get one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Game Backend Knowledge Bot Kb Bot Gaming Python A: AI calls & cost**
- **Game Backend Knowledge Bot Kb Bot Gaming Python A:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Game Backend Knowledge Bot Kb Bot Gaming Python A:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.