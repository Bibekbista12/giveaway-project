import uuid
from datetime import timedelta
from django.db import transaction, models
from django.utils import timezone
from .models import Prize, SpinSession, Participant


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def can_spin(request):
    """
    Checkpoint 1: anonymous dedup, before any identity exists.
    Blocks repeat spins via cookie, device fingerprint, or IP within 24h.
    """
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
    """
    Checkpoint 2: real-identity dedup, at form submission.
    """
    return Participant.objects.filter(
        models.Q(mobile_number=mobile_number) | models.Q(email=email)
    ).exists()


def pick_weighted_prize():
    """
    Randomly selects an available prize, weighted by `weight`.
    Must be called inside a transaction.atomic() block by the caller,
    since it locks rows to prevent overselling.
    """
    import random

    prizes = list(
        Prize.objects.select_for_update().filter(is_active=True, remaining_quantity__gt=0)
    )
    if not prizes:
        return None

    total_weight = sum(p.weight for p in prizes)
    pick = random.uniform(0, total_weight)
    cumulative = 0
    for prize in prizes:
        cumulative += prize.weight
        if pick <= cumulative:
            return prize
    return prizes[-1]  # fallback, shouldn't normally hit this


def create_spin_session(request, prize):
    """
    Call inside the same transaction as pick_weighted_prize() + the
    remaining_quantity decrement.
    """
    cookie_id = request.COOKIES.get("giveaway_uid") or str(uuid.uuid4())
    return SpinSession.objects.create(
        prize=prize,
        session_cookie_id=cookie_id,
        device_fingerprint=request.POST.get("device_fingerprint", ""),
        ip_address=get_client_ip(request),
        expires_at=timezone.now() + timedelta(minutes=30),
    ), cookie_id


from django.core.exceptions import ValidationError

ALLOWED_DOC_EXTENSIONS = ["pdf", "jpg", "jpeg", "png"]
MAX_DOC_SIZE_MB = 5


def validate_uploaded_file(uploaded_file):
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_DOC_EXTENSIONS:
        raise ValidationError(f"Unsupported file type: .{ext}")
    if uploaded_file.size > MAX_DOC_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"File too large (max {MAX_DOC_SIZE_MB}MB)")