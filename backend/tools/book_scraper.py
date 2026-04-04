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

def scrape_books(target_count=10):
    logging.info("Starting book scraping from Open Library...")
    try:
        conn = get_db_connection()
        logging.info("Connected to the database.")
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return

    count = 0
    queries = [
        "fiction", "computers", "science", "history", "biography",
        "business", "art", "cooking", "psychology", "philosophy"
    ]
    for query in queries:
        if count >= target_count:
            break
        logging.info(f"Scraping category: {query}")

        for page in range(1, 10):
            if count >= target_count:
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
                    if count >= target_count:
                        break

                    title = item.get("title")
                    authors = item.get("author_name", ["Unknown Author"])
                    year = item.get("first_publish_year", 2000)
                    isbn_list = item.get("isbn", [])
                    isbn = isbn_list[0] if isbn_list else f"FAKE-{random.randint(1000000000000,9999999999999)}"

                    if not title:
                        logging.warning(f"Skipped book without title: {title}")
                        continue

                    # Fetch and translate summary to Polish
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

                    try:
                        with conn.cursor() as cur:
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
                                        "INSERT INTO authors (first_name, last_name) VALUES (%s, %s) RETURNING id",
                                        (fname, lname)
                                    )
                                    auth_id = cur.fetchone()[0]
                                    cur.execute(
                                        "INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s)",
                                        (book_id, auth_id)
                                    )

                                cur.execute(
                                    "INSERT INTO categories (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                                    (query,)
                                )
                                cat_id = cur.fetchone()[0]
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