from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Q
from django.contrib.admin import SimpleListFilter

from .models import (
    Place,
    Hotel,
    EmergencyContact,
    FAQ,
    RecommendationHistory,
    VisitorCounter,
    Hotspot,
)


# =========================================================
# CUSTOM ADMIN TITLES & LIVE ANALYTICS DATA
# =========================================================

admin.site.site_header = "MeroYatra Administration"
admin.site.site_title = "MeroYatra Admin Portal"
admin.site.index_title = "Welcome to MeroYatra Analytics & Management Dashboard"


original_index = admin.site.index


def custom_admin_index(request, extra_context=None):
    extra_context = extra_context or {}

    # =====================================================
    # BASIC STATISTICS
    # =====================================================

    counter = VisitorCounter.objects.filter(pk=1).first()
    total_visits = counter.total_visits if counter else 0

    total_places = Place.objects.filter(is_active=True).count()
    total_hotels = Hotel.objects.count()
    total_searches = RecommendationHistory.objects.count()
    total_hotspots = Hotspot.objects.count()

    extra_context["total_visits"] = total_visits
    extra_context["total_places"] = total_places
    extra_context["total_hotels"] = total_hotels
    extra_context["total_searches"] = total_searches
    extra_context["total_hotspots"] = total_hotspots

    # =====================================================
    # CATEGORY COUNTS
    # =====================================================

    extra_context["nature_count"] = Place.objects.filter(
        category__icontains="Nature"
    ).count()

    extra_context["trekking_count"] = Place.objects.filter(
        category__icontains="Trekking"
    ).count()

    extra_context["cultural_count"] = Place.objects.filter(
        category__icontains="Cultural"
    ).count()

    extra_context["adventure_count"] = Place.objects.filter(
        category__icontains="Adventure"
    ).count()

    extra_context["wildlife_count"] = Place.objects.filter(
        category__icontains="Wildlife"
    ).count()

    # =====================================================
    # PROVINCE BREAKDOWN
    # =====================================================

    extra_context["bagmati_count"] = Place.objects.filter(
        province__icontains="Bagmati"
    ).count()

    extra_context["gandaki_count"] = Place.objects.filter(
        province__icontains="Gandaki"
    ).count()

    extra_context["koshi_count"] = Place.objects.filter(
        Q(province__icontains="Koshi")
        | Q(province__icontains="1")
    ).count()

    extra_context["lumbini_count"] = Place.objects.filter(
        province__icontains="Lumbini"
    ).count()

    extra_context["karnali_count"] = Place.objects.filter(
        Q(province__icontains="Karnali")
        | Q(province__icontains="Sudurpashchim")
    ).count()

    # =====================================================
    # DYNAMIC TOP SPOTS
    # =====================================================

    gandaki_spots = list(
        Place.objects.filter(
            province__icontains="Gandaki",
            is_active=True,
        ).values_list(
            "place_name",
            flat=True,
        )[:3]
    )

    bagmati_spots = list(
        Place.objects.filter(
            province__icontains="Bagmati",
            is_active=True,
        ).values_list(
            "place_name",
            flat=True,
        )[:3]
    )

    extra_context["gandaki_top_spots"] = (
        ", ".join(gandaki_spots)
        if gandaki_spots
        else "Pokhara, Annapurna, Mustang"
    )

    extra_context["bagmati_top_spots"] = (
        ", ".join(bagmati_spots)
        if bagmati_spots
        else "Kathmandu Valley, Nagarkot"
    )

    # =====================================================
    # RECENT RECOMMENDATION SEARCHES
    # =====================================================

    extra_context["recent_searches"] = (
        RecommendationHistory.objects
        .order_by("-searched_at")[:5]
    )

    return original_index(
        request,
        extra_context=extra_context,
    )


admin.site.index = custom_admin_index


# =========================================================
# CUSTOM FILTERS
# =========================================================

class ActivityFilter(SimpleListFilter):

    title = "activities"
    parameter_name = "activity"

    def lookups(self, request, model_admin):

        activities = set()

        for place in Place.objects.all():

            if place.activities:

                for activity in place.activities.split(","):

                    activity = activity.strip()

                    if activity:
                        activities.add(activity)

        return sorted(
            (activity, activity)
            for activity in activities
        )

    def queryset(self, request, queryset):

        if self.value():

            return queryset.filter(
                activities__icontains=self.value()
            )

        return queryset


class CategoryFilter(SimpleListFilter):

    title = "category"
    parameter_name = "category"

    def lookups(self, request, model_admin):

        return [
            ("Adventure", "Adventure"),
            ("Cultural", "Cultural"),
            ("Nature", "Nature"),
            ("Wildlife", "Wildlife"),
            ("Trekking", "Trekking"),
        ]

    def queryset(self, request, queryset):

        if self.value():

            return queryset.filter(
                category__icontains=self.value()
            )

        return queryset


# =========================================================
# PLACE ADMIN
# =========================================================

@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):

    list_display = (
        "place_id",
        "place_name",
        "city",
        "category",
        "activities",
        "province",
        "duration",
        "budget_level",
        "image_tag",
        "featured",
        "is_active",
    )

    search_fields = (
        "place_name",
        "category",
        "province",
        "activities",
    )

    list_filter = (
        CategoryFilter,
        ActivityFilter,
        "province",
        "budget_level",
        "featured",
        "is_active",
    )

    ordering = ("place_id",)

    def image_tag(self, obj):

        if obj.image:

            return format_html(
                '<img src="/static/images/{}" '
                'width="80" height="50" '
                'style="border-radius:5px;" />',
                obj.image,
            )

        return "No Image"

    image_tag.short_description = "Image"


# =========================================================
# EMERGENCY CONTACT ADMIN
# =========================================================

@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):

    list_display = (
        "title",
        "phone_number",
    )

    search_fields = (
        "title",
        "phone_number",
    )


# =========================================================
# FAQ ADMIN
# =========================================================

@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):

    list_display = (
        "question",
    )

    search_fields = (
        "question",
        "answer",
    )


# =========================================================
# RECOMMENDATION HISTORY ADMIN
# =========================================================

@admin.register(RecommendationHistory)
class RecommendationHistoryAdmin(admin.ModelAdmin):

    list_display = (
        "category",
        "activities",
        "province",
        "budget_level",
        "duration",
        "searched_at",
    )

    search_fields = (
        "category",
        "activities",
        "province",
    )

    list_filter = (
        "category",
        "province",
        "budget_level",
        "duration",
    )


# =========================================================
# VISITOR COUNTER ADMIN
# =========================================================

@admin.register(VisitorCounter)
class VisitorCounterAdmin(admin.ModelAdmin):

    list_display = (
        "total_visits",
    )

    readonly_fields = (
        "total_visits",
    )

    # Disable Add button
    def has_add_permission(self, request):
        return False

    # Disable Delete button
    def has_delete_permission(self, request, obj=None):
        return False


# =========================================================
# HOTSPOT ADMIN
# =========================================================

@admin.register(Hotspot)
class HotspotAdmin(admin.ModelAdmin):

    list_display = (
        "hotspot_name",
        "place",
        "category",
        "image_tag",
    )

    search_fields = (
        "hotspot_name",
        "category",
        "place__place_name",
    )

    list_filter = (
        "place",
        "category",
    )

    def image_tag(self, obj):

        if obj.image:

            return format_html(
                '<img src="/static/images/{}" '
                'width="80" height="50" '
                'style="border-radius:5px;" />',
                obj.image,
            )

        return "No Image"

    image_tag.short_description = "Image"