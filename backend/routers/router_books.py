from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field
import threading
from database import get_db_connection
from tools.book_scraper import scrape_books
from book_indexer import build_point, upsert_points
from tools.book_scraper import generate_deterministic_isbn

router = APIRouter(prefix="/books", tags=["books"])


class ManualBookRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    published_year: int = Field(ge=0, le=2100)
    isbn: str = Field(min_length=1, max_length=20)
    summary: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    category: str | None = None


@router.post("/scrape")
def run_scraper(count: int = 10):
    def scraper_thread():
        scrape_books(count)
    threading.Thread(target=scraper_thread, daemon=True).start()
    return {"status": "started", "target_count": count}


@router.post("/manual")
def add_manual_book(request: ManualBookRequest):
    if(request.isbn == "AUTO"):
        request.isbn = generate_deterministic_isbn(request.title, request.authors)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO books (title, published_year, isbn, summary)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (isbn) DO NOTHING
                RETURNING id
                """,
                (request.title, request.published_year, request.isbn, request.summary),
            )
            row = cur.fetchone()

            if not row:
                return {
                    "status": "exists",
                    "detail": "Book with this ISBN already exists",
                }

            book_id = row[0]

            author_ids: list[int] = []
            for author in request.authors:
                parts = author.strip().split(" ", 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else "-"

                cur.execute(
                    """
                    SELECT id
                    FROM authors
                    WHERE first_name = %s AND last_name = %s
                    """,
                    (first_name, last_name),
                )
                author_row = cur.fetchone()

                if author_row:
                    author_id = author_row[0]
                else:
                    cur.execute(
                        """
                        INSERT INTO authors (first_name, last_name)
                        VALUES (%s, %s)
                        RETURNING id
                        """,
                        (first_name, last_name),
                    )
                    author_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO book_authors (book_id, author_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (book_id, author_id),
                )
                author_ids.append(author_id)

            category_id = None
            if request.category:
                cur.execute(
                    """
                    SELECT id
                    FROM categories
                    WHERE name = %s
                    """,
                    (request.category,),
                )
                category_row = cur.fetchone()

                if category_row:
                    category_id = category_row[0]
                else:
                    cur.execute(
                        """
                        INSERT INTO categories (name)
                        VALUES (%s)
                        RETURNING id
                        """,
                        (request.category,),
                    )
                    category_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO book_categories (book_id, category_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (book_id, category_id),
                )

            cur.execute(
                """
                INSERT INTO book_copies (book_id, barcode)
                VALUES (%s, %s)
                ON CONFLICT (barcode) DO NOTHING
                """,
                (book_id, f"SN-{request.isbn}"),
            )

            conn.commit()

    point = build_point(
        {
            "id": book_id,
            "title": request.title,
            "summary": request.summary,
            "isbn": request.isbn,
            "published_year": request.published_year,
        }
    )
    upsert_points([point])

    return {
        "status": "ok",
        "book_id": book_id,
        "authors_added": len(author_ids),
        "category_added": category_id is not None,
        "indexed_in_qdrant": True,
    }