from django.contrib import admin
from django.utils.html import format_html
from .models import Place


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
    )

    search_fields = (
        "place_name",
        "category",
        "province",
        "activities",
    )

    list_filter = (
        "category",
        "province",
        "budget_level",
        "tourist_type",
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