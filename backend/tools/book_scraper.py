import requests
import time
import logging
import hashlib
from deep_translator import GoogleTranslator
from database import get_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def generate_deterministic_isbn(title, author):
    combined = f"{title}:{author}".encode('utf-8')
    hash_hex = hashlib.md5(combined).hexdigest()[:13]
    return f"{hash_hex}"


def scrape_books(target_count=20000):
    logging.info("Starting book scraping from Open Library...")
    try:
        conn = get_db_connection()
        logging.info("Connected to the database.")
    except Exception as e:
        logging.error(f"Database connection error: {e}")
        return

    queries = [
        #"fiction", "computers", "science", "history", "biography",
        #"business", "art", "cooking", "psychology", "philosophy",
        #"crime", "fantasy", "romance", "horror", "travel",
        #"drama", "poetry", "self-help", "health", "thriller",
        #"mystery", "young adult", "adventure", "classic", "children",
        #"education",

        #"technology",
        #"math", "astronomy", "nature",
        #"medicine", "law", "politics", "economics", "sports",
        #"music", "literature", "comics", "graphic novel", "war",
        #"religion", "spirituality", "engineering", "programming",

        #"architecture", "design", "photography", "animation", "film",
        #"dance", "theater", "humor", "satire", "paranormal",
        #"superhero", "spy", "detective", "historical fiction", "dystopian",
        #"utopian", "cyberpunk", "steampunk", "apocalyptic", "post-apocalyptic",
        #"science fiction", "alternate history", "magic",
        #"mythology", "legend", "folklore", "western", "noir", "essay", "journalism", "sociology",
        #"anthropology", "linguistics", "ethics"


        "fiction", "literary fiction", "contemporary fiction", "historical fiction",
        "classics", "short stories", "young adult", "middle grade", "children",
        "picture books", "romance", "romantic suspense", "new adult",
        "fantasy", "epic fantasy", "urban fantasy", "high fantasy",
        "magical realism", "mythology", "fairy tales", "folklore", "legends",
        "science fiction", "space opera", "cyberpunk", "steampunk", "time travel",
        "dystopian", "utopian", "post-apocalyptic", "alternate history", "speculative",
        "mystery", "cozy mystery", "detective", "noir", "thriller", "psychological thriller",
        "crime", "true crime", "spy", "espionage", "legal thriller", "political thriller",
        "horror", "gothic", "paranormal", "supernatural", "occult",
        "adventure", "survival", "western", "war", "naval", "pirate",
        "biography", "memoir", "autobiography", "history", "military history",
        "political history", "social history", "philosophy", "ethics", "religion",
        "spirituality", "theology", "self-help", "personal development", "productivity",
        "psychology", "psychiatry", "psychotherapy", "sociology", "anthropology",
        "cultural studies", "linguistics", "language learning", "reference",
        "dictionaries", "encyclopedias", "textbooks", "academic", "essays", "journalism",
        "business", "entrepreneurship", "leadership", "management", "marketing",
        "finance", "investing", "economics", "startups", "case studies",
        "technology", "programming", "software engineering", "data science", "machine learning",
        "artificial intelligence", "devops", "cybersecurity", "cryptography", "databases",
        "web development", "mobile development", "cloud computing", "engineering",
        "electronics", "robotics", "architecture", "urban planning", "design",
        "graphic design", "photography", "film", "cinema studies", "theater",
        "music", "music theory", "music history", "dance", "performance",
        "comics", "graphic novels", "manga", "animation", "illustration",
        "food & cooking", "baking", "wine & beverages", "nutrition", "gardening",
        "nature", "wildlife", "natural history", "environment", "climate change",
        "sustainability", "travel", "travel writing", "guidebooks", "geography",
        "sports", "fitness", "yoga", "running", "cycling", "football",
        "hobbies", "crafts", "knitting", "woodworking", "DIY", "home improvement",
        "parenting", "education", "pedagogy", "children's education", "medical",
        "medicine", "nursing", "public health", "nutrition science", "law",
        "criminology", "policing", "legal studies", "mathematics", "statistics",
        "logic", "astronomy", "physics", "chemistry", "biology", "neuroscience",
        "transportation", "automotive", "aviation", "space", "astronautics",
        "games", "video games", "game design", "tabletop RPGs", "board games",
        "music writing", "food writing", "memoir of artists", "personal essays"
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
                response = requests.get(url, timeout=20).json()
                docs = response.get("docs", [])
                if not docs:
                    logging.info("No results for this query.")
                    break

                for item in docs:
                    if fetched >= to_fetch or count >= target_count:
                        break

                    title = item.get("title", "Unknown")
                    authors = item.get("author_name", ["Unknown Author"])
                    year = item.get("first_publish_year", 2000)
                    isbn_list = item.get("isbn", [])

                    if isbn_list:
                        isbn = isbn_list[0]
                    else:
                        first_author = authors[0] if authors else "Unknown"
                        isbn = generate_deterministic_isbn(title, first_author)

                    try:
                        with conn.cursor() as cur:
                            summary_pl = "Brak opisu."
                            summary_en = "Brak opisu."
                            work_key = item.get("key")
                            if work_key:
                                details_url = f"https://openlibrary.org{work_key}.json"
                                try:
                                    details = requests.get(details_url, timeout=20).json()
                                    summary_en = details.get("description", "Brak opisu.")
                                    if isinstance(summary_en, dict):
                                        summary_en = summary_en.get("value", "Brak opisu.")

                                    if summary_en and summary_en != "Brak opisu.":
                                        try:
                                            summary_pl = GoogleTranslator(source="auto", target="pl").translate(
                                                summary_en)
                                        except Exception as e:
                                            logging.warning(f"Translation error for {title}: {e}")
                                            summary_pl = "Brak opisu."
                                except Exception as e:
                                    logging.warning(f"Could not fetch details from {details_url}: {e}")
                                    summary_pl = "Brak opisu."

                            if summary_pl == "Brak opisu.":
                                continue


                            logging.info(f"Trying to add book: {title} ({isbn})")

                            cur.execute("""
                                        INSERT INTO books (title, published_year, isbn, summary)
                                        VALUES (%s, %s, %s, %s) ON CONFLICT (isbn) DO NOTHING
                                RETURNING id
                                        """, (title, int(year), isbn, summary_pl))

                            res = cur.fetchone()
                            if not res:
                                logging.info(f"Book already exists in database: {title} ({isbn})")
                                conn.commit()
                                continue

                            book_id = res[0]
                            logging.info(f"Added book: {title} (id={book_id})")

                            for author in authors:
                                parts = author.split(' ', 1)
                                fname = parts[0]
                                lname = parts[1] if len(parts) > 1 else "-"

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
                                    """
                                    INSERT INTO book_authors (book_id, author_id)
                                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                                    """,
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
                                """
                                INSERT INTO book_categories (book_id, category_id)
                                VALUES (%s, %s) ON CONFLICT DO NOTHING
                                """,
                                (book_id, cat_id)
                            )

                            barcode = f"SN-{isbn}"
                            cur.execute(
                                """
                                INSERT INTO book_copies (book_id, barcode)
                                VALUES (%s, %s) ON CONFLICT (barcode) DO NOTHING
                                """,
                                (book_id, barcode)
                            )

                            conn.commit()
                            fetched += 1
                            count += 1
                            logging.info(f"[{count}/{target_count}] Added: {title}")
                            time.sleep(0.5)

                    except Exception as e:
                        conn.rollback()
                        logging.error(f"Error saving '{title}': {e}")

            except Exception as e:
                logging.error(f"API connection error: {e}")
                time.sleep(5)

    conn.close()
    logging.info("Book scraping finished.")