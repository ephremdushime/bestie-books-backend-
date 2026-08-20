# Bestie Books — Backend (Core: Users, Books, Orders, Payments)

Django 6 + Django REST Framework implementation of the core data model and
API from the Master Development Protocol. Built to run on SQLite locally
and switch to PostgreSQL in staging/production via `.env`.

## What's implemented

| App        | Covers                                                                 |
|------------|-------------------------------------------------------------------------|
| `accounts` | Custom email-based User (Reader/Author/Admin roles), AuthorProfile, Device (2-device cap, sec. 9 Layer 6), JWT auth |
| `catalog`  | Category, Book (draft → pending → approved/rejected → published), BookAsset (encrypted file metadata) |
| `orders`   | Order, OrderItem, LibraryEntry (the reader's unlocked personal library) |
| `payments` | Payment (MTN MoMo / Airtel Money / Visa / Mastercard / PayPal), confirm/fail service that unlocks the library |
| `reader`   | Secure reading sessions + dynamic, watermarked, per-page rendering (protocol sec. 8-9) |
| `reviews`  | Reader reviews (rating + comment) with author responses |
| `notifications` | In-app notification feed, fired on purchase confirm, book approve/reject, review response, payout updates |
| `coupons`  | Admin-managed discount codes, applied at order creation, usage counted only on confirmed payment |
| `payouts`  | Author royalty payout requests, validated against a computed available balance, admin approve/reject/mark-paid |

### MTN MoMo integration (`payments/momo_client.py`)

Real integration against MTN's Collections API (`https://momodeveloper.mtn.com`),
not a stub - drop your sandbox credentials into `.env` and it works as-is:

- `get_access_token()` - Basic auth (API user + API key) -> Bearer token
- `request_to_pay()` - triggers the payment-approval prompt on the payer's
  phone; MTN stays PENDING until they approve/decline on their handset
- `get_transaction_status()` - poll to resolve PENDING -> SUCCESSFUL/FAILED

Flow: `POST /payments/` with `provider: mtn_momo` calls `request_to_pay`
immediately and returns the payment as PENDING. The client should then
either poll `POST /payments/{id}/check_status/`, or (in production, with
`MOMO_CALLBACK_URL` set to a public HTTPS endpoint) let MTN push the
result to `POST /payments/webhooks/mtn-momo/`. Either path runs through
the same `confirm_payment`/`fail_payment` functions from before, so the
library-unlock guarantee holds regardless of which one fires.

Network failures and non-2xx responses from MTN are caught and turned into
a cleanly `FAILED` payment rather than a crash - verified live: with no
reachable MTN sandbox from this environment, `POST /payments/` still
returns `201` with `status: "failed"` instead of a 500.

`payments/tests.py` mocks MTN's exact HTTP shape (headers, URL, payload)
with `responses` and asserts the client sends what MTN's docs specify -
this environment can't reach `sandbox.momodeveloper.mtn.com` directly,
so these mocked tests are the verification available without your real
keys; run `python manage.py test payments` once you drop in credentials
to sanity-check, then hit the sandbox for real via the live endpoints.

### Airtel Money integration (`payments/airtel_client.py`)

Same request/poll shape as MTN MoMo, against Airtel Africa's real
Openweb Collections API (`https://openapiuat.airtel.africa`):

- `get_access_token()` - OAuth2 client_credentials -> Bearer token
- `request_to_pay()` - POST `/merchant/v1/payments/`
- `get_transaction_status()` - GET `/standard/v1/payments/{id}`, where
  Airtel's status codes are `TS` (success), `TF` (failed), `TIP` (still
  in progress) - mapped onto the same `confirm_payment`/`fail_payment`
  functions MTN and the admin `simulate_confirm` stub all share.

Two more mocked-HTTP tests in `payments/tests.py` cover the success and
failure paths the same way as MTN's.

