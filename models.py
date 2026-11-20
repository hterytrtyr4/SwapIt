"""SQLAlchemy models for SwapIt."""
from __future__ import annotations

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite disables FK enforcement by default — turn it on per connection
    so ondelete rules and referential integrity actually hold."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------
ITEM_AVAILABLE = "available"
ITEM_RESERVED = "reserved"
ITEM_SWAPPED = "swapped"
ITEM_STATUSES = (ITEM_AVAILABLE, ITEM_RESERVED, ITEM_SWAPPED)
ITEM_STATUS_LABELS = {
    ITEM_AVAILABLE: "Available",
    ITEM_RESERVED: "Reserved",
    ITEM_SWAPPED: "Swapped",
}

SWAP_PENDING = "pending"
SWAP_ACCEPTED = "accepted"
SWAP_REJECTED = "rejected"
SWAP_COMPLETED = "completed"
SWAP_CANCELLED = "cancelled"
SWAP_STATUSES = (SWAP_PENDING, SWAP_ACCEPTED, SWAP_REJECTED, SWAP_COMPLETED, SWAP_CANCELLED)
SWAP_STATUS_LABELS = {
    SWAP_PENDING: "Pending",
    SWAP_ACCEPTED: "Accepted",
    SWAP_REJECTED: "Rejected",
    SWAP_COMPLETED: "Completed",
    SWAP_CANCELLED: "Cancelled",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False)
    email: Mapped[str] = mapped_column(db.String(120), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(db.String(256), nullable=False)
    college_name: Mapped[str | None] = mapped_column(db.String(120), default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    items: Mapped[list[Item]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    sent_requests: Mapped[list[SwapRequest]] = relationship(
        foreign_keys="SwapRequest.requester_id",
        back_populates="requester",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    received_requests: Mapped[list[SwapRequest]] = relationship(
        foreign_keys="SwapRequest.receiver_id",
        back_populates="receiver",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.strip().split() if p]
        return "".join(p[0].upper() for p in parts[:2]) or "?"


class Item(db.Model):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(db.String(120), nullable=False)
    description: Mapped[str] = mapped_column(db.Text, nullable=False)
    category: Mapped[str] = mapped_column(db.String(40), nullable=False, index=True)
    image: Mapped[str] = mapped_column(db.String(120), nullable=False)
    image_data: Mapped[bytes | None] = mapped_column(db.LargeBinary, nullable=True)
    image_mimetype: Mapped[str | None] = mapped_column(db.String(40), nullable=True)
    condition: Mapped[str] = mapped_column(db.String(20), nullable=False)
    wanted_item: Mapped[str] = mapped_column(db.String(160), nullable=False)
    notes: Mapped[str | None] = mapped_column(db.String(500), default="")
    status: Mapped[str] = mapped_column(
        db.String(20), nullable=False, default=ITEM_AVAILABLE, index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="items")

    @property
    def image_url(self) -> str:
        from flask import current_app, url_for

        if current_app.config.get("MEDIA_BACKEND") == "db":
            if self.image_data:
                return url_for("marketplace.item_image", item_id=self.id)
        elif self.image:
            return url_for("static", filename=f"uploads/{self.image}")
        # Graceful placeholder when a listing has no image at all.
        return (
            "data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' "
            "width='640' height='480'%3E%3Crect width='640' height='480' fill='%23ede9fe'/%3E"
            "%3Ctext x='320' y='250' font-family='sans-serif' font-size='28' fill='%236d28d9' "
            "text-anchor='middle'%3ENo image%3C/text%3E%3C/svg%3E"
        )

    @property
    def status_label(self) -> str:
        return ITEM_STATUS_LABELS.get(self.status, self.status.title())


class SwapRequest(db.Model):
    __tablename__ = "swap_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"), nullable=False, index=True
    )
    receiver_id: Mapped[int] = mapped_column(
        db.ForeignKey("users.id"), nullable=False, index=True
    )
    offered_item_id: Mapped[int] = mapped_column(
        db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_item_id: Mapped[int] = mapped_column(
        db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message: Mapped[str | None] = mapped_column(db.String(500), default="")
    status: Mapped[str] = mapped_column(
        db.String(20), nullable=False, default=SWAP_PENDING, index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    requester: Mapped[User] = relationship(
        foreign_keys=[requester_id], back_populates="sent_requests"
    )
    receiver: Mapped[User] = relationship(
        foreign_keys=[receiver_id], back_populates="received_requests"
    )
    offered_item: Mapped[Item] = relationship(foreign_keys=[offered_item_id])
    requested_item: Mapped[Item] = relationship(foreign_keys=[requested_item_id])

    @property
    def status_label(self) -> str:
        return SWAP_STATUS_LABELS.get(self.status, self.status.title())

    @property
    def is_pending(self) -> bool:
        return self.status == SWAP_PENDING

    @property
    def is_active(self) -> bool:
        """Statuses that lock both items from further requests."""
        return self.status in (SWAP_PENDING, SWAP_ACCEPTED)
