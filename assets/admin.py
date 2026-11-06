from django.contrib import admin

from .models import Asset, AssetHistory


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "asset_tag",
        "category",
        "status",
        "assigned_to",
        "date_issued",
    )
    list_filter = ("status", "category")
    search_fields = ("name", "asset_tag", "serial_number", "assigned_to")


@admin.register(AssetHistory)
class AssetHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "asset",
        "field_changed",
        "old_value",
        "new_value",
        "changed_by",
        "changed_at",
    )
    list_filter = ("field_changed", "changed_at")
    search_fields = (
        "asset__name",
        "asset__asset_tag",
        "old_value",
        "new_value",
        "changed_by__username",
    )
    readonly_fields = ("changed_at",)
