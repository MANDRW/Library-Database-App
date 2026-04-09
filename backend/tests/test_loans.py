import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from routers.router_loans import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


@pytest.fixture
def mock_db_connection():
    """Mock połączenia z bazą danych"""
    with patch('routers.router_loans.get_db_connection') as mock:
        yield mock


class TestReturnLoan:
    """Testy dla zwracania książek i naliczania kar"""

    def test_return_loan_on_time_no_fine(self, mock_db_connection):
        """Zwrot przed deadline'em – bez kary"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Loan data: wypożyczono dzisiaj, termin za 14 dni
        due_date = date.today() + timedelta(days=14)
        mock_cursor.fetchone.side_effect = [
            (1, 1, due_date),  # copy_id, user_id, due_date
            (0,),              # current fine
        ]

        response = client.post("/loans/1/return")

        assert response.status_code == 200
        assert response.json()["fine_added"] == 0
        assert response.json()["total_fine"] == 0
        assert response.json()["user_blocked"] is False

    def test_return_loan_overdue_with_fine(self, mock_db_connection):
        """Zwrot po deadline'em – naliczenie kary"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Loan data: deadline był 5 dni temu
        due_date = date.today() - timedelta(days=5)
        mock_cursor.fetchone.side_effect = [
            (1, 1, due_date),   # copy_id, user_id, due_date
            (5,),               # current fine (5 dni * 1 = 5)
        ]

        response = client.post("/loans/1/return")

        assert response.status_code == 200
        assert response.json()["fine_added"] == 5
        assert response.json()["total_fine"] == 5
        assert response.json()["user_blocked"] is False

    def test_return_loan_blocks_user_over_20_fine(self, mock_db_connection):
        """Kara > 20 – zablokowanie użytkownika"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Loan data: 25 dni opóźnienia
        due_date = date.today() - timedelta(days=25)
        mock_cursor.fetchone.side_effect = [
            (1, 1, due_date),   # copy_id, user_id, due_date
            (25,),              # current fine (25 dni)
        ]

        response = client.post("/loans/1/return")

        assert response.status_code == 200
        assert response.json()["fine_added"] == 25
        assert response.json()["total_fine"] == 25
        assert response.json()["user_blocked"] is True

        # Sprawdź czy UPDATE users SET is_active = FALSE został wywołany
        mock_cursor.execute.assert_any_call(
            "UPDATE users SET is_active = FALSE WHERE id = %s",
            (1,)
        )

    def test_return_loan_not_found(self, mock_db_connection):
        """Pożyczka nie istnieje"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.return_value = None

        response = client.post("/loans/999/return")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_return_loan_accumulates_fines(self, mock_db_connection):
        """Kara się kumuluje – poprzednia kara + nowa kara"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Loan data: 10 dni opóźnienia, użytkownik ma już 15 kar
        due_date = date.today() - timedelta(days=10)
        mock_cursor.fetchone.side_effect = [
            (1, 1, due_date),   # copy_id, user_id, due_date
            (25,),              # total fine (15 poprzednich + 10 nowych)
        ]

        response = client.post("/loans/1/return")

        assert response.status_code == 200
        assert response.json()["fine_added"] == 10
        assert response.json()["total_fine"] == 25
        assert response.json()["user_blocked"] is True

    def test_return_loan_updates_book_status(self, mock_db_connection):
        """Status książki zmienia się z 'loaned' na 'active'"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        due_date = date.today() + timedelta(days=14)
        mock_cursor.fetchone.side_effect = [
            (1, 1, due_date),
            (0,),
        ]

        response = client.post("/loans/1/return")

        assert response.status_code == 200
        # Sprawdź czy UPDATE na book_copies został wykonany
        mock_cursor.execute.assert_any_call(
            "UPDATE book_copies SET status = 'active' WHERE id = %s",
            (1,)
        )

class TestCreateLoan:
    """Testy dla tworzenia pożyczek"""

    def test_create_loan_success(self, mock_db_connection):
        """Pomyślne utworzenie pożyczki"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        due_date = date.today() + timedelta(days=14)
        loan_date = date.today()

        mock_cursor.fetchone.side_effect = [
            (1,),  # copy exists
            (1,),  # user exists
            (1, 1, 1, loan_date, due_date, None),  # loan created
        ]

        response = client.post(
            "/loans/",
            json={
                "copy_id": 1,
                "user_id": 1,
                "due_date": due_date.isoformat()
            }
        )

        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["user_id"] == 1

    def test_create_loan_book_copy_not_found(self, mock_db_connection):
        """Egzemplarz książki nie istnieje"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.return_value = None

        response = client.post(
            "/loans/",
            json={
                "copy_id": 999,
                "user_id": 1,
                "due_date": date.today().isoformat()
            }
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_loan_user_not_found(self, mock_db_connection):
        """Użytkownik nie istnieje"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            (1,),  # copy exists
            None,  # user doesn't exist
        ]

        response = client.post(
            "/loans/",
            json={
                "copy_id": 1,
                "user_id": 999,
                "due_date": date.today().isoformat()
            }
        )

        assert response.status_code == 404
        assert "user not found" in response.json()["detail"].lower()