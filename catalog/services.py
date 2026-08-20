import hashlib

import fitz  # PyMuPDF
from django.core.files.base import ContentFile

from common.crypto import generate_dek, wrap_key, encrypt_bytes
from reader.services import PAGE_WIDTH, PAGE_HEIGHT, PAGE_FONTSIZE
from .models import BookAsset, Book


def ingest_book_file(book: Book, uploaded_file, file_type: str) -> BookAsset:
    """
    Protocol sec. 7 (System processes): metadata extraction + encryption.
    Virus scanning is stubbed (no AV engine wired up yet) but left as an
    explicit, visible step rather than silently skipped.

    The plaintext file is only ever held in memory here, long enough to
    checksum, page-count, and encrypt it - it is never written to disk
    unencrypted.
    """
    raw = uploaded_file.read()

    checksum = hashlib.sha256(raw).hexdigest()
    virus_scan_passed = _stub_virus_scan(raw)

    page_count = None
    if file_type == BookAsset.FileType.PDF:
        with fitz.open(stream=raw, filetype="pdf") as doc:
            page_count = doc.page_count
    elif file_type == BookAsset.FileType.EPUB:
        with fitz.open(stream=raw, filetype="epub") as doc:
            # EPUB has no fixed pages until reflowed to a page size - use
            # the same dimensions the reader renders at (reader/services.py
            # PAGE_WIDTH/PAGE_HEIGHT) so the count matches what readers see.
            doc.layout(width=PAGE_WIDTH, height=PAGE_HEIGHT, fontsize=PAGE_FONTSIZE)
            page_count = doc.page_count

    dek = generate_dek()
    ciphertext = encrypt_bytes(raw, dek)

    asset, _ = BookAsset.objects.update_or_create(
        book=book,
        defaults=dict(
            file_type=file_type,
            original_filename=uploaded_file.name,
            checksum_sha256=checksum,
            wrapped_key=wrap_key(dek),
            page_count=page_count,
            virus_scan_passed=virus_scan_passed,
        ),
    )
    asset.encrypted_file.save(f"{book.id}.enc", ContentFile(ciphertext), save=True)
    return asset


def _stub_virus_scan(raw: bytes) -> bool:
    """Placeholder for a real AV/ClamAV integration - always passes for now."""
    return True
