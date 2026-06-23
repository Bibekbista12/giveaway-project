import uuid
import random
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.db import transaction, models
from django.utils import timezone
from .models import Prize, SpinSession, Participant


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def can_spin(request):
    cookie_id = request.COOKIES.get("giveaway_uid")
    fingerprint = request.POST.get("device_fingerprint", "") or request.GET.get("device_fingerprint", "")
    ip = get_client_ip(request)

    query = models.Q(ip_address=ip, spun_at__gte=timezone.now() - timedelta(hours=24))
    if cookie_id:
        query |= models.Q(session_cookie_id=cookie_id)
    if fingerprint:
        query |= models.Q(device_fingerprint=fingerprint)

    existing = SpinSession.objects.filter(query).exclude(status="expired")
    return not existing.exists()


def is_duplicate_participant(mobile_number, email):
    return Participant.objects.filter(
        models.Q(mobile_number=mobile_number) | models.Q(email=email)
    ).exists()


def pick_weighted_outcome():
    """
    Picks an outcome (real prize OR a 'better luck next time' entry),
    weighted by `weight`. Only real prizes (is_prize=True) need
    remaining_quantity > 0; loss entries (is_prize=False) are unlimited.
    Must be called inside transaction.atomic() since it locks rows.
    """
    real_prizes = models.Q(is_prize=True, remaining_quantity__gt=0)
    loss_entries = models.Q(is_prize=False)

    entries = list(
        Prize.objects.select_for_update().filter(
            models.Q(is_active=True) & (real_prizes | loss_entries)
        )
    )
    if not entries:
        return None

    total_weight = sum(e.weight for e in entries)
    pick = random.uniform(0, total_weight)
    cumulative = 0
    for entry in entries:
        cumulative += entry.weight
        if pick <= cumulative:
            return entry
    return entries[-1]


def create_spin_session(request, outcome):
    cookie_id = request.COOKIES.get("giveaway_uid") or str(uuid.uuid4())
    status = "pending_form" if outcome.is_prize else "completed"
    return SpinSession.objects.create(
        prize=outcome,
        session_cookie_id=cookie_id,
        device_fingerprint=request.POST.get("device_fingerprint", ""),
        ip_address=get_client_ip(request),
        status=status,
        expires_at=timezone.now() + timedelta(minutes=30),
    ), cookie_id


ALLOWED_DOC_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]
MAX_DOC_SIZE_MB = 5


def validate_uploaded_file(uploaded_file):
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise ValidationError(f"Unsupported file type: .{ext}")
    if uploaded_file.size > MAX_DOC_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"File too large (max {MAX_DOC_SIZE_MB}MB)")