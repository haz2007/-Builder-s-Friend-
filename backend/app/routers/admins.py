from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin, require_owner
from ..database import get_db
from ..models import User
from ..schemas import AdminCreate, AdminResponse
from ..services.admin_service import (
    AdminServiceError,
    add_admin,
    has_telegram,
    list_admins,
    remove_admin,
)


router = APIRouter(prefix="/api/v1/admins", tags=["Admins"])


def to_response(db: Session, user: User) -> AdminResponse:
    return AdminResponse(
        id=user.id,
        email=user.email,
        phone=user.phone,
        role=user.role,
        is_owner=user.is_owner,
        has_telegram=has_telegram(db, user),
    )


@router.get("/", response_model=list[AdminResponse])
def get_admins(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Список видят все админы, менять его может только владелец."""
    return [to_response(db, user) for user in list_admins(db)]


@router.post("/", response_model=AdminResponse)
def create_admin(
    data: AdminCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    try:
        user = add_admin(db, data.login)
    except AdminServiceError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return to_response(db, user)


@router.delete("/{user_id}", response_model=AdminResponse)
def delete_admin(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    try:
        user = remove_admin(db, user_id, current_user)
    except AdminServiceError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return to_response(db, user)
