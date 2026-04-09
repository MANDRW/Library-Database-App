import os
import psycopg
from dotenv import load_dotenv
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"), override=True)

def get_db_connection():
    return psycopg.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST", "db"),
        port="5432"
    )

def init_db():
    retries = 5
    while retries > 0:
        try:
            logger.info("Attempting to connect to the database...")
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    logger.info("Connected to the database. Creating tables...")
                    cur.execute("""
                        DO $$
                        BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'book_status') THEN
                            EXECUTE 'CREATE TYPE book_status AS ENUM (''active'', ''loaned'')';
                        END IF;
                        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'access_level') THEN
                            EXECUTE 'CREATE TYPE access_level AS ENUM (''admin'', ''worker'', ''member'')';
                        END IF;
                        END
                        $$;
                    """)
                    cur.execute("""
                                CREATE TABLE IF NOT EXISTS books (
                                                                     id SERIAL PRIMARY KEY,
                                                                     title VARCHAR(255) NOT NULL,
                                    published_year INT NOT NULL,
                                    isbn VARCHAR(20) UNIQUE NOT NULL,
                                    summary TEXT
                                    );
                                CREATE TABLE IF NOT EXISTS categories (
                                                                          id SERIAL PRIMARY KEY,
                                                                          name VARCHAR(255) UNIQUE NOT NULL
                                    );

                                CREATE TABLE IF NOT EXISTS book_categories (
                                                                               book_id INT REFERENCES books(id) ON DELETE CASCADE,
                                    category_id INT REFERENCES categories(id) ON DELETE CASCADE,
                                    PRIMARY KEY (book_id, category_id)
                                    );
                                CREATE TABLE IF NOT EXISTS authors (
                                                                       id SERIAL PRIMARY KEY,
                                                                       first_name VARCHAR(255) NOT NULL,
                                    last_name VARCHAR(255) NOT NULL
                                    );
                                CREATE TABLE IF NOT EXISTS book_authors (
                                                                            book_id INT REFERENCES books(id) ON DELETE CASCADE,
                                    author_id INT REFERENCES authors(id) ON DELETE CASCADE,
                                    PRIMARY KEY (book_id, author_id)
                                    );
                                CREATE TABLE IF NOT EXISTS book_copies (
                                                                           id SERIAL PRIMARY KEY,
                                                                           book_id INT REFERENCES books(id) ON DELETE CASCADE,
                                    barcode VARCHAR(50) UNIQUE NOT NULL,
                                    status book_status NOT NULL DEFAULT 'active'
                                    );
                                CREATE TABLE IF NOT EXISTS users (
                                                                     id SERIAL PRIMARY KEY,
                                                                     first_name VARCHAR(255) NOT NULL,
                                    last_name VARCHAR(255) NOT NULL,
                                    email VARCHAR(255) UNIQUE NOT NULL,
                                    password VARCHAR(255) NOT NULL,
                                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                                    fine DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                                    access_level access_level NOT NULL DEFAULT 'member',
                                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    );
                                CREATE TABLE IF NOT EXISTS loans (
                                                                     id SERIAL PRIMARY KEY,
                                                                     copy_id INT REFERENCES book_copies(id) ON DELETE CASCADE,
                                    user_id INT REFERENCES users(id) ON DELETE CASCADE,
                                    loan_date DATE NOT NULL DEFAULT CURRENT_DATE,
                                    due_date DATE NOT NULL,
                                    return_date DATE
                                    );
                                """)
                    logger.info("Tables created successfully. Checking environment variables...")

                    test_user_vars = {
                        "TEST_USER_FIRST_NAME": os.getenv("TEST_USER_FIRST_NAME"),
                        "TEST_USER_LAST_NAME": os.getenv("TEST_USER_LAST_NAME"),
                        "TEST_USER_EMAIL": os.getenv("TEST_USER_EMAIL"),
                        "TEST_USER_PASSWORD": os.getenv("TEST_USER_PASSWORD"),
                    }
                    for var, value in test_user_vars.items():
                        logger.info(f"{var}: {value}")
                    if not all(test_user_vars.values()):
                        raise ValueError("Missing required environment variables for the test user.")
                    logger.info("Adding test user...")
                    cur.execute("""
                                INSERT INTO users (first_name, last_name, email, password, access_level)
                                VALUES (%s, %s, %s, %s, %s)
                                    ON CONFLICT (email) DO NOTHING;
                                """, (
                                    test_user_vars["TEST_USER_FIRST_NAME"],
                                    test_user_vars["TEST_USER_LAST_NAME"],
                                    test_user_vars["TEST_USER_EMAIL"],
                                    test_user_vars["TEST_USER_PASSWORD"],
                                    "member"
                                ))

                    if cur.rowcount > 0:
                        logger.info(f"Test user created successfully. Rows affected: {cur.rowcount}")
                    else:
                        logger.info("Test user already exists (skipped due to conflict).")

                    conn.commit()
                    logger.info("Database initialization completed.")
                    break
        except Exception as e:
            retries -= 1
            logger.error(f"Database initialization failed: {e}")
            logger.info(f"Retrying... ({retries} retries left)")
            time.sleep(2)