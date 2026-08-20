from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from common.models import BaseModel
from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    A single User model backs all three roles from the protocol
    (Reader, Author, Administrator). `role` drives permissioning;
    `AuthorProfile` holds author-only fields via a one-to-one link,
    keeping the base table lean for the much larger reader population.
    """

    class Role(models.TextChoices):
        READER = "reader", "Reader"
        AUTHOR = "author", "Author"
        ADMIN = "admin", "Administrator"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.READER)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  # email verification, sec. 5

    # Social login references (sec. 5 - Google / Apple / Facebook login)
    google_sub = models.CharField(max_length=255, blank=True, null=True, unique=True)
    apple_sub = models.CharField(max_length=255, blank=True, null=True, unique=True)

    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "accounts_user"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    @property
    def is_author(self):
        return self.role == self.Role.AUTHOR


class AuthorProfile(BaseModel):
    """Author-only fields (protocol sec. 3 - Author, sec. 12 - Author Dashboard)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="author_profile")
    pen_name = models.CharField(max_length=150, blank=True)
    bio = models.TextField(blank=True)
    payout_method = models.CharField(max_length=50, blank=True)  # e.g. "mtn_momo", "bank"
    payout_details = models.JSONField(default=dict, blank=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        db_table = "accounts_author_profile"

    def __str__(self):
        return self.pen_name or self.user.email


class Device(BaseModel):
    """
    Enforces the device-limit security control (protocol sec. 9, Layer 6):
    max 2 active devices per reader; additional devices require verification.
    """

    class DeviceType(models.TextChoices):
        WEB = "web", "Web Browser"
        ANDROID = "android", "Android App"
        IOS = "ios", "iOS App"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    device_id = models.CharField(max_length=255)  # client-generated fingerprint
    device_name = models.CharField(max_length=150, blank=True)
    device_type = models.CharField(max_length=10, choices=DeviceType.choices)
    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "accounts_device"
        unique_together = ("user", "device_id")

    def __str__(self):
        return f"{self.user.email} - {self.device_name or self.device_id[:8]}"
