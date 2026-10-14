from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Notification, User


router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["Notifications"]
)


@router.get("/")
def get_notifications(
    unread_only: bool = False,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
    )

    if unread_only:
        query = query.filter(Notification.is_read == 0)

    return (
        query
        .order_by(Notification.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/unread-count")
def get_unread_notifications_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == 0
        )
        .count()
    )

    return {
        "count": count
    }


@router.patch("/{notification_id}/read")
def mark_notification_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
        .first()
    )

    if notification is None:
        raise HTTPException(
            status_code=404,
            detail="Notification not found"
        )

    notification.is_read = 1

    db.commit()
    db.refresh(notification)

    return notification


@router.patch("/read-all")
def mark_all_notifications_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notifications = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read == 0
        )
        .all()
    )

    for notification in notifications:
        notification.is_read = 1

    db.commit()

    return {
        "message": "All notifications marked as read",
        "count": len(notifications)
    }