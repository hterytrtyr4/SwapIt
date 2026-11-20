"""Optional: seed the database with demo users and listings.

Usage:  python seed_demo.py

Every demo account uses the password: password123
This script is purely for local demonstrations — it is never run
automatically by the application.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from PIL import Image, ImageDraw  # noqa: E402

from app import app  # noqa: E402
from models import (  # noqa: E402
    ITEM_SWAPPED,
    SWAP_COMPLETED,
    SWAP_PENDING,
    Item,
    SwapRequest,
    User,
    db,
)

DEMO_PASSWORD = "password123"


def _demo_image(label: str, color: tuple, filename: str) -> str:
    """Generate a simple labelled placeholder image for a demo listing."""
    uploads = app.config["UPLOAD_FOLDER"]
    path = os.path.join(uploads, filename)
    if os.path.isfile(path):
        return filename
    img = Image.new("RGB", (640, 480), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([24, 24, 616, 456], outline=(255, 255, 255), width=6)
    draw.text((48, 210), label, fill=(255, 255, 255))
    img.save(path, format="JPEG", quality=85)
    return filename


DEMO_USERS = [
    ("Aarav Mehta", "aarav@demo.swapit", "IIT Bombay"),
    ("Priya Sharma", "priya@demo.swapit", "IIT Delhi"),
    ("Rohan Das", "rohan@demo.swapit", "NIT Trichy"),
]

DEMO_ITEMS = [
    # (owner email, title, description, category, condition, wanted, notes, color)
    ("aarav@demo.swapit", "Casio Scientific Calculator",
     "Barely used Casio fx-991EX. Perfect for engineering coursework, all functions working.",
     "Electronics", "Good", "Engineering mechanics textbook",
     "Can hand over at the campus library.", (109, 40, 217)),
    ("priya@demo.swapit", "Engineering Mechanics Textbook",
     "Engineering Mechanics by R.C. Hibbeler, 8th edition. Some highlighting in the first three chapters, otherwise clean.",
     "Books", "Good", "Scientific calculator",
     "Looking to swap before mid-terms.", (217, 119, 6)),
    ("rohan@demo.swapit", "Yonex Badminton Racquet",
     "Yonex Nanoray light-weight racquet with a fresh grip and full cover included.",
     "Sports", "Good", "Chess board or board games",
     "", (22, 163, 74)),
    ("aarav@demo.swapit", "Mechanical Pencil Set",
     "Set of 5 high-quality mechanical pencils (0.5mm) plus two refill packs.",
     "Stationery", "New", "Sketch pens or art supplies",
     "", (37, 99, 235)),
    ("priya@demo.swapit", "Bluetooth Speaker",
     "Compact portable speaker, punchy bass, about 6 hours of battery life. Minor scuffs on the base.",
     "Electronics", "Used", "Study lamp or calculator",
     "Charging cable included.", (124, 58, 237)),
    ("rohan@demo.swapit", "Harry Potter Box Set (1-3)",
     "First three Harry Potter books, paperback, read once and stored carefully.",
     "Books", "Good", "Any thriller novels",
     "", (225, 29, 72)),
    # Pair that has already been swapped (shows up in swap history).
    ("priya@demo.swapit", "Graphic Drawing Tablet",
     "Entry-level drawing tablet with stylus, great for design coursework. Already swapped!",
     "Electronics", "Good", "Wireless mouse",
     "", (14, 165, 233)),
    ("rohan@demo.swapit", "Wireless Mouse",
     "Ergonomic wireless mouse with USB receiver. Already swapped!",
     "Electronics", "Good", "Drawing tablet",
     "", (168, 85, 247)),
]


def seed() -> None:
    with app.app_context():
        users_by_email: dict[str, User] = {}
        for name, email, college in DEMO_USERS:
            user = User.query.filter_by(email=email).first()
            if user is None:
                user = User(name=name, email=email, college_name=college)
                user.set_password(DEMO_PASSWORD)
                db.session.add(user)
                db.session.flush()
                print(f"+ user  {email}")
            users_by_email[email] = user

        for email, title, desc, cat, cond, wanted, notes, color in DEMO_ITEMS:
            if Item.query.filter_by(title=title).first() is not None:
                continue
            filename = _demo_image(title, color, f"demo_{abs(hash(title)) % 100000}.jpg")
            item = Item(
                user_id=users_by_email[email].id,
                title=title, description=desc, category=cat,
                image=filename, condition=cond, wanted_item=wanted, notes=notes,
            )
            db.session.add(item)
            print(f"+ item  [{email}] {title}")

        db.session.flush()

        # --- Demo swap history: a completed exchange between Priya & Rohan ----
        if SwapRequest.query.count() == 0:
            tablet = Item.query.filter_by(title="Graphic Drawing Tablet").first()
            mouse = Item.query.filter_by(title="Wireless Mouse").first()
            done_swap = SwapRequest(
                requester_id=tablet.user_id,
                receiver_id=mouse.user_id,
                offered_item_id=tablet.id,
                requested_item_id=mouse.id,
                message="Tablet for the mouse — thanks!",
                status=SWAP_COMPLETED,
            )
            db.session.add(done_swap)
            tablet.status = ITEM_SWAPPED
            mouse.status = ITEM_SWAPPED
            print("+ swap  completed: Graphic Drawing Tablet <-> Wireless Mouse")

            # --- Demo pending request: Rohan offers HP set for Priya's speaker
            hp = Item.query.filter_by(title="Harry Potter Box Set (1-3)").first()
            speaker = Item.query.filter_by(title="Bluetooth Speaker").first()
            pending = SwapRequest(
                requester_id=hp.user_id,
                receiver_id=speaker.user_id,
                offered_item_id=hp.id,
                requested_item_id=speaker.id,
                message="Hey! Would you swap the speaker for the first three Potter books?",
                status=SWAP_PENDING,
            )
            db.session.add(pending)
            print("+ swap  pending: Harry Potter Box Set (1-3) -> Bluetooth Speaker")

        db.session.commit()
        print("\nDone. Demo login: aarav@demo.swapit / priya@demo.swapit / rohan@demo.swapit")
        print(f"Password for all demo accounts: {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
