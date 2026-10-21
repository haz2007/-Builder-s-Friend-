"""Заявки «перезвоните мне»: сохранение, сообщение админам, отметка «перезвонили»."""

import html
from datetime import UTC, datetime

from sqlalchemy.orm import Session, selectinload

from ..models import CallbackRequest, ProductVariant, User
from ..schemas import CallbackRequestCreate
from . import audit
from .order_notifications import admin_links, enqueue, format_money, format_quantity


def cart_summary(db: Session, data: CallbackRequestCreate) -> tuple[str | None, float | None]:
    """Корзина текстом по текущим ценам из базы — ценам из браузера не верим."""
    if not data.items:
        return None, None
    ids = [item.variant_id for item in data.items]
    variants = {
        variant.id: variant
        for variant in db.query(ProductVariant)
        .options(selectinload(ProductVariant.product))
        .filter(ProductVariant.id.in_(ids), ProductVariant.is_active == 1)
    }
    lines, total = [], 0.0
    for item in data.items:
        variant = variants.get(item.variant_id)
        if variant is None or variant.product.is_active != 1:
            continue
        name = variant.product.name
        if variant.name != variant.unit:
            name += f" ({variant.name})"
        cost = variant.price * item.quantity
        total += cost
        lines.append(f"{name} — {format_quantity(item.quantity)} {variant.unit} = {format_money(cost)}")
    if not lines:
        return None, None
    return "\n".join(lines), round(total, 2)


def admin_message(request: CallbackRequest) -> str:
    lines = [
        f"<b>📞 Перезвоните: заявка №{request.id}</b>",
        "",
        f"👤 {html.escape(request.name)}",
        f"📱 {html.escape(request.phone)}",
    ]
    if request.comment:
        lines.append(f"💬 <i>{html.escape(request.comment)}</i>")
    if request.cart_summary:
        lines += ["", "🧾 Хочет заказать:"]
        lines += [f"• {html.escape(line)}" for line in request.cart_summary.split("\n")]
        lines.append(f"💰 Примерно: <b>{format_money(request.cart_total or 0)}</b>")
    return "\n".join(lines)


def done_keyboard(request_id: int) -> dict:
    return {"inline_keyboard": [[{"text": "✅ Перезвонили", "callback_data": f"cb:done:{request_id}"}]]}


def create(db: Session, data: CallbackRequestCreate) -> CallbackRequest:
    summary, total = cart_summary(db, data)
    request = CallbackRequest(
        name=data.name,
        phone=data.phone,
        comment=data.comment or None,
        cart_summary=summary,
        cart_total=total,
    )
    db.add(request)
    db.flush()
    text = admin_message(request)
    enqueue(db, [(link.telegram_chat_id, text, done_keyboard(request.id)) for link in admin_links(db)])
    db.commit()
    db.refresh(request)
    return request


def mark_done(db: Session, request_id: int, actor: User) -> CallbackRequest | None:
    """Отмечает, что перезвонили. Повторная отметка ничего не меняет."""
    request = db.query(CallbackRequest).filter(CallbackRequest.id == request_id).with_for_update().first()
    if request is None:
        return None
    if request.status == "NEW":
        request.status = "DONE"
        request.handled_by_id = actor.id
        request.handled_at = datetime.now(UTC).replace(tzinfo=None)
        audit.record(db, actor, "callback.done", "callback", request.id,
                     f"Перезвонили по заявке №{request.id}: {request.name}, {request.phone}")
        db.commit()
    db.refresh(request)
    return request
