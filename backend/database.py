import os
import psycopg
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")

def get_db_connection():
    return psycopg.connect(
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port="5432"
    )

def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
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
                    isbn VARCHAR(20) UNIQUE NOT NULL
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
            conn.commit()