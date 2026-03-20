from pydantic import BaseModel
from datetime import date
from typing import Optional

class LoanBase(BaseModel):
    copy_id: int
    user_id: int
    due_date: date

class LoanCreate(LoanBase):
    pass

class Loan(LoanBase):
    id: int
    loan_date: date
    return_date: Optional[date] = None

    class Config:
        from_attributes = True