eKash (Rwanda's unified MTN MoMo + Airtel Money + bank rail) remains a
strong upgrade path once bank/aggregator merchant onboarding is in
place, since one integration would then cover all networks - MTN MoMo
and Airtel Money were built first because both have self-serve developer
sandboxes available today, unlike eKash's bank-mediated access.

### Card / bank transfer via Flutterwave (`payments/flutterwave_client.py`)

**Why Flutterwave over Paystack**: researched both for Rwanda specifically.
Flutterwave lists Rwanda as a fully operating market today - self-serve
signup, Mobile Money Rwanda, cards, bank transfer. Paystack (now part of
Stripe) announced Rwanda in 2023 but access there is still an invite-only
early-access program; its own current docs still scope self-serve
accounts to Nigeria, Ghana, South Africa, and Kenya. For a Rwandan
business wanting to actually accept payments now, that gate ruled
Paystack out regardless of its other strengths.

Flutterwave Standard is **redirect-based**, unlike MTN MoMo/Airtel's
phone-prompt push:

1. `initiate_flutterwave_payment()` - POST `/v3/payments`, returns a
   hosted checkout `link` covering card, bank transfer, and mobile money
   in one page. Stored on `Payment.checkout_url` for the frontend to
   redirect to.
2. The payer completes checkout on Flutterwave's page and is sent back
   to `redirect_url` (`{FRONTEND_URL}/checkout/{order_id}`).
3. **The redirect itself is never trusted as proof of payment** -
   Flutterwave's own docs note that even closing the checkout page
   produces a redirect. `check_flutterwave_status()` calls
   `verify_by_reference` and additionally checks the verified
   amount/currency actually match what was charged before confirming -
   an "successful" status with a short-paid amount does not unlock the
   library (covered by `test_verify_amount_mismatch_does_not_confirm`).
4. `payments/webhooks/flutterwave/` handles the async case, and - unlike
   MTN's unsigned callback - verifies Flutterwave's `verif-hash` header
   against `FLUTTERWAVE_WEBHOOK_SECRET_HASH` before acting on it.

4 mocked-HTTP tests cover initiation, successful verification, the
amount-mismatch defense, and failure - live in this environment (with no
reachable Flutterwave API), initiating still degrades to a clean `201` /
`status: failed`, same as MTN and Airtel.

Not yet built: an admin UI for editing book/category details beyond
approve/reject (goes through Django admin for now).

### The secure reader engine (`reader` app)

- **Encryption at rest** (`common/crypto.py`): each uploaded book gets a
  random per-book key (DEK), envelope-encrypted with a master key before
  storage. The plaintext file is never written to disk - `catalog.services.ingest_book_file`
  encrypts it in memory on upload.
- **No raw file access, ever**: `BookAsset` never exposes `encrypted_file`,
  the wrapped key, or a download URL through the API. The only way to see
  content is one rendered page at a time via a reading session.
- **Reading sessions** (`POST /reader/sessions/`): only issued if a
  `LibraryEntry` proves ownership. Each session gets a unique token and a
  2-hour expiry.
- **Dynamic page rendering** (`GET /reader/read/<token>/pages/<n>/`):
  decrypts the file in memory and rasterizes exactly one page - PDF pages
  render directly via PyMuPDF; EPUB is reflowed to a fixed page size
  (`doc.layout(...)`) so it paginates consistently between upload-time
  page counting and read-time rendering. Either way, only a PNG comes
  back - never the source file.
- **Reading progress sync** (protocol sec. 8): every page fetch updates
  the reader's `LibraryEntry.reading_progress_percent` and `last_read_at`.
- **Bookmarks & highlights** (`/reader/bookmarks/`, `/reader/highlights/`):
  standard CRUD, scoped to the caller, filterable by `?book=<id>`, and
  gated on actually owning the book (same `LibraryEntry` check as
  starting a session).
- **Visible + forensic watermarking**: every page gets a visible "Purchased
  by" footer burned in, plus the purchaser's user ID/email and a faint
  tiled overlay embedded in the image (PNG metadata + low-opacity text) so
  a leaked page can be traced back to whoever downloaded it. This is a
  best-effort forensic mark, not true steganography.
- **Session monitoring**: an IP change mid-session immediately revokes the
  session (`PageAccessLog` records every request for audit).
- **Device cap**: reading sessions require the caller's device to be
  registered and active, on top of the existing 2-device limit.

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit as needed, incl. MOMO_* sandbox keys
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Switch to PostgreSQL by setting `DB_ENGINE=postgres` and the `DB_*` vars in `.env`.

## API surface (all under `/api/v1/`)

```
POST   auth/register/              Sign up as reader or author
POST   auth/token/                 Log in (JWT access + refresh)
POST   auth/token/refresh/
GET    users/me/                   Current user profile
PATCH  users/me/
GET/POST/DELETE  devices/          Manage registered devices (max 2 active)

GET/POST         categories/       Admin write, public read
GET/POST/PATCH   books/            Author manages own books, public sees published only
POST   books/{id}/submit_for_approval/   (author)
POST   books/{id}/approve/               (admin)
POST   books/{id}/reject/                (admin)
POST   books/{id}/upload_asset/          (author) multipart: file + file_type (epub/pdf)
GET    books/my_sales/                   (author) per-book units_sold + revenue for the dashboard

GET/PATCH  authors/me/                   Current user's AuthorProfile (pen name, bio, payout method)

GET/POST  orders/                  Reader creates an order from book_ids (+ optional coupon_code)
GET       orders/{id}/
GET       library/                 Reader's unlocked books
GET       library/{id}/

GET/POST  payments/                Initiate a payment against a pending order
GET       payments/{id}/
POST      payments/{id}/check_status/       Poll provider status (MTN MoMo + Airtel Money hit the real APIs)
POST      payments/{id}/simulate_confirm/   (admin, dev stand-in where no sandbox exists)
POST      payments/{id}/simulate_fail/      (admin)
POST      payments/webhooks/mtn-momo/       MTN's async callback (needs public HTTPS + MOMO_CALLBACK_URL)
POST      payments/webhooks/flutterwave/    Flutterwave's signed webhook (verifies verif-hash header)

POST   reader/sessions/                          Start a reading session for an owned book
GET    reader/read/{token}/pages/{n}/            Fetch one rendered, watermarked page (PNG)
GET/POST/PATCH/DELETE  reader/bookmarks/         Saved pages (filter: ?book=<id>)
GET/POST/PATCH/DELETE  reader/highlights/        Highlighted passages + notes (filter: ?book=<id>)

GET/POST/PATCH/DELETE  reviews/           Filter: ?book=<id>; create requires owning the book
POST   reviews/{id}/respond/              (book's author only) reply to a review

GET    notifications/                     Own in-app notifications
POST   notifications/{id}/mark_read/
POST   notifications/mark_all_read/

GET/POST/PATCH/DELETE  coupons/           (admin only) discount codes

GET/POST  payouts/                        Author requests a royalty payout
GET       payouts/balance/                (author) available balance = confirmed revenue − claimed payouts
POST      payouts/{id}/approve/           (admin)
POST      payouts/{id}/mark_paid/         (admin)
POST      payouts/{id}/reject/            (admin)
```

`admin/` is the Django admin, usable immediately for managing all data.

## Design notes

- **UUID primary keys** everywhere (`common.BaseModel`) — book/order/payment
  IDs get exposed in URLs, watermarks, and receipts, so sequential integers
  would leak volume and be guessable.
- **BookAsset never exposes the encrypted file, wrapped key, or a download
  URL** through the API — the only way to see content is one rendered
  page at a time via a reading session (protocol sec. 9, Layer 3).
- **Payment confirmation is one transactional function** (`payments.services.confirm_payment`)
  so "paid" and "library unlocked" can never drift out of sync, whether
  it's called from `check_status`, the MTN webhook, or an admin's
  `simulate_confirm`.
- **Order amounts are always server-computed** from `Book.price` at order
  time — never trust a client-supplied amount for payment.

## Verified

Migrations run clean, `manage.py check` passes, and the following was
tested end-to-end against a live dev server:

- register → author publishes a book → admin approves → reader orders →
  payment initiated → payment confirmed → library unlocked
- author uploads a PDF → confirmed encrypted on disk (no `%PDF-` header) →
  reader without a purchase is blocked from starting a session → after
  purchase, session starts and a watermarked page renders correctly →
  out-of-range page returns 404
- mid-session IP change auto-revokes the session
- a 3rd device registration is rejected past the 2-device cap
- an EPUB uploads, reflows to 6 pages, renders a watermarked page
  identical in pipeline to the PDF path, and syncs reading progress
  (50% after page 3 of 6)
- bookmarks and highlights can be created/listed/filtered by the owner,
  and are blocked for a reader who hasn't purchased the book
- MTN MoMo: 6 mocked-HTTP tests (`payments/tests.py`) confirm the client
  sends the exact headers/payload MTN's docs specify, and that SUCCESSFUL/
  FAILED statuses correctly unlock/don't-unlock the library; live against
  this environment's blocked network, initiating a payment still degrades
  to a clean `201`/`status: failed` instead of a 500
- Airtel Money: same treatment, 2 more mocked-HTTP tests against the real
  Openweb Collections API shape
- Flutterwave: 4 mocked-HTTP tests, including one that proves an
  amount-mismatched "successful" verification does NOT unlock the
  library - live, initiating still degrades to a clean 201/failed with
  no reachable API
- coupons: a 2-item order with a 20%-off code correctly totaled `$12.00`
  from a `$15.00` subtotal, and `used_count` only incremented after the
  payment actually confirmed (not at order creation)
- notifications: fired and retrievable after purchase confirmation, book
  approval, a review response, and a payout being marked paid
- reviews: a reader could review only a book they owned; the book's
  author could respond, which notified the reviewer
- payouts: `available_balance` computed correctly from real sales,
  a request within balance succeeded, a request exceeding it was
  rejected with the actual balance in the error message, and admin
  `mark_paid` notified the author

