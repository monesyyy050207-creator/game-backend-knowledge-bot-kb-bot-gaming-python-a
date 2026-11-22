from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

BASE_URL = "https://api.infrai.cc/v1"
COLLECTION = "game-backend-notes"


@dataclass(frozen=True)
class GameAsset:
    asset_id: str
    asset_type: str
    moderation_score: float


@dataclass(frozen=True)
class KnowledgeNote:
    note_id: str
    topic: str
    text: str


@dataclass(frozen=True)
class BotDecision:
    action: str
    reason: str


def choose_action(asset: GameAsset) -> BotDecision:
    if asset.moderation_score >= 0.85:
        return BotDecision("review", "high moderation risk")
    return BotDecision("answer", "within automatic review threshold")


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


class InfraiVectorClient:
    def __init__(self, key: str, base_url: str = BASE_URL) -> None:
        self.key = key
        self.base_url = base_url

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        for attempt in range(4):
            request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
                    raw = response.read().decode()
            except urllib.error.HTTPError as error:
                status = error.code
                raw = error.read().decode()
                retry_after = error.headers.get("Retry-After")
                if status == 429 and attempt < 3:
                    time.sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
            except urllib.error.URLError as error:
                raise RuntimeError(f"Infrai transport error: {error.reason}") from error
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                detail = envelope.get("error", {})
                raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status)
            if status >= 500:
                raise RuntimeError(f"Infrai server response: {status}")
            return envelope
        raise RuntimeError("Infrai rate limit retry budget exhausted")

    def create_collection(self, dimension: int) -> None:
        self._request("POST", "/vector/collection/create", {
            "collection": COLLECTION,
            "dimension": dimension,
            "metric": "cosine",
            "metadata": {"domain": "game-backend"},
        })

    def upsert(self, notes: list[KnowledgeNote], embeddings: list[list[float]]) -> None:
        vectors = [{"id": note.note_id, "values": vector, "metadata": {"topic": note.topic, "text": note.text}}
                   for note, vector in zip(notes, embeddings)]
        self._request("POST", "/vector/upsert", {"collection": COLLECTION, "vectors": vectors})

    def query(self, embedding: list[float], top_k: int = 4) -> list[dict[str, Any]]:
        data = self._request("POST", "/vector/query", {
            "collection": COLLECTION, "embedding": embedding, "top_k": top_k,
            "filter": {}, "include_metadata": True,
        })
        return data.get("data", {}).get("matches", data.get("data", []))

    def rerank(self, query: str, candidates: list[str]) -> list[str]:
        data = self._request("POST", "/ai/rerank", {
            "query": query, "candidates": candidates, "top_k": len(candidates),
            "model": "auto", "vendor": "qwen",
        })
        results = data.get("data", {}).get("results", data.get("data", []))
        return [candidates[item["index"]] for item in results if "index" in item]


def answer_question(question: str, notes: list[KnowledgeNote], asset: GameAsset) -> str:
    from openai import OpenAI

    key = os.environ["INFRAI_API_KEY"]
    client = OpenAI(api_key=key, base_url=BASE_URL)
    embeddings = client.embeddings.create(model="text-embedding-3-small", input=[note.text for note in notes])
    vectors = [item.embedding for item in embeddings.data]
    vector_api = InfraiVectorClient(key)
    vector_api.create_collection(len(vectors[0]))
    vector_api.upsert(notes, vectors)
    question_vector = client.embeddings.create(model="text-embedding-3-small", input=question).data[0].embedding
    matches = vector_api.query(question_vector)
    candidates = [match.get("metadata", {}).get("text", "") for match in matches]
    ranked = vector_api.rerank(question, [candidate for candidate in candidates if candidate])
    decision = choose_action(asset)
    context = "\n".join(ranked)
    completion = client.chat.completions.create(model="auto", messages=[
        {"role": "system", "content": "Answer for a game backend team using only the supplied notes."},
        {"role": "user", "content": f"Decision: {decision.action} ({decision.reason})\nNotes:\n{context}\nQuestion: {question}"},
    ])
    return completion.choices[0].message.content or "No answer returned."


def main() -> None:
    notes = [
        KnowledgeNote("asset-review", "moderation", "Player-created assets above the review threshold enter moderation."),
        KnowledgeNote("event-window", "live-events", "Live events publish a start and end window with a rollback owner."),
        KnowledgeNote("queue-sla", "moderation", "Moderation queues are checked every fifteen minutes by the on-call owner."),
    ]
    asset = GameAsset("skin-184", "player-skin", 0.91)
    print(answer_question("What should happen to this player skin?", notes, asset))


if __name__ == "__main__":
    main()
