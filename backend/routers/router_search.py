from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from book_indexer import search_books, sync_books_index

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