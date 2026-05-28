import os
from typing import Any

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from database import get_db_connection

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"), override=False)

MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
VECTOR_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "books")
INDEX_BATCH_SIZE = int(os.getenv("INDEX_BATCH_SIZE", "64"))

model = SentenceTransformer(MODEL_NAME)
client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def build_book_text(title: str, summary: str | None) -> str:
    return f"Tytuł: {title}\nOpis: {summary or ''}"


def embed_text(text: str) -> list[float]:
    return model.encode(text).tolist()


def ensure_collection() -> None:
    existing = [collection.name for collection in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_DIM,
                distance=models.Distance.COSINE,
            ),
        )


def fetch_books_from_db() -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, summary, isbn, published_year
                FROM books
                ORDER BY id
                """
            )
            rows = cur.fetchall()

    books = []
    for row in rows:
        books.append(
            {
                "id": row[0],
                "title": row[1],
                "summary": row[2],
                "isbn": row[3],
                "published_year": row[4],
            }
        )
    return books


def get_existing_book_ids() -> set[int]:
    ensure_collection()
    ids: set[int] = set()
    offset = None

    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=256,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        if not points:
            break
        for point in points:
            ids.add(int(point.id))
        if offset is None:
            break

    return ids

def build_point(book: dict[str, Any]) -> models.PointStruct:
    text = build_book_text(book["title"], book["summary"])
    vector = embed_text(text)
    payload = {
        "title": book["title"],
        "summary": book["summary"] or "",
        "isbn": book["isbn"],
        "published_year": book["published_year"],
    }
    return models.PointStruct(id=book["id"], vector=vector, payload=payload)

def upsert_points(points: list[models.PointStruct]) -> None:
    if not points:
        return
    ensure_collection()
    client.upsert(collection_name=COLLECTION_NAME, points=points)


def sync_books_index(only_missing: bool = False, batch_size: int | None = None) -> dict[str, int]:
    ensure_collection()
    books = fetch_books_from_db()
    existing_ids = get_existing_book_ids() if only_missing else set()
    batch_limit = batch_size or INDEX_BATCH_SIZE

    indexed = 0
    skipped = 0
    buffer: list[models.PointStruct] = []

    for book in books:
        if only_missing and book["id"] in existing_ids:
            skipped += 1
            continue

        buffer.append(build_point(book))
        if len(buffer) >= batch_limit:
            upsert_points(buffer)
            indexed += len(buffer)
            buffer.clear()

    if buffer:
        upsert_points(buffer)
        indexed += len(buffer)

    return {
        "total": len(books),
        "indexed": indexed,
        "skipped": skipped,
    }


def search_books(query: str, limit: int = 10) -> list[dict[str, Any]]:
    ensure_collection()
    vector = embed_text(query)

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        limit=limit,
        with_payload=True,
    )

    results = response.points

    output = []
    for result in results:
        payload = result.payload or {}
        output.append(
            {
                "id": result.id,
                "score": result.score,
                "title": payload.get("title"),
                "summary": payload.get("summary"),
                "isbn": payload.get("isbn"),
                "published_year": payload.get("published_year"),
            }
        )
    return output