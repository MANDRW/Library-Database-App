from fastapi import FastAPI
from database import get_db_connection

app = FastAPI(title="Library")


@app.get("/health")
def health_check():
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                db_version = cur.fetchone()[0]

        return {"status": "ok", "db_version": db_version}
    except Exception as e:
        return {"status": "error: ", "detail": str(e)}