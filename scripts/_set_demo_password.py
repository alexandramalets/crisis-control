import os
from datetime import datetime

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import get_session_factory
from app.models import User

username = os.environ.get("DEMO_LOGIN", "analyst")
password = os.environ.get("DEMO_PASSWORD")
if not password:
    raise SystemExit("DEMO_PASSWORD is required")

session = get_session_factory()()
user = session.scalar(select(User).where(User.username == username))
if user is None:
    raise SystemExit(f"user {username} not found")
user.password_hash = hash_password(password)
user.failed_login_count = 0
user.locked_until = None
user.is_active = True
session.commit()
print(f"password updated for {username} at {datetime.now().isoformat(timespec='seconds')}")
