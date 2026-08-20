import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Adds created_at / updated_at to any model that inherits it."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDPrimaryKeyModel(models.Model):
    """
    Use UUID primary keys instead of auto-incrementing integers.

    Reasoning: book, order, and payment identifiers are exposed in URLs,
    watermarks, and receipts (see Master Development Protocol, sections 6
    and 9) - sequential integers would leak volume/scale information and
    are easier to enumerate.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class BaseModel(UUIDPrimaryKeyModel, TimeStampedModel):
    class Meta:
        abstract = True
