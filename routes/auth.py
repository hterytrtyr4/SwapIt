"""Authentication routes: register, login, logout."""
from __future__ import annotations

import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from models import User, db

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_safe_next(target: str | None) -> bool:
    return bool(target) and target.startswith("/") and not target.startswith("//")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        college = request.form.get("college_name", "").strip()

        errors: list[str] = []
        if not name or len(name) < 2 or len(name) > 100:
            errors.append("Full name must be between 2 and 100 characters.")
        if not email or not EMAIL_RE.match(email):
            errors.append("Please enter a valid email address.")
        if not password or len(password) < 8:
            errors.append("Password must be at least 8 characters long.")
        if password != confirm:
            errors.append("Passwords do not match.")
        if college and len(college) > 120:
            errors.append("College name must be 120 characters or fewer.")
        if not errors:
            existing = User.query.filter(db.func.lower(User.email) == email).first()
            if existing:
                errors.append("An account with this email already exists.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template(
                "register.html",
                form_data={"name": name, "email": email, "college_name": college},
            )

        user = User(name=name, email=email, college_name=college)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash(f"Welcome to SwapIt, {user.name.split()[0]}! Your account is ready.", "success")
        next_page = request.args.get("next")
        return redirect(next_page if _is_safe_next(next_page) else url_for("dashboard.dashboard"))

    return render_template("register.html", form_data={})


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user is None or not user.check_password(password):
            flash("Invalid email or password. Please try again.", "danger")
            return render_template("login.html", form_data={"email": email})

        login_user(user, remember=remember)
        flash(f"Welcome back, {user.name.split()[0]}!", "success")
        next_page = request.args.get("next")
        return redirect(next_page if _is_safe_next(next_page) else url_for("dashboard.dashboard"))

    return render_template("login.html", form_data={})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out. See you soon!", "info")
    return redirect(url_for("marketplace.index"))
