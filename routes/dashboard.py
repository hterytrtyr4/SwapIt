"""User dashboard, smart matches page, and profile management."""
from __future__ import annotations

import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from config import Config
from matching import find_matches_for_user
from models import (
    ITEM_AVAILABLE,
    ITEM_STATUSES,
    ITEM_STATUS_LABELS,
    SWAP_ACCEPTED,
    SWAP_CANCELLED,
    SWAP_COMPLETED,
    SWAP_PENDING,
    SWAP_REJECTED,
    Item,
    SwapRequest,
    User,
    db,
)

dashboard_bp = Blueprint("dashboard", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    my_items = (
        Item.query.filter_by(user_id=current_user.id).order_by(Item.created_at.desc()).all()
    )

    # Status filter for "My Items" (availability filtering lives here so the
    # public marketplace stays strictly limited to available listings).
    status_filter = request.args.get("status", "all")
    filtered_items = my_items
    if status_filter in ITEM_STATUSES:
        filtered_items = [i for i in my_items if i.status == status_filter]

    incoming = (
        SwapRequest.query.filter_by(receiver_id=current_user.id)
        .order_by(SwapRequest.created_at.desc())
        .all()
    )
    sent = (
        SwapRequest.query.filter_by(requester_id=current_user.id)
        .order_by(SwapRequest.created_at.desc())
        .all()
    )

    all_items = Item.query.all()
    matches = find_matches_for_user(current_user, all_items, limit=12)

    involved = (
        SwapRequest.query.filter(
            ((SwapRequest.requester_id == current_user.id) | (SwapRequest.receiver_id == current_user.id))
        ).all()
    )
    stats = {
        "total_listings": len(my_items),
        "active_listings": sum(1 for i in my_items if i.status == ITEM_AVAILABLE),
        "pending": sum(1 for s in involved if s.status == SWAP_PENDING),
        "accepted": sum(1 for s in involved if s.status == SWAP_ACCEPTED),
        "completed": sum(1 for s in involved if s.status == SWAP_COMPLETED),
    }

    history = [
        s
        for s in sorted(involved, key=lambda s: s.created_at, reverse=True)
        if s.status in (SWAP_COMPLETED, SWAP_REJECTED, SWAP_CANCELLED)
    ]

    return render_template(
        "dashboard.html",
        my_items=my_items,
        filtered_items=filtered_items,
        status_filter=status_filter,
        status_labels=ITEM_STATUS_LABELS,
        incoming=incoming,
        sent=sent,
        matches=matches,
        stats=stats,
        history=history,
    )


@dashboard_bp.route("/matches")
@login_required
def matches():
    all_items = Item.query.all()
    matches = find_matches_for_user(current_user, all_items, limit=40)
    return render_template("matches.html", matches=matches)


@dashboard_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        college = request.form.get("college_name", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors: list[str] = []
        if not name or len(name) < 2 or len(name) > 100:
            errors.append("Full name must be between 2 and 100 characters.")
        if not email or not EMAIL_RE.match(email):
            errors.append("Please enter a valid email address.")
        if college and len(college) > 120:
            errors.append("College name must be 120 characters or fewer.")

        if email != current_user.email.lower():
            existing = User.query.filter(db.func.lower(User.email) == email).first()
            if existing:
                errors.append("That email address is already in use.")

        change_password = bool(new_password or confirm_password or current_password)
        if change_password:
            if not current_user.check_password(current_password):
                errors.append("Your current password is incorrect.")
            if len(new_password) < 8:
                errors.append("New password must be at least 8 characters long.")
            if new_password != confirm_password:
                errors.append("New passwords do not match.")

        if errors:
            for err in errors:
                flash(err, "danger")
        else:
            current_user.name = name
            current_user.email = email
            current_user.college_name = college
            if change_password:
                current_user.set_password(new_password)
            db.session.commit()
            flash("Profile updated successfully.", "success")
            return redirect(url_for("dashboard.profile"))

    total_items = Item.query.filter_by(user_id=current_user.id).count()
    completed_swaps = SwapRequest.query.filter(
        ((SwapRequest.requester_id == current_user.id) | (SwapRequest.receiver_id == current_user.id))
        & (SwapRequest.status == SWAP_COMPLETED)
    ).count()

    return render_template(
        "profile.html",
        total_items=total_items,
        completed_swaps=completed_swaps,
    )
