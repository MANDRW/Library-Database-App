from enum import Enum

class BookStatus(str, Enum):
    ACTIVE = 'active'
    LOANED = 'loaned'

class AccessLevel(str, Enum):
    ADMIN = 'admin'
    WORKER = 'worker'
    MEMBER = 'member'