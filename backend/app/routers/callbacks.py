from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from ..auth import require_admin
from ..database import get_db
from ..models import CallbackRequest, User
from ..rate_limit import callback_limiter
from ..schemas import CallbackRequestCreate, CallbackRequestResponse
from ..services import callbacks
from ..services.order_notifications import deliver_pending

router = APIRouter(prefix="/api/v1/callback-requests", tags=["Callback requests"])


@router.post("/", response_model=CallbackRequestResponse, dependencies=[Depends(callback_limiter)])
def create_callback_request(
    data: CallbackRequestCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Заказ по телефону без регистрации: админам сразу приходит сообщение в Telegram."""
    request = callbacks.create(db, data)
    background_tasks.add_task(deliver_pending)
    return request


@router.get("/", response_model=list[CallbackRequestResponse])
def list_callback_requests(
    status: str | None = Query(default=None, pattern="^(NEW|DONE)$"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(CallbackRequest).options(selectinload(CallbackRequest.handled_by))
    if status is not None:
        query = query.filter(CallbackRequest.status == status)
    return query.order_by(CallbackRequest.id.desc()).limit(limit).all()


@router.post("/{request_id}/done", response_model=CallbackRequestResponse)
def mark_callback_done(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    request = callbacks.mark_done(db, request_id, current_user)
    if request is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return request
