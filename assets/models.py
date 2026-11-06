from django.conf import settings
from django.db import models

# Create your models here.


class Asset(models.Model):
    CATEGORY_CHOICES = [
        ('laptop', 'Laptop'),
        ('desktop', 'Desktop'),
        ('printer', 'Printer'),
        ('router', 'Router / Switch'),
        ('phone', 'Phone / Tablet'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('repair', 'Under Repair'),
        ('retired', 'Retired'),
    ]

    name = models.CharField(max_length=100)
    asset_tag = models.CharField(max_length=50, unique=True)
    serial_number = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    assigned_to = models.CharField(max_length=100, blank=True)
    date_issued = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.asset_tag})"


class AssetHistory(models.Model):
    FIELD_CHOICES = [
        ("status", "Status"),
        ("assigned_to", "Assigned to"),
    ]

    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name="history",
    )
    field_changed = models.CharField(max_length=20, choices=FIELD_CHOICES)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_history",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at", "-pk"]

    def __str__(self):
        return f"{self.asset}: {self.get_field_changed_display()} changed"