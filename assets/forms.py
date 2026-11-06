from django import forms

from .models import Asset


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = [
            "name",
            "asset_tag",
            "serial_number",
            "category",
            "status",
            "assigned_to",
            "date_issued",
            "notes",
        ]
        error_messages = {
            "asset_tag": {
                "unique": "An asset with this asset tag already exists.",
            },
        }
        widgets = {
            "date_issued": forms.DateInput(attrs={"type": "date"}),
        }
