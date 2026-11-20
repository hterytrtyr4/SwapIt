"""SwapIt end-to-end test-suite (stdlib unittest, no extra deps).

Covers the 14 required workflows:
  1. Register a new user            8. Send a swap request
  2. Login and logout               9. Accept and reject requests
  3. Add a new item                10. Prevent duplicate requests
  4. Browse marketplace            11. Prevent unauthorized actions
  5. Search and filter items       12. Complete an accepted swap
  6. Edit and delete own listing   13. Verify dashboard statistics
  7. Mutual swap suggestions       14. CSRF + upload validation

Run with:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import re
import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image  # noqa: E402

from app import create_app  # noqa: E402
from config import TestingConfig  # noqa: E402
from matching import find_matches_for_user, pair_score  # noqa: E402
from models import (  # noqa: E402
    ITEM_AVAILABLE,
    ITEM_RESERVED,
    ITEM_SWAPPED,
    SWAP_ACCEPTED,
    SWAP_COMPLETED,
    SWAP_PENDING,
    SWAP_REJECTED,
    Item,
    SwapRequest,
    User,
    db,
)


def make_image_file(filename: str = "photo.png", color=(124, 58, 237), size=(320, 240)):
    """Build an in-memory image upload for tests."""
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    buf.seek(0)
    return (buf, filename)


class SwapItTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def register(self, name="Priya Sharma", email="priya@example.com",
                 password="password123", college="IIT Bombay", follow=True):
        return self.client.post(
            "/register",
            data=dict(
                name=name, email=email, password=password,
                confirm_password=password, college_name=college,
            ),
            follow_redirects=follow,
        )

    def login(self, email="priya@example.com", password="password123", follow=True):
        return self.client.post(
            "/login",
            data=dict(email=email, password=password),
            follow_redirects=follow,
        )

    def logout(self):
        return self.client.post("/logout", follow_redirects=True)

    def add_item(self, title="Casio Scientific Calculator", category="Electronics",
                 condition="Good", wanted="Engineering mechanics textbook",
                 description="Barely used Casio fx-991EX, perfect working condition.",
                 filename="calc.png", follow=True, notes=""):
        return self.client.post(
            "/items/add",
            data=dict(
                title=title, description=description, category=category,
                condition=condition, wanted_item=wanted, notes=notes,
                image=make_image_file(filename),
            ),
            content_type="multipart/form-data",
            follow_redirects=follow,
        )

    def create_user(self, name, email, college=""):
        user = User(name=name, email=email, college_name=college)
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        return user

    def create_item(self, user, title, wanted, category="Books", condition="Good",
                    description="A fine item in good shape.", status=ITEM_AVAILABLE):
        item = Item(
            user_id=user.id, title=title, description=description,
            category=category, image="placeholder.png", condition=condition,
            wanted_item=wanted, status=status,
        )
        db.session.add(item)
        db.session.commit()
        return item

    # ================================================================== #
    # 1. Registration
    # ================================================================== #
    def test_01_register_new_user(self):
        rv = self.register()
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"Dashboard", rv.data)
        self.assertIn(b"Priya", rv.data)
        user = User.query.filter_by(email="priya@example.com").first()
        self.assertIsNotNone(user)
        self.assertNotIn("password", user.password_hash.lower())
        self.assertTrue(user.check_password("password123"))
        self.assertFalse(user.password_hash.startswith("password"))

    def test_01b_register_validation(self):
        # Duplicate email
        self.register(follow=False)
        self.logout()
        rv = self.register(email="PRIYA@example.com")
        self.assertIn(b"already exists", rv.data)
        # Password mismatch
        rv = self.client.post(
            "/register",
            data=dict(name="Test User", email="t@example.com",
                      password="password123", confirm_password="different1",
                      college_name=""),
            follow_redirects=True,
        )
        self.assertIn(b"do not match", rv.data)
        # Short password
        rv = self.client.post(
            "/register",
            data=dict(name="Test User", email="t2@example.com",
                      password="short", confirm_password="short", college_name=""),
            follow_redirects=True,
        )
        self.assertIn(b"at least 8", rv.data)

    # ================================================================== #
    # 2. Login / logout
    # ================================================================== #
    def test_02_login_logout(self):
        self.register(follow=False)
        self.logout()
        rv = self.login(follow=False)
        self.assertEqual(rv.status_code, 302)
        rv = self.client.get("/dashboard")
        self.assertEqual(rv.status_code, 200)
        rv = self.logout()
        self.assertEqual(rv.status_code, 200)
        rv = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(rv.status_code, 302)  # protected route redirects
        self.assertIn("/login", rv.headers["Location"])

    def test_02b_login_wrong_password(self):
        self.register(follow=False)
        self.logout()
        rv = self.login(password="wrongpass123")
        self.assertIn(b"Invalid email or password", rv.data)

    # ================================================================== #
    # 3. Add item
    # ================================================================== #
    def test_03_add_item(self):
        self.register(follow=False)
        rv = self.add_item()
        self.assertIn(b"listed on the marketplace", rv.data)
        item = Item.query.filter_by(title="Casio Scientific Calculator").first()
        self.assertIsNotNone(item)
        self.assertEqual(item.status, ITEM_AVAILABLE)
        self.assertTrue(item.image.endswith(".png"))
        # Image exists on disk inside static/uploads
        path = os.path.join(self.app.config["UPLOAD_FOLDER"], item.image)
        self.assertTrue(os.path.isfile(path))

    def test_03b_add_item_validation(self):
        self.register(follow=False)
        rv = self.client.post(
            "/items/add",
            data=dict(title="ab", description="short", category="Nope",
                      condition="Bad", wanted_item="",
                      image=make_image_file()),
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Title must be", rv.data)
        self.assertIn(b"valid category", rv.data)
        self.assertEqual(Item.query.count(), 0)

    def test_03c_upload_rejects_non_image(self):
        self.register(follow=False)
        rv = self.client.post(
            "/items/add",
            data=dict(
                title="Sneaky file", description="This is not really an image at all.",
                category="Other", condition="New", wanted_item="Anything",
                image=(io.BytesIO(b"<?php echo 'pwn'; ?>"), "evil.php"),
            ),
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Unsupported image format", rv.data)
        self.assertEqual(Item.query.count(), 0)

    def test_03d_upload_rejects_fake_image(self):
        self.register(follow=False)
        rv = self.client.post(
            "/items/add",
            data=dict(
                title="Fake image", description="This claims to be a PNG but is not.",
                category="Other", condition="New", wanted_item="Anything",
                image=(io.BytesIO(b"\x89PNG\r\n fake fake fake"), "fake.png"),
            ),
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"not a valid image", rv.data)
        self.assertEqual(Item.query.count(), 0)

    # ================================================================== #
    # 4 & 5. Marketplace browsing, search, filter, sort
    # ================================================================== #
    def test_04_browse_marketplace(self):
        alice = self.create_user("Alice", "alice@example.com")
        self.create_item(alice, "Physics Textbook", "Scientific calculator")
        self.create_item(alice, "Badminton Racquet", "Chess board", category="Sports")
        self.create_item(alice, "Reserved Lamp", "Desk", category="Other", status=ITEM_RESERVED)

        rv = self.client.get("/marketplace")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"Physics Textbook", rv.data)
        self.assertIn(b"Badminton Racquet", rv.data)
        self.assertNotIn(b"Reserved Lamp", rv.data)  # only available items shown

    def test_04b_search_and_filter(self):
        alice = self.create_user("Alice", "alice@example.com")
        self.create_item(alice, "Physics Textbook", "Calculator", category="Books")
        self.create_item(alice, "Calculator", "Physics book", category="Electronics")

        rv = self.client.get("/marketplace?q=physics")
        self.assertIn(b"Physics Textbook", rv.data)
        # The other listing (titled "Calculator") must not appear; the shown card may
        # legitimately mention "Calculator" in its wanted-chip.
        self.assertNotIn(b">Calculator</a>", rv.data)

        rv = self.client.get("/marketplace?category=Electronics")
        self.assertIn(b"Calculator", rv.data)
        self.assertNotIn(b"Physics Textbook", rv.data)

        rv = self.client.get("/marketplace?sort=title")
        self.assertEqual(rv.status_code, 200)

    def test_04c_own_items_hidden_from_marketplace(self):
        self.register(follow=False)
        self.add_item(follow=False)
        rv = self.client.get("/marketplace")
        self.assertNotIn(b"Casio Scientific Calculator", rv.data)
        # Anonymous visitors see it
        self.logout()
        rv = self.client.get("/marketplace")
        self.assertIn(b"Casio Scientific Calculator", rv.data)

    # ================================================================== #
    # 6. Edit and delete own listing (+ ownership enforcement)
    # ================================================================== #
    def test_06_edit_and_delete_own_item(self):
        self.register(follow=False)
        self.add_item(follow=False)
        item = Item.query.first()

        rv = self.client.post(
            f"/items/{item.id}/edit",
            data=dict(
                title="Casio fx-991EX (updated)", description="Updated description here.",
                category="Electronics", condition="New", wanted_item="Chemistry book",
                notes="Pickup near library",
            ),
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Listing updated", rv.data)
        item = Item.query.first()
        self.assertEqual(item.title, "Casio fx-991EX (updated)")
        self.assertEqual(item.wanted_item, "Chemistry book")

        rv = self.client.post(f"/items/{item.id}/delete", follow_redirects=True)
        self.assertIn(b"Listing deleted", rv.data)
        self.assertEqual(Item.query.count(), 0)

    def test_06b_cannot_edit_or_delete_others_items(self):
        alice = self.create_user("Alice", "alice@example.com")
        their_item = self.create_item(alice, "Alice's Guitar", "Ukulele")
        self.register(follow=False)  # logged in as Priya

        rv = self.client.get(f"/items/{their_item.id}/edit")
        self.assertEqual(rv.status_code, 403)
        rv = self.client.post(f"/items/{their_item.id}/delete", follow_redirects=False)
        self.assertEqual(rv.status_code, 403)
        self.assertEqual(Item.query.count(), 1)

    # ================================================================== #
    # 7. Mutual swap matching
    # ================================================================== #
    def test_07_matching_finds_mutual_swap(self):
        alice = self.create_user("Alice", "alice@example.com")
        bob = self.create_user("Bob", "bob@example.com")
        calc = self.create_item(
            alice, "Calculator", "Engineering Book",
            category="Electronics", description="A scientific calculator.",
        )
        book = self.create_item(
            bob, "Engineering Book", "Calculator",
            category="Books", description="Engineering mechanics textbook.",
        )

        matches = find_matches_for_user(alice, Item.query.all())
        self.assertTrue(matches, "Expected a mutual match between calculator and book")
        best = matches[0]
        self.assertEqual(best["my_item"].id, calc.id)
        self.assertEqual(best["their_item"].id, book.id)
        self.assertEqual(best["owner_name"], "Bob")
        self.assertGreaterEqual(best["score"], 45)
        self.assertLessEqual(best["score"], 100)

        # One-sided pair must score meaningfully lower than a mutual pair.
        lonely = self.create_item(bob, "Random Lamp", "Vintage poster")
        s_mutual, _, _ = pair_score(calc, book)
        s_lonely, _, _ = pair_score(calc, lonely)
        self.assertGreater(s_mutual, s_lonely)

    def test_07b_matches_page_and_dashboard_section(self):
        alice = self.create_user("Alice", "alice@example.com")
        bob = self.create_user("Bob", "bob@example.com")
        self.create_item(alice, "Calculator", "Engineering Book", category="Electronics")
        self.create_item(bob, "Engineering Book", "Calculator", category="Books")
        self.login(email="alice@example.com")

        rv = self.client.get("/matches")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"mutual match", rv.data)
        self.assertIn(b"Engineering Book", rv.data)
        self.assertIn(b"Bob", rv.data)

        rv = self.client.get("/dashboard")
        self.assertIn(b"Suggested Matches", rv.data)

    # ================================================================== #
    # 8. Send swap request (+ duplicate / self-request guards)
    # ================================================================== #
    def _setup_two_users_with_items(self):
        alice = self.create_user("Alice", "alice@example.com")
        bob = self.create_user("Bob", "bob@example.com")
        a_item = self.create_item(alice, "Engineering Book", "Calculator", category="Books")
        b_item = self.create_item(bob, "Calculator", "Engineering Book", category="Electronics")
        return alice, bob, a_item, b_item

    def test_08_send_swap_request(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")

        rv = self.client.get(f"/swaps/request/{b_item.id}")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"Request a Swap", rv.data)

        rv = self.client.post(
            f"/swaps/request/{b_item.id}",
            data=dict(offered_item_id=str(a_item.id), message="Hi! Want to trade?"),
            follow_redirects=True,
        )
        self.assertIn(b"Swap request sent to Bob", rv.data)
        req = SwapRequest.query.first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, SWAP_PENDING)
        self.assertEqual(req.requester_id, alice.id)
        self.assertEqual(req.receiver_id, bob.id)

    def test_08b_cannot_request_own_item(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        rv = self.client.get(f"/swaps/request/{a_item.id}", follow_redirects=True)
        self.assertIn(b"your own item", rv.data)
        self.assertEqual(SwapRequest.query.count(), 0)

    def test_08c_duplicate_pending_request_blocked(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        for _ in range(2):
            rv = self.client.post(
                f"/swaps/request/{b_item.id}",
                data=dict(offered_item_id=str(a_item.id), message=""),
                follow_redirects=True,
            )
        self.assertIn(b"already have a pending request", rv.data)
        self.assertEqual(SwapRequest.query.count(), 1)

    # ================================================================== #
    # 9. Accept / reject requests
    # ================================================================== #
    def test_09_accept_request(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(
            f"/swaps/request/{b_item.id}",
            data=dict(offered_item_id=str(a_item.id), message=""),
        )
        self.logout()

        self.login(email="bob@example.com")
        req = SwapRequest.query.first()
        rv = self.client.post(f"/swaps/{req.id}/accept", follow_redirects=True)
        self.assertIn(b"Swap accepted", rv.data)

        req = SwapRequest.query.first()
        self.assertEqual(req.status, SWAP_ACCEPTED)
        self.assertEqual(db.session.get(Item, a_item.id).status, ITEM_RESERVED)
        self.assertEqual(db.session.get(Item, b_item.id).status, ITEM_RESERVED)

    def test_09b_reject_request(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(
            f"/swaps/request/{b_item.id}",
            data=dict(offered_item_id=str(a_item.id), message=""),
        )
        self.logout()

        self.login(email="bob@example.com")
        req = SwapRequest.query.first()
        rv = self.client.post(f"/swaps/{req.id}/reject", follow_redirects=True)
        self.assertIn(b"rejected", rv.data)
        self.assertEqual(SwapRequest.query.first().status, SWAP_REJECTED)
        # Items stay available after a rejection
        self.assertEqual(db.session.get(Item, a_item.id).status, ITEM_AVAILABLE)
        self.assertEqual(db.session.get(Item, b_item.id).status, ITEM_AVAILABLE)

    def test_09c_cancel_sent_request(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(
            f"/swaps/request/{b_item.id}",
            data=dict(offered_item_id=str(a_item.id), message=""),
        )
        req = SwapRequest.query.first()
        rv = self.client.post(f"/swaps/{req.id}/cancel", follow_redirects=True)
        self.assertIn(b"cancelled", rv.data)
        self.assertEqual(SwapRequest.query.first().status, "cancelled")

    def test_09d_accepting_reserves_items_and_blocks_new_requests(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        carol = self.create_user("Carol", "carol@example.com")
        c_item = self.create_item(carol, "Chess set", "Anything fun")

        self.login(email="alice@example.com")
        self.client.post(f"/swaps/request/{b_item.id}",
                         data=dict(offered_item_id=str(a_item.id), message=""))
        self.logout()

        # Carol also requests Bob's calculator before Alice's request is accepted.
        self.login(email="carol@example.com")
        self.client.post(f"/swaps/request/{b_item.id}",
                         data=dict(offered_item_id=str(c_item.id), message=""))
        self.logout()

        self.login(email="bob@example.com")
        req_a = SwapRequest.query.filter_by(requester_id=alice.id).first()
        self.client.post(f"/swaps/{req_a.id}/accept", follow_redirects=True)

        # Carol's overlapping pending request must be auto-cancelled.
        req_c = SwapRequest.query.filter_by(requester_id=carol.id).first()
        self.assertEqual(req_c.status, "cancelled")

        # New requests against the reserved item are refused.
        self.logout()
        self.login(email="carol@example.com")
        rv = self.client.get(f"/swaps/request/{b_item.id}", follow_redirects=True)
        self.assertIn(b"unavailable", rv.data)

    # ================================================================== #
    # 10-11. Authorization guards
    # ================================================================== #
    def test_10_only_receiver_can_accept(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(f"/swaps/request/{b_item.id}",
                         data=dict(offered_item_id=str(a_item.id), message=""))
        req = SwapRequest.query.first()

        # Requester (Alice) cannot accept her own request.
        rv = self.client.post(f"/swaps/{req.id}/accept", follow_redirects=False)
        self.assertEqual(rv.status_code, 403)

        # Random stranger cannot accept either.
        self.logout()
        carol = self.create_user("Carol", "carol@example.com")
        self.login(email="carol@example.com")
        rv = self.client.post(f"/swaps/{req.id}/accept", follow_redirects=False)
        self.assertEqual(rv.status_code, 403)
        self.assertEqual(SwapRequest.query.first().status, SWAP_PENDING)

    def test_10b_only_requester_can_cancel(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(f"/swaps/request/{b_item.id}",
                         data=dict(offered_item_id=str(a_item.id), message=""))
        req = SwapRequest.query.first()
        self.logout()

        self.login(email="bob@example.com")
        rv = self.client.post(f"/swaps/{req.id}/cancel", follow_redirects=False)
        self.assertEqual(rv.status_code, 403)
        self.assertEqual(SwapRequest.query.first().status, SWAP_PENDING)

    def test_10c_double_accept_is_ignored(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(f"/swaps/request/{b_item.id}",
                         data=dict(offered_item_id=str(a_item.id), message=""))
        self.logout()
        self.login(email="bob@example.com")
        req = SwapRequest.query.first()
        self.client.post(f"/swaps/{req.id}/accept")
        rv = self.client.post(f"/swaps/{req.id}/accept", follow_redirects=True)
        self.assertIn(b"already been processed", rv.data)

    # ================================================================== #
    # 12. Complete an accepted swap
    # ================================================================== #
    def test_12_complete_swap(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(f"/swaps/request/{b_item.id}",
                         data=dict(offered_item_id=str(a_item.id), message=""))
        self.logout()

        self.login(email="bob@example.com")
        req = SwapRequest.query.first()
        self.client.post(f"/swaps/{req.id}/accept")
        rv = self.client.post(f"/swaps/{req.id}/complete", follow_redirects=True)
        self.assertIn(b"marked as completed", rv.data)

        self.assertEqual(SwapRequest.query.first().status, SWAP_COMPLETED)
        self.assertEqual(db.session.get(Item, a_item.id).status, ITEM_SWAPPED)
        self.assertEqual(db.session.get(Item, b_item.id).status, ITEM_SWAPPED)

    def test_12b_cannot_complete_pending_swap(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(f"/swaps/request/{b_item.id}",
                         data=dict(offered_item_id=str(a_item.id), message=""))
        req = SwapRequest.query.first()
        rv = self.client.post(f"/swaps/{req.id}/complete", follow_redirects=True)
        self.assertIn(b"Only an accepted swap", rv.data)
        self.assertEqual(SwapRequest.query.first().status, SWAP_PENDING)

    def test_12c_cannot_delete_item_in_active_swap(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(f"/swaps/request/{b_item.id}",
                         data=dict(offered_item_id=str(a_item.id), message=""))
        rv = self.client.post(f"/items/{a_item.id}/delete", follow_redirects=True)
        self.assertIn(b"cannot be deleted", rv.data)
        self.assertEqual(Item.query.count(), 2)

    # ================================================================== #
    # 13. Dashboard statistics
    # ================================================================== #
    def test_13_dashboard_statistics(self):
        alice, bob, a_item, b_item = self._setup_two_users_with_items()
        self.login(email="alice@example.com")
        self.client.post(f"/swaps/request/{b_item.id}",
                         data=dict(offered_item_id=str(a_item.id), message=""))
        self.logout()
        self.login(email="bob@example.com")
        req = SwapRequest.query.first()
        self.client.post(f"/swaps/{req.id}/accept")

        rv = self.client.get("/dashboard")
        self.assertEqual(rv.status_code, 200)
        html = rv.data.decode()
        self.assertIn("Accepted swaps", html)
        # Bob has 1 listing, 0 active (it is reserved), 0 pending, 1 accepted, 0 completed.
        self.assertIn("Total listings", html)
        self.assertIn("Completed swaps", html)

        self.client.post(f"/swaps/{req.id}/complete")
        rv = self.client.get("/dashboard")
        self.assertIn("Swap History", rv.data.decode())

    def test_13b_profile_page(self):
        self.register(follow=False)
        self.add_item(follow=False)
        rv = self.client.get("/profile")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"priya@example.com", rv.data)
        self.assertIn(b"IIT Bombay", rv.data)
        self.assertIn(b"Member since", rv.data)

        rv = self.client.post(
            "/profile",
            data=dict(name="Priya S. Updated", email="priya@example.com",
                      college_name="IIT Delhi", current_password="",
                      new_password="", confirm_password=""),
            follow_redirects=True,
        )
        self.assertIn(b"Profile updated", rv.data)
        self.assertIn(b"IIT Delhi", rv.data)
        self.assertNotIn(b"password_hash", rv.data)

    def test_13c_profile_password_change(self):
        self.register(follow=False)
        rv = self.client.post(
            "/profile",
            data=dict(name="Priya Sharma", email="priya@example.com",
                      college_name="IIT Bombay", current_password="password123",
                      new_password="newpassword456", confirm_password="newpassword456"),
            follow_redirects=True,
        )
        self.assertIn(b"Profile updated", rv.data)
        self.logout()
        self.assertTrue(self.login(password="newpassword456").status_code == 200)

    # ================================================================== #
    # 14. CSRF + misc security
    # ================================================================== #
    def test_14_csrf_protection(self):
        self.app.config["WTF_CSRF_ENABLED"] = True
        try:
            rv = self.client.post(
                "/register",
                data=dict(name="Hacker", email="h@x.com", password="password123",
                          confirm_password="password123", college_name=""),
                follow_redirects=False,
            )
            self.assertEqual(rv.status_code, 400)  # missing CSRF token
            self.assertEqual(User.query.count(), 0)
        finally:
            self.app.config["WTF_CSRF_ENABLED"] = False

    def test_14b_password_never_exposed(self):
        self.register(follow=False)
        rv = self.client.get("/profile")
        self.assertNotIn(b"pbkdf2", rv.data)
        self.assertNotIn(b"password_hash", rv.data)

    def test_14c_404_page(self):
        rv = self.client.get("/item/9999")
        self.assertEqual(rv.status_code, 404)
        rv = self.client.get("/no-such-page")
        self.assertEqual(rv.status_code, 404)

    def test_14d_home_page_renders(self):
        rv = self.client.get("/")
        self.assertEqual(rv.status_code, 200)
        self.assertIn(b"Don't Buy It", rv.data)
        self.assertIn(b"How it works", rv.data)


if __name__ == "__main__":
    unittest.main(verbosity=2)
