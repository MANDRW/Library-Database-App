from fastapi import APIRouter, BackgroundTasks

import threading
from tools.book_scraper import scrape_books

router = APIRouter(prefix="/books", tags=["books"])

@router.post("/scrape")
def run_scraper(count: int = 10):
    def scraper_thread():
        scrape_books(count)
    threading.Thread(target=scraper_thread, daemon=True).start()
    return {"status": "started", "target_count": count}