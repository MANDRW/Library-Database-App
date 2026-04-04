from pydantic import BaseModel, field
from typing import List
from authors import Author
from categories import Category
from enums import BookStatus

class BookCopyBase(BaseModel):
    barcode: str
    status: BookStatus = BookStatus.ACTIVE

class BookCopy(BookCopyBase):
    id: int
    book_id: int
    class Config:
        from_attributes = True

class BookBase(BaseModel):
    title: str
    published_year: int
    isbn: str
    summary: str

class BookCreate(BookBase):
    author_ids: List[int]
    category_ids: List[int]

class Book(BookBase):
    id: int
    authors: List[Author] = field(default_factory=list)
    categories: List[Category] = field(default_factory=list)
    copies: List[BookCopy] = field(default_factory=list)

    class Config:
        from_attributes = True