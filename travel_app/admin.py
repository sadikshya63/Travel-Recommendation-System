from django.contrib import admin
from django.utils.html import format_html
from .models import Place, Hotel, EmergencyContact, FAQ, RecommendationHistory,VisitorCounter, Hotspot
from django.contrib.admin import SimpleListFilter
class ActivityFilter(SimpleListFilter):
    title = "activities"
    parameter_name = "activity"

    def lookups(self, request, model_admin):
        activities = set()

        for place in Place.objects.all():
            if place.activities:
                for activity in place.activities.split(","):
                    activities.add(activity.strip())

        return sorted((a, a) for a in activities)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                activities__icontains=self.value()
            )
        return queryset
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
        "tourist_type",
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
    "category",
    ActivityFilter,
    "province",
    "budget_level",
    "tourist_type",
    "featured",
    "is_active",
)

    ordering = ("place_id",)

    def image_tag(self, obj):
        if obj.image:
            return format_html(
                '<img src="/static/images/{}" width="80" height="50" style="border-radius:5px;" />',
                obj.image
            )
        return "No Image"

    image_tag.short_description = "Image"


@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = (
        "hotel_name",
        "place",
        "price_range",
        "rating",
        "contact_number",
    )

    search_fields = (
        "hotel_name",
        "place__place_name",
        "address",
    )

    list_filter = (
        "place",
        "price_range",
    )

    def image_tag(self, obj):
        if obj.image:
            return format_html(
                '<img src="/static/images/{}" width="80" height="50" style="border-radius:5px;" />',
                obj.image
            )
        return "No Image"

    image_tag.short_description = "Image"


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


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = (
        "question",
    )

    search_fields = (
        "question",
        "answer",
    )
@admin.register(RecommendationHistory)
class RecommendationHistoryAdmin(admin.ModelAdmin):
    change_list_template = "admin/recommendation_history.html"
    list_display = (
        "category",
        "province",
        "budget_level",
        "tourist_type",
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
        "tourist_type",
    )
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        extra_context["domestic_count"] = RecommendationHistory.objects.filter(
            tourist_type="Domestic"
        ).count()

        extra_context["international_count"] = RecommendationHistory.objects.filter(
            tourist_type="International"
        ).count()

        return super().changelist_view(request, extra_context=extra_context)
    
@admin.register(VisitorCounter)
class VisitorCounterAdmin(admin.ModelAdmin):
    list_display = ("total_visits",)

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
                '<img src="/static/images/{}" width="80" height="50" style="border-radius:5px;" />',
                obj.image
            )
        return "No Image"

    image_tag.short_description = "Image"