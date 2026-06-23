from django.contrib import admin
from .models import Prize, SpinSession, Participant, Document


@admin.register(Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "total_quantity", "remaining_quantity", "weight", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name",)


@admin.register(SpinSession)
class SpinSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "prize", "status", "ip_address", "spun_at", "expires_at")
    list_filter = ("status", "prize")
    search_fields = ("ip_address", "device_fingerprint")
    readonly_fields = ("id", "spun_at")


class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    readonly_fields = ("uploaded_at",)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "full_name", "mobile_number", "email", "get_prize",
        "verification_status", "created_at",
    )
    list_filter = ("verification_status", "mobile_verified", "email_verified")
    search_fields = ("full_name", "mobile_number", "email", "college_name")
    readonly_fields = ("created_at", "spin_session")
    inlines = [DocumentInline]
    actions = ["mark_verified", "mark_rejected"]

    def get_prize(self, obj):
        return obj.spin_session.prize.name
    get_prize.short_description = "Prize"

    @admin.action(description="Mark selected participants as verified")
    def mark_verified(self, request, queryset):
        from django.utils import timezone
        queryset.update(
            verification_status="verified",
            verified_by=request.user,
            verified_at=timezone.now(),
        )

    @admin.action(description="Mark selected participants as rejected")
    def mark_rejected(self, request, queryset):
        queryset.update(verification_status="rejected")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("participant", "doc_type", "is_required", "uploaded_at")
    list_filter = ("doc_type", "is_required")