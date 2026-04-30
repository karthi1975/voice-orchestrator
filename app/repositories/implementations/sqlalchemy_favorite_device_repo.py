"""SQLAlchemy implementation of FavoriteDevice repository."""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.domain.models import FavoriteDevice
from app.repositories.favorite_device_repository import IFavoriteDeviceRepository
from app.repositories.implementations.sqlalchemy_models import FavoriteDeviceModel


class SQLAlchemyFavoriteDeviceRepository(IFavoriteDeviceRepository):
    def __init__(self, session: Session):
        self._session = session

    def add(self, favorite: FavoriteDevice) -> FavoriteDevice:
        existing = self.get_by_user_home_entity(
            favorite.user_ref, favorite.home_id, favorite.entity_id
        )
        if existing:
            raise ValueError(
                f"entity {favorite.entity_id} already favorited for user {favorite.user_ref} in home {favorite.home_id}"
            )
        model = self._to_model(favorite)
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def get_by_id(self, favorite_id: str) -> Optional[FavoriteDevice]:
        model = self._session.get(FavoriteDeviceModel, favorite_id)
        return self._to_domain(model) if model else None

    def get_by_user_home_entity(
        self, user_ref: str, home_id: str, entity_id: str
    ) -> Optional[FavoriteDevice]:
        model = self._session.query(FavoriteDeviceModel).filter_by(
            user_ref=user_ref, home_id=home_id, entity_id=entity_id,
        ).first()
        return self._to_domain(model) if model else None

    def list_for_user_home(self, user_ref: str, home_id: str) -> List[FavoriteDevice]:
        models = self._session.query(FavoriteDeviceModel).filter_by(
            user_ref=user_ref, home_id=home_id,
        ).order_by(
            FavoriteDeviceModel.position.asc(),
            FavoriteDeviceModel.created_at.asc(),
        ).all()
        return [self._to_domain(m) for m in models]

    def update_position(self, favorite_id: str, position: int) -> Optional[FavoriteDevice]:
        model = self._session.get(FavoriteDeviceModel, favorite_id)
        if not model:
            return None
        model.position = position
        self._session.commit()
        self._session.refresh(model)
        return self._to_domain(model)

    def delete(self, favorite_id: str) -> bool:
        model = self._session.get(FavoriteDeviceModel, favorite_id)
        if not model:
            return False
        self._session.delete(model)
        self._session.commit()
        return True

    @staticmethod
    def _to_domain(model: FavoriteDeviceModel) -> FavoriteDevice:
        return FavoriteDevice(
            id=model.id,
            user_ref=model.user_ref,
            home_id=model.home_id,
            entity_id=model.entity_id,
            friendly_name=model.friendly_name,
            domain=model.domain,
            kind=model.kind or "entity",
            device_id=model.device_id,
            primary_entity_id=model.primary_entity_id,
            position=model.position,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_model(favorite: FavoriteDevice) -> FavoriteDeviceModel:
        return FavoriteDeviceModel(
            id=favorite.id,
            user_ref=favorite.user_ref,
            home_id=favorite.home_id,
            entity_id=favorite.entity_id,
            friendly_name=favorite.friendly_name,
            domain=favorite.domain,
            kind=favorite.kind,
            device_id=favorite.device_id,
            primary_entity_id=favorite.primary_entity_id,
            position=favorite.position,
            created_at=favorite.created_at,
        )
