import uuid
from django.db import models
from django.core.validators import RegexValidator


class Prize(models.Model):
    CATEGORY_CHOICES = [
        ("voucher", "Gift Voucher"),
        ("food", "Food Coupon"),
        ("drink", "Free Drink"),
        ("movie", "Movie Ticket"),
        ("concert", "Concert Ticket"),
        ("other", "Other"),
    ]
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    total_quantity = models.PositiveIntegerField()
    remaining_quantity = models.PositiveIntegerField()
    weight = models.PositiveIntegerField(
        default=1, help_text="Relative odds of being selected on the wheel"
    )
    is_active = models.BooleanField(default=True)
    is_prize = models.BooleanField(default=True, help_text="Uncheck for 'better luck next time' segments")

    image = models.ImageField(upload_to="prizes/", blank=True, null=True)

    def is_available(self):
        return self.is_active and self.remaining_quantity > 0

    def __str__(self):
        return self.name


class SpinSession(models.Model):
    STATUS_CHOICES = [
        ("pending_form", "Waiting for form"),
        ("completed", "Form submitted"),
        ("expired", "Expired / abandoned"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prize = models.ForeignKey(Prize, on_delete=models.PROTECT)

    session_cookie_id = models.CharField(max_length=64, db_index=True)
    device_fingerprint = models.CharField(max_length=128, db_index=True, blank=True)
    ip_address = models.GenericIPAddressField(db_index=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_form")
    spun_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [
            models.Index(fields=["ip_address", "spun_at"]),
            models.Index(fields=["device_fingerprint"]),
        ]

    def __str__(self):
        return f"{self.id} - {self.prize.name} ({self.status})"


phone_validator = RegexValidator(r"^\+?\d{7,15}$", "Enter a valid mobile number.")


class Participant(models.Model):
    VERIFICATION_CHOICES = [
        ("pending", "Pending review"),
        ("verified", "Verified"),
        ("rejected", "Rejected"),
    ]
    spin_session = models.OneToOneField(SpinSession, on_delete=models.CASCADE, related_name="participant")

    full_name = models.CharField(max_length=150)
    mobile_number = models.CharField(max_length=15, unique=True, validators=[phone_validator])
    email = models.EmailField(unique=True)
    date_of_birth = models.DateField()
    address = models.TextField()
    college_name = models.CharField(max_length=200)
    plus_two_completion_year = models.PositiveIntegerField()

    mobile_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    verification_status = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default="pending")
    verified_by = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def prize_is_valid(self):
        return (
            self.verification_status == "verified"
            and self.documents.filter(is_required=True).exists()
        )

    def __str__(self):
        return f"{self.full_name} ({self.email})"


def document_upload_path(instance, filename):
    return f"documents/{instance.participant_id}/{filename}"


class Document(models.Model):
    DOC_TYPE_CHOICES = [
        ("plus2_certificate", "+2 Pass Certificate / Marksheet"),
        ("other", "Additional document"),
    ]
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to=document_upload_path)
    is_required = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.doc_type} - {self.participant.full_name}"