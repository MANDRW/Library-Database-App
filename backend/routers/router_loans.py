from fastapi import APIRouter, HTTPException
from datetime import date
from schemas.schema_loans import Loan, LoanCreate
from database import get_db_connection
router = APIRouter(prefix="/loans", tags=["loans"])

@router.post("/", response_model=Loan)
async def create_loan(loan: LoanCreate):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM book_copies WHERE book_id = %s AND status = 'active' ORDER BY id LIMIT 1",
                    (loan.copy_id,)
                )
                copy = cur.fetchone()
                if not copy:
                    raise HTTPException(status_code=404, detail="Book copy not found")

                cur.execute("SELECT id FROM users WHERE id = %s", (loan.user_id,))
                if not cur.fetchone():
                    raise HTTPException(status_code=404, detail="User not found")

                cur.execute(
                    """INSERT INTO loans (copy_id, user_id, due_date)
                       VALUES (%s, %s, %s)
                           RETURNING id, copy_id, user_id, loan_date, due_date, return_date""",
                    (loan.copy_id, loan.user_id, loan.due_date)
                )
                result = cur.fetchone()

                cur.execute(
                    "UPDATE book_copies SET status = 'loaned' WHERE id = %s",
                    (loan.copy_id,)
                )
                conn.commit()

                return {
                    "id": result[0],
                    "copy_id": result[1],
                    "user_id": result[2],
                    "loan_date": result[3],
                    "due_date": result[4],
                    "return_date": result[5]
                }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{loan_id}/return")
async def return_loan(loan_id: int):
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT copy_id, user_id, due_date FROM loans WHERE id = %s",
                    (loan_id,)
                )
                result = cur.fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="Loan not found")

                copy_id, user_id, due_date = result
                today = date.today()

                if today > due_date:
                    days_overdue = (today - due_date).days
                    fine = days_overdue
                else:
                    fine = 0

                cur.execute(
                    """UPDATE loans SET return_date = CURRENT_DATE
                       WHERE id = %s""",
                    (loan_id,)
                )

                cur.execute(
                    """UPDATE users SET fine = fine + %s WHERE id = %s""",
                    (fine, user_id)
                )

                cur.execute(
                    "SELECT fine FROM users WHERE id = %s",
                    (user_id,)
                )
                total_fine = cur.fetchone()[0]

                if total_fine > 20:
                    cur.execute(
                        "UPDATE users SET is_active = FALSE WHERE id = %s",
                        (user_id,)
                    )

                cur.execute(
                    "UPDATE book_copies SET status = 'active' WHERE id = %s",
                    (copy_id,)
                )
                conn.commit()

                return {
                    "message": "Book returned successfully",
                    "fine_added": fine,
                    "total_fine": total_fine,
                    "user_blocked": total_fine > 20
                }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))