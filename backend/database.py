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