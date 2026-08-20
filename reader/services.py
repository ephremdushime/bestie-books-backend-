"""
The secure reader engine (protocol sec. 8 and sec. 9).

Nothing here ever returns the underlying EPUB/PDF file or a URL to it.
`render_page` decrypts the source file in memory, rasterizes exactly one
page with PyMuPDF, burns in a visible watermark, embeds a forensic
(invisible) watermark in the image metadata, and returns PNG bytes only.
"""

import io
from datetime import timedelta

import fitz  # PyMuPDF
from django.utils import timezone
from PIL import Image, ImageDraw
from PIL.PngImagePlugin import PngInfo
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError

from common.crypto import unwrap_key, decrypt_bytes
from accounts.models import Device
from catalog.models import Book
from orders.models import LibraryEntry
from .models import ReadingSession, PageAccessLog

SESSION_LIFETIME = timedelta(hours=2)

# Fixed "page" dimensions EPUBs are reflowed to (fitz has no native EPUB
# pages - it paginates text to whatever page size you give it). PDFs are
# rendered at the same pixel size for a visually consistent reader.
PAGE_WIDTH = 1240
PAGE_HEIGHT = 1755
PAGE_FONTSIZE = 14


def start_session(user, book_id, device_id: str | None, ip_address: str | None) -> ReadingSession:
    try:
        book = Book.objects.select_related("asset").get(id=book_id)
    except Book.DoesNotExist:
        raise NotFound("Book not found.")

    if not LibraryEntry.objects.filter(user=user, book=book).exists():
        raise PermissionDenied("You do not own this book.")

    if not hasattr(book, "asset"):
        raise ValidationError("This book has no readable file uploaded yet.")

    device = None
    if device_id:
        device = Device.objects.filter(user=user, device_id=device_id, is_active=True).first()
        if device is None:
            raise PermissionDenied(
                "Unrecognized or inactive device. Register this device before reading."
            )

    session = ReadingSession.objects.create(
        user=user,
        book=book,
        device=device,
        expires_at=timezone.now() + SESSION_LIFETIME,
        last_ip=ip_address,
    )
    return session


def _get_valid_session(token: str, ip_address: str | None) -> ReadingSession:
    try:
        session = ReadingSession.objects.select_related("book__asset", "user").get(token=token)
    except ReadingSession.DoesNotExist:
        raise NotFound("Invalid session token.")

    if session.is_revoked:
        raise PermissionDenied(f"Session revoked: {session.revoked_reason or 'unspecified'}.")

    if session.expires_at < timezone.now():
        raise PermissionDenied("Session expired. Start a new reading session.")

    # Session monitoring (sec. 9, Layer 7): a mid-session IP change is
    # treated as suspicious and immediately revokes the session, rather
    # than trying to guess whether it's the same reader.
    if session.last_ip and ip_address and session.last_ip != ip_address:
        session.is_revoked = True
        session.revoked_reason = "IP address changed mid-session"
        session.save(update_fields=["is_revoked", "revoked_reason"])
        raise PermissionDenied("Session revoked: suspicious activity detected (IP changed).")

    if ip_address and not session.last_ip:
        session.last_ip = ip_address
        session.save(update_fields=["last_ip"])

    return session


def render_page(token: str, page_number: int, ip_address: str | None) -> bytes:
    session = _get_valid_session(token, ip_address)

    PageAccessLog.objects.create(
        session=session, page_number=page_number, ip_address=ip_address or "0.0.0.0"
    )

    asset = session.book.asset
    dek = unwrap_key(asset.wrapped_key)
    with asset.encrypted_file.open("rb") as f:
        ciphertext = f.read()
    plaintext = decrypt_bytes(ciphertext, dek)

    filetype = "pdf" if asset.file_type == asset.FileType.PDF else "epub"
    with fitz.open(stream=plaintext, filetype=filetype) as doc:
        if filetype == "epub":
            # EPUB has no fixed pages until reflowed - use the same
            # dimensions ingest_book_file used to compute page_count,
            # so page numbers stay stable between upload and reading.
            doc.layout(width=PAGE_WIDTH, height=PAGE_HEIGHT, fontsize=PAGE_FONTSIZE)

        if page_number < 1 or page_number > doc.page_count:
            raise NotFound(f"Page {page_number} out of range (1-{doc.page_count}).")
        page = doc.load_page(page_number - 1)
        dpi = None if filetype == "epub" else 150
        pix = page.get_pixmap(dpi=dpi) if dpi else page.get_pixmap()
        png_bytes = pix.tobytes("png")
        total_pages = doc.page_count

    _sync_reading_progress(session, page_number, doc_page_count=total_pages)
    return _watermark_image(png_bytes, session)


def _sync_reading_progress(session: ReadingSession, page_number: int, doc_page_count: int):
    """Protocol sec. 8: reading progress sync."""
    from orders.models import LibraryEntry

    progress = round((page_number / doc_page_count) * 100) if doc_page_count else 0
    LibraryEntry.objects.filter(user=session.user, book=session.book).update(
        last_read_at=timezone.now(), reading_progress_percent=min(progress, 100)
    )


def _watermark_image(png_bytes: bytes, session: ReadingSession) -> bytes:
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    w, h = image.size

    # Layer 5 - visible watermark: small footer with purchaser identity.
    footer_text = f"Purchased by: {session.user.full_name or session.user.email}  |  {session.user.email}"
    draw.rectangle([(0, h - 26), (w, h)], fill=(255, 255, 255, 220))
    draw.text((8, h - 20), footer_text, fill=(90, 90, 90, 255))

    # Best-effort forensic marking approximating Layer 4 ("invisible"
    # watermark). This is a faint, tiled, low-opacity overlay - not true
    # steganography - plus the same identity embedded in PNG metadata
    # below, so leaked pages can still be traced back to the purchaser.
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    odraw = ImageDraw.Draw(overlay)
    tag = f"{session.user.id} {session.user.email}"
    for y in range(0, h, 90):
        for x in range(0, w, 260):
            odraw.text((x, y), tag, fill=(120, 120, 120, 18))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

    metadata = PngInfo()
    metadata.add_text("user_id", str(session.user.id))
    metadata.add_text("email", session.user.email)
    metadata.add_text("session_id", str(session.id))
    metadata.add_text("timestamp", timezone.now().isoformat())

    out = io.BytesIO()
    image.save(out, format="PNG", pnginfo=metadata)
    return out.getvalue()
