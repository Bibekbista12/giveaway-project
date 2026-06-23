import csv
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Count
from campaign.models import Participant, SpinSession


@staff_member_required
def stats_view(request):
    total_participants = Participant.objects.count()
    total_spins = SpinSession.objects.count()
    total_verified = Participant.objects.filter(verification_status="verified").count()
    total_unverified = Participant.objects.exclude(verification_status="verified").count()

    prize_distribution = (
        SpinSession.objects.values("prize__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    winners = (
        Participant.objects.filter(verification_status="verified")
        .select_related("spin_session__prize")
        .order_by("-created_at")
    )

    return render(request, "dashboard/stats.html", {
        "total_participants": total_participants,
        "total_spins": total_spins,
        "total_verified": total_verified,
        "total_unverified": total_unverified,
        "prize_distribution": prize_distribution,
        "winners": winners,
    })


@staff_member_required
def export_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="participants.csv"'
    writer = csv.writer(response)
    writer.writerow(["Name", "Mobile", "Email", "Prize", "Verification", "Submitted at"])

    participants = Participant.objects.select_related("spin_session__prize")
    for p in participants:
        writer.writerow([
            p.full_name, p.mobile_number, p.email,
            p.spin_session.prize.name, p.verification_status, p.created_at,
        ])
    return response