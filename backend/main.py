from fastapi import FastAPI
from database import get_db_connection, init_db
import threading
from tools.book_scraper import scrape_books
from routers import router_health as health
from routers import router_loans as loans
from routers import router_search as search
from routers import router_books as books

app = FastAPI(title="Library")
app.include_router(health.router)
app.include_router(loans.router)
app.include_router(search.router)
app.include_router(books.router)

@app.on_event("startup")
def startup_event():
    init_db()



