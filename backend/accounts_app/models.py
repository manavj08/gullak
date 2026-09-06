from django.contrib.auth.models import AbstractUser
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.core.validators import RegexValidator

phone_validator = RegexValidator(
    regex=r'^\+?[0-9]{10,15}$',
    message="Enter a valid phone number (10-15 digits, optional +country code)."
)


class User(AbstractUser):
    """
    Custom user. Login uses email OR phone + password.
    MPIN is a separate 4-6 digit quick-unlock hash, independent of the password.
    """
    email = models.EmailField(unique=True)
    phone = models.CharField(
        max_length=16, unique=True, null=True, blank=True, validators=[phone_validator]
    )
    mpin_hash = models.CharField(max_length=128, null=True, blank=True)
    daily_reminder_time = models.TimeField(null=True, blank=True, help_text="Preferred daily check-in reminder time")
    upi_id = models.CharField(
        max_length=100, null=True, blank=True,
        help_text="Self-reported UPI ID (e.g. name@bank), used to build settlement pay links. Not verified.",
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def set_mpin(self, raw_mpin: str):
        self.mpin_hash = make_password(raw_mpin)

    def check_mpin(self, raw_mpin: str) -> bool:
        if not self.mpin_hash:
            return False
        return check_password(raw_mpin, self.mpin_hash)

    def has_mpin(self) -> bool:
        return bool(self.mpin_hash)

    def __str__(self):
        return self.email
