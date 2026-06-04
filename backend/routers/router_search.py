from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from book_indexer import search_books, sync_books_index
from database import get_db_connection

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=100)


@router.post("/sync")
def sync_index(only_missing: bool = False, background: bool = False, background_tasks: BackgroundTasks=None):
    if background:
        if background_tasks is not None:
            background_tasks.add_task(sync_books_index, only_missing=only_missing)
            return {"status": "started", "only_missing": only_missing}
        return {"status": "error", "detail": "Background tasks not available"}

    result = sync_books_index(only_missing=only_missing)
    return {
        "status": "ok",
        **result,
    }


@router.post("/books")
def semantic_search(request: SearchRequest):
    results = search_books(request.query, limit=request.limit)
    return {
        "query": request.query,
        "count": len(results),
        "results": results,
    }
@router.post("/text")
def text_search(request: SearchRequest):
    q = f"%{request.query}%"
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, summary, isbn, published_year
                FROM books
                WHERE title ILIKE %s OR summary ILIKE %s
                LIMIT %s
                """,
                (q, q, request.limit),
            )
            rows = cur.fetchall()

    results = [
        {
            "id": r[0],
            "title": r[1],
            "summary": r[2],
            "isbn": r[3],
            "published_year": r[4],
        }
        for r in rows
    ]

    return {
        "query": request.query,
        "count": len(results),
        "results": results,
    }