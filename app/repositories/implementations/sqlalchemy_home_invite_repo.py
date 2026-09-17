"""SQLAlchemy home invite repository (PostgreSQL)."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import HomeInvite
from app.repositories.home_invite_repository import IHomeInviteRepository
from app.repositories.implementations.sqlalchemy_models import HomeInviteModel


class SQLAlchemyHomeInviteRepository(IHomeInviteRepository):
    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _to_domain(m: HomeInviteModel) -> HomeInvite:
        return HomeInvite(
            code=m.code, home_id=m.home_id, role=m.role,
            created_by=m.created_by, created_at=m.created_at,
            expires_at=m.expires_at, max_uses=m.max_uses,
            use_count=m.use_count, revoked_at=m.revoked_at,
        )

    def add(self, invite: HomeInvite) -> HomeInvite:
        if self._session.get(HomeInviteModel, invite.code) is not None:
            raise ValueError(f"Invite code '{invite.code}' already exists")
        model = HomeInviteModel(
            code=invite.code, home_id=invite.home_id, role=invite.role,
            created_by=invite.created_by, created_at=invite.created_at,
            expires_at=invite.expires_at, max_uses=invite.max_uses,
            use_count=invite.use_count, revoked_at=invite.revoked_at,
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def get_by_code(self, code: str) -> Optional[HomeInvite]:
        model = self._session.get(HomeInviteModel, code)
        return self._to_domain(model) if model else None

    def list_by_home(self, home_id: str) -> List[HomeInvite]:
        stmt = select(HomeInviteModel).where(
            HomeInviteModel.home_id == home_id
        ).order_by(HomeInviteModel.created_at.desc())
        return [self._to_domain(m) for m in self._session.execute(stmt).scalars().all()]

    def update(self, invite: HomeInvite) -> HomeInvite:
        model = self._session.get(HomeInviteModel, invite.code)
        if model is None:
            raise ValueError(f"Invite code '{invite.code}' not found")
        model.role = invite.role
        model.expires_at = invite.expires_at
        model.max_uses = invite.max_uses
        model.use_count = invite.use_count
        model.revoked_at = invite.revoked_at
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)
