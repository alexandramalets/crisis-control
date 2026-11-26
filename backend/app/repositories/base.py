from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def paginate(session: Session, query: Select, limit: int, offset: int) -> tuple[list, int]:
    total = session.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    items = list(session.scalars(query.limit(limit).offset(offset)).unique())
    return items, total or 0
