import requests
import time
import random
import logging
from deep_translator import GoogleTranslator
from database import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def generate_fake_isbn(cur):
    while True:
        fake_isbn = f"FAKE-{random.randint(1000000000000,9999999999999)}"
        cur.execute("SELECT 1 FROM books WHERE isbn = %s", (fake_isbn,))
        if not cur.fetchone():
            return fake_isbn

def scrape_books(target_count=10):
    logging.info("Starting book scraping from Open Library...")
    try:
        conn = get_db_connection()
        logging.info("Connected to the database.")
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return

    queries = [
        "fiction", "computers", "science", "history", "biography",
        "business", "art", "cooking", "psychology", "philosophy"
        ##"crime", "fantasy", "romance", "horror"
    ]
    num_categories = len(queries)
    if target_count < num_categories:
        categories_plan = {q: 1 for q in queries[:target_count]}
    else:
        base = target_count // num_categories
        extra = target_count % num_categories
        categories_plan = {}
        for idx, q in enumerate(queries):
            categories_plan[q] = base + (1 if idx < extra else 0)

    count = 0
    for query in queries:
        to_fetch = categories_plan.get(query, 0)
        if to_fetch == 0:
            continue
        fetched = 0
        logging.info(f"Scraping category: {query} ({to_fetch} books)")
        for page in range(1, 10):
            if fetched >= to_fetch or count >= target_count:
                break
            url = f"https://openlibrary.org/search.json?q={query}&page={page}"
            logging.info(f"Fetching: {url}")
            try:
                response = requests.get(url, timeout=10).json()
                docs = response.get("docs", [])
                if not docs:
                    logging.info("No results for this query.")
                    break
                for item in docs:
                    if fetched >= to_fetch or count >= target_count:
                        break

                    title = item.get("title")
                    authors = item.get("author_name", ["Unknown Author"])
                    year = item.get("first_publish_year", 2000)
                    isbn_list = item.get("isbn", [])

                    try:
                        with conn.cursor() as cur:
                            if isbn_list:
                                isbn = isbn_list[0]
                            else:
                                isbn = generate_fake_isbn(cur)

                            cur.execute("SELECT 1 FROM books WHERE isbn = %s", (isbn,))
                            if cur.fetchone():
                                logging.info(f"Book already exists in database: {title} ({isbn})")
                                continue
                            cur.execute("SELECT 1 FROM books WHERE title = %s", (title,))
                            if cur.fetchone():
                                logging.info(f"Book with same title already exists: {title}")
                                continue

                            summary_pl = "Brak opisu."
                            work_key = item.get("key")
                            if work_key:
                                details_url = f"https://openlibrary.org{work_key}.json"
                                try:
                                    details = requests.get(details_url, timeout=10).json()
                                    summary_en = details.get("description", "Brak opisu.")
                                    if isinstance(summary_en, dict):
                                        summary_en = summary_en.get("value", "Brak opisu.")
                                    summary_pl = GoogleTranslator(source="auto", target="pl").translate(summary_en)
                                except Exception:
                                    summary_pl = "Brak opisu."

                            logging.info(f"Trying to add book: {title} ({isbn})")
                            cur.execute("""
                                        INSERT INTO books (title, published_year, isbn, summary)
                                        VALUES (%s, %s, %s, %s) RETURNING id
                                        """, (title, int(year), isbn, summary_pl))

                            res = cur.fetchone()
                            if res:
                                book_id = res[0]
                                logging.info(f"Added book: {title} (id={book_id})")
                                for author in authors:
                                    parts = author.split(' ', 1)
                                    fname, lname = parts[0], (parts[1] if len(parts) > 1 else "-")
                                    cur.execute(
                                        "SELECT id FROM authors WHERE first_name = %s AND last_name = %s",
                                        (fname, lname)
                                    )
                                    author_row = cur.fetchone()
                                    if not author_row:
                                        cur.execute(
                                            "INSERT INTO authors (first_name, last_name) VALUES (%s, %s) RETURNING id",
                                            (fname, lname)
                                        )
                                        auth_id = cur.fetchone()[0]
                                    else:
                                        auth_id = author_row[0]
                                    cur.execute(
                                        "INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s)",
                                        (book_id, auth_id)
                                    )

                                cur.execute("SELECT id FROM categories WHERE name = %s", (query,))
                                cat_row = cur.fetchone()
                                if not cat_row:
                                    cur.execute(
                                        "INSERT INTO categories (name) VALUES (%s) RETURNING id",
                                        (query,)
                                    )
                                    cat_id = cur.fetchone()[0]
                                else:
                                    cat_id = cat_row[0]

                                cur.execute(
                                    "INSERT INTO book_categories (book_id, category_id) VALUES (%s, %s)",
                                    (book_id, cat_id)
                                )

                                barcode = f"SN-{isbn}" if isbn else f"SN-ID{book_id}"
                                cur.execute(
                                    "INSERT INTO book_copies (book_id, barcode) VALUES (%s, %s)",
                                    (book_id, barcode)
                                )

                                conn.commit()
                                fetched += 1
                                count += 1
                                logging.info(f"[{count}/{target_count}] Added: {title}")
                                time.sleep(0.5)
                            else:
                                logging.info(f"Book already exists in database: {title} ({isbn})")
                    except Exception as e:
                        conn.rollback()
                        logging.error(f"Error saving '{title}': {e}")
            except Exception as e:
                logging.error(f"API connection error: {e}")
                time.sleep(5)

    conn.close()
    logging.info("Book scraping finished.")