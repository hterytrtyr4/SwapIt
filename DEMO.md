# SwapIt — 3-minute demo script

Everything below runs offline against the local SQLite database. No accounts to
create, no external services, no API keys.

```bash
make dev        # install + seed demo data + start the server
# → http://127.0.0.1:5000
```

`make dev` is `make install && make seed && make run`. If you prefer to do it
step by step, see [README §4](README.md#4-run-locally).

---

## 1. Demo accounts

All demo users share the password **`password123`**.

| Email | College | What they are holding |
| --- | --- | --- |
| `aarav@demo.swapit` | IIT Bombay | Casio Scientific Calculator, Mechanical Pencil Set |
| `priya@demo.swapit` | IIT Delhi | Engineering Mechanics Textbook, Bluetooth Speaker, *(Graphic Drawing Tablet — already swapped)* |
| `rohan@demo.swapit` | NIT Trichy | Yonex Badminton Racquet, Harry Potter Box Set, *(Wireless Mouse — already swapped)* |

Seeded state: **8 listings**, **1 completed swap**, **1 pending swap**.

Log out between accounts from the navbar avatar menu to see the other side of a
request — the same swap looks different to the sender and the receiver.

---

## 2. The story to show (in order)

### a) Landing page — `/`
Hero reads *"Don't Buy It. Swap It."*, then How It Works, then **featured items
pulled from the real database** (not hard-coded placeholders). Point out there is
no "Buy" button anywhere by design.

### b) Marketplace — `/marketplace`
Six available items from three different owners. Demonstrate:
- **Search** `calculator` → one result
- **Category** filter → `Books` → 2 results
- **Sort** → Title A–Z flips the order
- Notice you never see your own items here, and swapped items are gone

### c) Log in as `aarav@demo.swapit` — `/dashboard`
The stat cards read: 2 total listings, 2 active, 0 pending, **0 completed**, and
the *My Items* table shows both his items as `available`.

### d) The matching engine — `/matches`
This is the flagship feature. The page is titled *"Swaps that fit both sides"* and
surfaces the classic pair:

> **Casio Scientific Calculator** (Aarav wants an *Engineering Mechanics Textbook*)
> ↔ **Engineering Mechanics Textbook** (Priya wants a *Scientific calculator*)
> → **78 / 100 potential match**

Explain the score is a **geometric mean of both directions**, so a one-sided match
can't rank high. Suggestions are never auto-accepted — they are hints, and the
human decides. Nothing here is generated without a real listing behind it.

### e) Send a request — `/marketplace` → open an item → *Request a Swap*
Pick Priya's textbook, choose the calculator as the offer, add a short message,
submit. Dashboard now shows the request under **Sent Swap Requests** with a
`pending` badge.

### f) The other side — log out, log in as `priya@demo.swapit`
Her dashboard shows the same request under **Incoming Swap Requests**, and the navbar
shows a pending-request badge. She clicks **Accept**:
- both items flip to `reserved`
- any overlapping pending requests on those items are auto-cancelled
- the swap moves to *accepted*, and can later be marked **completed**
  (items become `swapped`)

Rohan already has a pending request waiting for Priya — good to show that
incoming and sent queues are independent.

### g) Guardrails worth demoing
- Open `/items/<id>/edit` for an item you don't own → **403** page
- Request your own item → blocked with a flash message
- Send the same request twice → duplicate blocked
- Try to delete an item that is in an accepted swap → blocked
- Submit any form without a CSRF token → **400**

---

## 3. Reset the demo

```bash
make reset      # wipe instance/ + uploads, reseed from scratch
```

The database lives in `instance/swapit.db` and images in `static/uploads/`.
Both are git-ignored, so the demo is always disposable and never pollutes the
repository.

---

## 4. Talking points for a viva / review

- SQLite + SQLAlchemy ORM, foreign keys enforced; no hand-written SQL strings
- Password hashing via Werkzeug, `HttpOnly` + `SameSite=Lax` session cookies
- CSRF protection on **every** state-changing form (Flask-WTF)
- Upload validation: extension whitelist → Pillow `verify()` → re-encode (strips
  EXIF and fake headers) → resize to ≤1280 px → UUID filename
- Matching is explainable: normalisation → token coverage → `difflib` ratio →
  category hint → mutual geometric mean
- 35 automated tests cover the 14 required workflows, including negative cases
