from django.contrib import admin
from django.utils.html import format_html
from .models import Place, Hotel, EmergencyContact, FAQ


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):

    list_display = (
        "place_id",
        "place_name",
        "category",
        "activities",
        "province",
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
        "activities",
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