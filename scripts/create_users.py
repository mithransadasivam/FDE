"""Creates the two fictional demo users (does nothing if they exist).  Run: python -m scripts.create_users"""
from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal, init_db
from app.models import User

DEMO_PASSWORD = "demo-password-1"  # fictional demo accounts only
DEMO_USERS = [
    ("hm@example.com", "Hana Marsh (hiring manager)", "hiring_manager"),
    ("recruiter@example.com", "Ravi Clarke (recruiter)", "recruiter"),
]


def create_users(db=None) -> list[User]:
    init_db()
    own = db is None
    db = db or SessionLocal()
    try:
        users = []
        for email, name, role in DEMO_USERS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(email=email, name=name, role=role, password_hash=hash_password(DEMO_PASSWORD))
                db.add(user)
            users.append(user)
        db.commit()
        return users
    finally:
        if own:
            db.close()


if __name__ == "__main__":
    for u in create_users():
        print(f"{u.email:24} {u.role:15} password: {DEMO_PASSWORD}")
