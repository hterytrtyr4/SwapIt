"""Swap request workflow: create, accept, reject, cancel, complete."""
from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from config import Config
from models import (
    ITEM_AVAILABLE,
    ITEM_RESERVED,
    ITEM_SWAPPED,
    SWAP_ACCEPTED,
    SWAP_CANCELLED,
    SWAP_COMPLETED,
    SWAP_PENDING,
    SWAP_REJECTED,
    Item,
    SwapRequest,
    db,
    utcnow,
)

swaps_bp = Blueprint("swaps", __name__, url_prefix="/swaps")


def _get_swap_or_404(swap_id: int) -> SwapRequest:
    swap = db.session.get(SwapRequest, swap_id)
    if swap is None:
        abort(404)
    return swap


def _cancel_other_pending_requests(swap: SwapRequest) -> None:
    """Lock consistency: once a request is accepted, both items are reserved,
    so any other pending request touching either item must be cancelled."""
    others = (
        SwapRequest.query.filter(
            SwapRequest.id != swap.id,
            SwapRequest.status == SWAP_PENDING,
            (
                (SwapRequest.offered_item_id.in_([swap.offered_item_id, swap.requested_item_id]))
                | (SwapRequest.requested_item_id.in_([swap.offered_item_id, swap.requested_item_id]))
            ),
        )
        .with_for_update()
        .all()
    )
    for other in others:
        other.status = SWAP_CANCELLED
        other.updated_at = utcnow()


# --------------------------------------------------------------------- #
# Create a request
# --------------------------------------------------------------------- #
@swaps_bp.route("/request/<int:item_id>", methods=["GET", "POST"])
@login_required
def new_request(item_id: int):
    requested_item = db.session.get(Item, item_id)
    if requested_item is None:
        abort(404)

    if requested_item.user_id == current_user.id:
        flash("You cannot send a swap request for your own item.", "warning")
        return redirect(url_for("marketplace.item_detail", item_id=item_id))

    if requested_item.status != ITEM_AVAILABLE:
        flash("This item is currently unavailable for swaps.", "warning")
        return redirect(url_for("marketplace.item_detail", item_id=item_id))

    my_items = (
        Item.query.filter_by(user_id=current_user.id, status=ITEM_AVAILABLE)
        .order_by(Item.created_at.desc())
        .all()
    )

    if request.method == "POST":
        try:
            offered_id = int(request.form.get("offered_item_id", ""))
        except (TypeError, ValueError):
            offered_id = None
        message = request.form.get("message", "").strip()

        errors: list[str] = []
        offered_item = db.session.get(Item, offered_id) if offered_id else None
        if offered_item is None or offered_item.user_id != current_user.id:
            errors.append("Please select one of your own available items to offer.")
        elif offered_item.status != ITEM_AVAILABLE:
            errors.append("The item you are offering is no longer available.")
        if len(message) > 500:
            errors.append("Message must be 500 characters or fewer.")

        duplicate = None
        if offered_item is not None:
            duplicate = SwapRequest.query.filter_by(
                requester_id=current_user.id,
                receiver_id=requested_item.user_id,
                offered_item_id=offered_item.id,
                requested_item_id=requested_item.id,
                status=SWAP_PENDING,
            ).first()
            if duplicate:
                errors.append("You already have a pending request for this exact exchange.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template(
                "swap_request.html",
                requested_item=requested_item,
                my_items=my_items,
                form_data=request.form,
            )

        swap = SwapRequest(
            requester_id=current_user.id,
            receiver_id=requested_item.user_id,
            offered_item_id=offered_item.id,
            requested_item_id=requested_item.id,
            message=message,
            status=SWAP_PENDING,
        )
        db.session.add(swap)
        db.session.commit()
        flash(
            f"Swap request sent to {requested_item.user.name}. You'll be notified when they respond.",
            "success",
        )
        return redirect(url_for("dashboard.dashboard"))

    return render_template(
        "swap_request.html",
        requested_item=requested_item,
        my_items=my_items,
        form_data={},
    )


# --------------------------------------------------------------------- #
# Respond to / manage requests
# --------------------------------------------------------------------- #
@swaps_bp.route("/<int:swap_id>/accept", methods=["POST"])
@login_required
def accept(swap_id: int):
    swap = _get_swap_or_404(swap_id)
    if swap.receiver_id != current_user.id:
        abort(403)
    if swap.status != SWAP_PENDING:
        flash("This request has already been processed.", "warning")
        return redirect(url_for("dashboard.dashboard"))

    try:
        offered = db.session.get(Item, swap.offered_item_id)
        requested = db.session.get(Item, swap.requested_item_id)
        if offered.status != ITEM_AVAILABLE or requested.status != ITEM_AVAILABLE:
            raise ValueError("One of the items is no longer available for this exchange.")

        swap.status = SWAP_ACCEPTED
        swap.updated_at = utcnow()
        offered.status = ITEM_RESERVED
        requested.status = ITEM_RESERVED
        _cancel_other_pending_requests(swap)
        db.session.commit()
        flash(
            "Swap accepted! Both items are now reserved. Arrange the exchange with the other user.",
            "success",
        )
    except ValueError as exc:
        db.session.rollback()
        swap.status = SWAP_CANCELLED
        swap.updated_at = utcnow()
        db.session.commit()
        flash(f"Swap could not be accepted: {exc} The request was cancelled.", "warning")
    except Exception:
        db.session.rollback()
        flash("Something went wrong while accepting the request. Please try again.", "danger")

    return redirect(url_for("dashboard.dashboard"))


@swaps_bp.route("/<int:swap_id>/reject", methods=["POST"])
@login_required
def reject(swap_id: int):
    swap = _get_swap_or_404(swap_id)
    if swap.receiver_id != current_user.id:
        abort(403)
    if swap.status != SWAP_PENDING:
        flash("This request has already been processed.", "warning")
        return redirect(url_for("dashboard.dashboard"))

    swap.status = SWAP_REJECTED
    swap.updated_at = utcnow()
    db.session.commit()
    flash("Swap request rejected.", "info")
    return redirect(url_for("dashboard.dashboard"))


@swaps_bp.route("/<int:swap_id>/cancel", methods=["POST"])
@login_required
def cancel(swap_id: int):
    swap = _get_swap_or_404(swap_id)
    if swap.requester_id != current_user.id:
        abort(403)
    if swap.status != SWAP_PENDING:
        flash("Only a pending request can be cancelled.", "warning")
        return redirect(url_for("dashboard.dashboard"))

    swap.status = SWAP_CANCELLED
    swap.updated_at = utcnow()
    db.session.commit()
    flash("Swap request cancelled.", "info")
    return redirect(url_for("dashboard.dashboard"))


@swaps_bp.route("/<int:swap_id>/complete", methods=["POST"])
@login_required
def complete(swap_id: int):
    swap = _get_swap_or_404(swap_id)
    if current_user.id not in (swap.requester_id, swap.receiver_id):
        abort(403)
    if swap.status != SWAP_ACCEPTED:
        flash("Only an accepted swap can be marked as completed.", "warning")
        return redirect(url_for("dashboard.dashboard"))

    offered = db.session.get(Item, swap.offered_item_id)
    requested = db.session.get(Item, swap.requested_item_id)
    swap.status = SWAP_COMPLETED
    swap.updated_at = utcnow()
    offered.status = ITEM_SWAPPED
    requested.status = ITEM_SWAPPED
    db.session.commit()
    flash("Congratulations! The exchange has been marked as completed.", "success")
    return redirect(url_for("dashboard.dashboard"))
