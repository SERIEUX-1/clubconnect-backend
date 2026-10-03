from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import CampusCommitteeHandover, Institution, LicenceInquiry, SupportTicket, User


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ("short_name", "name", "kind", "is_active", "awards_enabled")
    list_filter = ("kind", "is_active", "awards_enabled")
    search_fields = ("name", "short_name", "slug")


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "role", "institution", "is_active", "is_staff")
    list_filter = ("role", "institution", "is_active", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("ClubConnect", {"fields": ("institution", "role", "student_id", "phone_number", "avatar", "preferred_language", "assigned_clubs")}),
    )


@admin.register(LicenceInquiry)
class LicenceInquiryAdmin(admin.ModelAdmin):
    list_display = ("institution_name", "contact_name", "contact_email", "status", "created_at")
    list_filter = ("status", "kind")
    search_fields = ("institution_name", "contact_name", "contact_email")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "email", "category", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("subject", "email", "name", "body")


@admin.register(CampusCommitteeHandover)
class CampusCommitteeHandoverAdmin(admin.ModelAdmin):
    list_display = ("institution", "outgoing", "incoming_email", "status", "created_at")
    list_filter = ("status",)
