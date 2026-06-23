import json
from django.http import JsonResponse
from django.views import View
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
from .models import Prize, SpinSession, Document, Participant
from .forms import ParticipantForm
from .services import (
    can_spin, pick_weighted_outcome, create_spin_session,
    is_duplicate_participant, validate_uploaded_file,
)


class SpinView(View):
    def get(self, request):
        already_spun = not can_spin(request)
        entries = list(
            Prize.objects.filter(is_active=True).values("id", "name", "is_prize")
        )
        return render(request, "spin.html", {
            "already_spun": already_spun,
            "prizes_json": json.dumps(entries),
        })

    def post(self, request):
        if not can_spin(request):
            return JsonResponse({"error": "already_participated"}, status=403)

        with transaction.atomic():
            outcome = pick_weighted_outcome()
            if outcome is None:
                return JsonResponse({"error": "no_prizes_left"}, status=409)

            if outcome.is_prize:
                outcome.remaining_quantity -= 1
                outcome.save()

            session, cookie_id = create_spin_session(request, outcome)

        response = JsonResponse({
            "prize_id": outcome.id,
            "prize": outcome.name,
            "is_prize": outcome.is_prize,
            "spin_session_id": str(session.id),
        })
        response.set_cookie(
            "giveaway_uid", cookie_id,
            max_age=60 * 60 * 24 * 365,
            httponly=True,
            samesite="Lax",
        )
        return response


class RegisterView(View):
    def get(self, request, spin_session_id):
        session = get_object_or_404(SpinSession, id=spin_session_id, status="pending_form")
        form = ParticipantForm()
        return render(request, "register.html", {"form": form, "prize": session.prize})

    def post(self, request, spin_session_id):
        session = get_object_or_404(SpinSession, id=spin_session_id, status="pending_form")
        form = ParticipantForm(request.POST)

        mobile = request.POST.get("mobile_number")
        email = request.POST.get("email")
        if mobile and email and is_duplicate_participant(mobile, email):
            form.add_error(None, "This mobile number or email has already participated.")
            return render(request, "register.html", {"form": form, "prize": session.prize})

        uploaded_file = request.FILES.get("plus2_certificate")
        if not uploaded_file:
            form.add_error(None, "Please upload your +2 certificate or marksheet.")
            return render(request, "register.html", {"form": form, "prize": session.prize})

        try:
            validate_uploaded_file(uploaded_file)
        except ValidationError as e:
            form.add_error(None, str(e))
            return render(request, "register.html", {"form": form, "prize": session.prize})

        if form.is_valid():
            with transaction.atomic():
                participant = form.save(commit=False)
                participant.spin_session = session
                participant.save()
                Document.objects.create(
                    participant=participant,
                    file=uploaded_file,
                    doc_type="plus2_certificate",
                    is_required=True,
                )
                session.status = "completed"
                session.save()

            send_verification_email(participant)
            return redirect("registration_success")

        return render(request, "register.html", {"form": form, "prize": session.prize})


def send_verification_email(participant):
    verify_url = f"{settings.SITE_BASE_URL}/verify-email/{participant.email_verification_token}/"
    send_mail(
        subject="Confirm your email — Giveaway Campaign",
        message=f"Hi {participant.full_name},\n\nPlease confirm your email by clicking this link:\n{verify_url}\n\nIf you didn't request this, ignore this email.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[participant.email],
    )


class VerifyEmailView(View):
    def get(self, request, token):
        participant = get_object_or_404(Participant, email_verification_token=token)
        if not participant.email_verified:
            participant.email_verified = True
            participant.save()
        return render(request, "email_verified.html", {"participant": participant})


def registration_success(request):
    return render(request, "registration_success.html")