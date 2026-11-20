"""Public pages: landing page, marketplace browsing, item detail."""
from __future__ import annotations

from flask import Blueprint, Response, abort, render_template, request
from flask_login import current_user

from config import Config
from models import ITEM_AVAILABLE, Item, db

marketplace_bp = Blueprint("marketplace", __name__)

SORT_OPTIONS = {
    "newest": Item.created_at.desc(),
    "oldest": Item.created_at.asc(),
    "title": Item.title.asc(),
}


@marketplace_bp.route("/")
def index():
    featured = (
        Item.query.filter_by(status=ITEM_AVAILABLE)
        .order_by(Item.created_at.desc())
        .limit(6)
        .all()
    )
    if current_user.is_authenticated:
        featured = [i for i in featured if i.user_id != current_user.id][:6]

    # Real community numbers for the hero proof + stats strip.
    from models import SWAP_COMPLETED, SwapRequest, User

    member_count = User.query.count()
    open_count = Item.query.filter_by(status=ITEM_AVAILABLE).count()
    completed_count = SwapRequest.query.filter_by(status=SWAP_COMPLETED).count()

    return render_template(
        "index.html",
        featured=featured,
        member_count=member_count,
        open_count=open_count,
        completed_count=completed_count,
        category_count=len(Config.CATEGORIES),
    )


@marketplace_bp.route("/marketplace")
def marketplace():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "newest")

    query = Item.query.filter_by(status=ITEM_AVAILABLE)
    if current_user.is_authenticated:
        query = query.filter(Item.user_id != current_user.id)

    if q:
        query = query.filter(Item.title.ilike(f"%{q}%"))
    if category in Config.CATEGORIES:
        query = query.filter_by(category=category)

    query = query.order_by(SORT_OPTIONS.get(sort, Item.created_at.desc()))
    items = query.all()

    return render_template(
        "marketplace.html",
        items=items,
        categories=Config.CATEGORIES,
        q=q,
        category=category,
        sort=sort,
    )


@marketplace_bp.route("/item/<int:item_id>")
def item_detail(item_id: int):
    item = db_get_item_or_404(item_id)

    suggested_score = None
    best_own_item = None
    if current_user.is_authenticated and item.user_id != current_user.id:
        from matching import find_matches_for_user

        all_items = Item.query.all()
        matches = find_matches_for_user(current_user, all_items, limit=50)
        related = [m for m in matches if m["their_item"].id == item.id]
        if related:
            best = related[0]
            suggested_score = best["score"]
            best_own_item = best["my_item"]

    return render_template(
        "item_detail.html",
        item=item,
        suggested_score=suggested_score,
        best_own_item=best_own_item,
    )


@marketplace_bp.route("/image/<int:item_id>")
def item_image(item_id: int):
    """Serve an item image stored in the database (MEDIA_BACKEND=db)."""
    item = db.session.get(Item, item_id)
    if item is None or not item.image_data:
        abort(404)
    response = Response(item.image_data, mimetype=item.image_mimetype or "image/jpeg")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


def db_get_item_or_404(item_id: int) -> Item:
    from models import db

    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    return item
