"""Item CRUD: add, edit, delete listings with validated image uploads."""
from __future__ import annotations

import io
import os
import uuid

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

from config import Config
from models import (
    ITEM_AVAILABLE,
    SWAP_ACCEPTED,
    SWAP_PENDING,
    Item,
    SwapRequest,
    db,
)

items_bp = Blueprint("items", __name__, url_prefix="/items")


# --------------------------------------------------------------------- #
# Image handling
# --------------------------------------------------------------------- #
def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
    )


def save_image(file_storage) -> tuple[str, bytes | None, str]:
    """Validate, normalise and store an uploaded image.

    Returns (filename, image_bytes_or_None, mimetype). With
    MEDIA_BACKEND='db' the processed bytes are returned for database
    storage; otherwise the file is written under static/uploads and the
    filename is unique (uuid-based, never trusting the client filename).

    Raises ValueError with a user-friendly message on any validation failure.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("Please upload an item image.")
    if not allowed_file(file_storage.filename):
        raise ValueError(
            "Unsupported image format. Please upload a PNG, JPG, JPEG, GIF or WEBP file."
        )

    try:
        image = Image.open(file_storage)
        image.verify()  # confirms the file is a real, untruncated image
        file_storage.seek(0)
        image = Image.open(file_storage)
        image = ImageOps.exif_transpose(image)  # respect orientation, drop EXIF
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        # PIL raises SyntaxError for corrupt/truncated images (e.g. bad CRC).
        raise ValueError("That file is not a valid image. Please upload a real image file.")

    # Normalise mode and size.
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    max_dim = current_app.config["MAX_IMAGE_DIMENSION"]
    image.thumbnail((max_dim, max_dim), Image.LANCZOS)

    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    if ext == "jpeg":
        ext = "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    fmt = "JPEG" if ext == "jpg" else ext.upper()
    mimetype = f"image/{'jpeg' if ext == 'jpg' else ext}"

    buffer = io.BytesIO()
    image.save(buffer, format=fmt, quality=85)
    data = buffer.getvalue()

    # Re-open once to confirm the written bytes are readable (paranoia pays off).
    try:
        with Image.open(io.BytesIO(data)) as check:
            check.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ValueError("Image processing failed. Please try a different file.")

    if current_app.config.get("MEDIA_BACKEND") == "db":
        return filename, data, mimetype

    save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    with open(save_path, "wb") as fh:
        fh.write(data)
    return filename, None, mimetype


def _delete_image_file(filename: str) -> None:
    """Best-effort removal of a locally stored image (no-op in db mode)."""
    if current_app.config.get("MEDIA_BACKEND") == "db":
        return
    try:
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        if os.path.isfile(path):
            os.remove(path)
    except OSError:  # pragma: no cover - best effort cleanup
        pass


def _validate_item_form(form) -> tuple[dict, list[str]]:
    """Server-side validation shared by add/edit. Returns (data, errors)."""
    data = {
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "category": form.get("category", "").strip(),
        "condition": form.get("condition", "").strip(),
        "wanted_item": form.get("wanted_item", "").strip(),
        "notes": form.get("notes", "").strip(),
    }
    errors: list[str] = []
    if not data["title"] or len(data["title"]) < 3 or len(data["title"]) > 120:
        errors.append("Title must be between 3 and 120 characters.")
    if not data["description"] or len(data["description"]) < 10:
        errors.append("Description must be at least 10 characters.")
    if data["category"] not in Config.CATEGORIES:
        errors.append("Please choose a valid category.")
    if data["condition"] not in Config.CONDITIONS:
        errors.append("Please choose a valid condition.")
    if not data["wanted_item"] or len(data["wanted_item"]) < 2 or len(data["wanted_item"]) > 160:
        errors.append("Please state what you want in exchange (2-160 characters).")
    if len(data["notes"]) > 500:
        errors.append("Additional notes must be 500 characters or fewer.")
    return data, errors


# --------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------- #
@items_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_item():
    if request.method == "POST":
        data, errors = _validate_item_form(request.form)
        image_error = None
        filename = None
        image_bytes = None
        image_mimetype = None
        try:
            filename, image_bytes, image_mimetype = save_image(request.files.get("image"))
        except ValueError as exc:
            image_error = str(exc)

        if image_error:
            errors.append(image_error)

        if errors:
            # Don't leak orphan uploads when the rest of the form is invalid.
            if filename:
                _delete_image_file(filename)
            for err in errors:
                flash(err, "danger")
            return render_template(
                "add_item.html",
                categories=Config.CATEGORIES,
                conditions=Config.CONDITIONS,
                form_data=data,
            )

        item = Item(
            user_id=current_user.id,
            title=data["title"],
            description=data["description"],
            category=data["category"],
            image=filename,
            image_data=image_bytes,
            image_mimetype=image_mimetype,
            condition=data["condition"],
            wanted_item=data["wanted_item"],
            notes=data["notes"],
        )
        db.session.add(item)
        db.session.commit()
        flash("Your item has been listed on the marketplace!", "success")
        return redirect(url_for("marketplace.item_detail", item_id=item.id))

    return render_template(
        "add_item.html",
        categories=Config.CATEGORIES,
        conditions=Config.CONDITIONS,
        form_data={},
    )


@items_bp.route("/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def edit_item(item_id: int):
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    if item.user_id != current_user.id:
        abort(403)

    if request.method == "POST":
        data, errors = _validate_item_form(request.form)

        new_image = request.files.get("image")
        filename = item.image
        image_bytes = None
        image_mimetype = None
        if new_image and new_image.filename:
            try:
                filename, image_bytes, image_mimetype = save_image(new_image)
            except ValueError as exc:
                errors.append(str(exc))

        if errors:
            # Discard a newly saved image if the rest of the form is invalid.
            if filename and filename != item.image:
                _delete_image_file(filename)
            for err in errors:
                flash(err, "danger")
            return render_template(
                "edit_item.html",
                item=item,
                categories=Config.CATEGORIES,
                conditions=Config.CONDITIONS,
                form_data=data,
            )

        if filename != item.image:
            _delete_image_file(item.image)
            item.image = filename
            item.image_data = image_bytes
            item.image_mimetype = image_mimetype
        item.title = data["title"]
        item.description = data["description"]
        item.category = data["category"]
        item.condition = data["condition"]
        item.wanted_item = data["wanted_item"]
        item.notes = data["notes"]
        db.session.commit()
        flash("Listing updated successfully.", "success")
        return redirect(url_for("marketplace.item_detail", item_id=item.id))

    form_data = {
        "title": item.title,
        "description": item.description,
        "category": item.category,
        "condition": item.condition,
        "wanted_item": item.wanted_item,
        "notes": item.notes or "",
    }
    return render_template(
        "edit_item.html",
        item=item,
        categories=Config.CATEGORIES,
        conditions=Config.CONDITIONS,
        form_data=form_data,
    )


@items_bp.route("/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_item(item_id: int):
    item = db.session.get(Item, item_id)
    if item is None:
        abort(404)
    if item.user_id != current_user.id:
        abort(403)

    active = SwapRequest.query.filter(
        ((SwapRequest.offered_item_id == item.id) | (SwapRequest.requested_item_id == item.id))
        & SwapRequest.status.in_([SWAP_PENDING, SWAP_ACCEPTED])
    ).first()
    if item.status != ITEM_AVAILABLE or active:
        flash(
            "This item cannot be deleted while it is reserved or part of an active swap request.",
            "warning",
        )
        return redirect(url_for("marketplace.item_detail", item_id=item.id))

    _delete_image_file(item.image)
    item.image_data = None
    item.image_mimetype = None
    db.session.delete(item)
    db.session.commit()
    flash("Listing deleted.", "info")
    return redirect(url_for("dashboard.dashboard"))
