from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import get_session_factory
from app.models import User

session = get_session_factory()()
rows = session.scalars(select(User).options(selectinload(User.role))).all()
if not rows:
    print("NO_USERS")
else:
    for user in rows:
        role = user.role.code if user.role is not None else ""
        print(f"{user.id}\t{user.username}\t{role}")
