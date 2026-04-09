from pydantic import BaseModel

class AuthorBase(BaseModel):
    first_name: str
    last_name: str

class AuthorCreate(AuthorBase):
    pass

class Author(AuthorBase):
    id: int

    class Config:
        from_attributes = True