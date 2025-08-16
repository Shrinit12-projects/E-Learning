# repos/users.py
from pymongo.database import Database
from passlib.context import CryptContext
from typing import Optional

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_user(db: Database, email: str, password: str, full_name: str, role: str) -> dict:
    if db.users.find_one({"email": email}):
        raise ValueError("Email already registered")
    hashed = hash_password(password)
    user = {"email": email, "hashed_password": hashed, "full_name": full_name, "role": role}
    result = db.users.insert_one(user)
    user["_id"] = str(result.inserted_id)
    return user

def get_user_by_email(db: Database, email: str) -> Optional[dict]:
    return db.users.find_one({"email": email})

def ensure_indexes(db: Database):
    db.users.create_index("email", unique=True)
