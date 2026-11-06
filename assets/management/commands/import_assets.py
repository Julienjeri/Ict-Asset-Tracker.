import csv
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from assets.models import Asset


class Command(BaseCommand):
    help = "Import new assets from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            nargs="?",
            type=Path,
            default=settings.BASE_DIR / "assets.csv",
            help="CSV file to import (defaults to assets.csv in the project folder).",
        )

    def handle(self, *args, **options):
        csv_file = options["csv_file"]
        if not csv_file.is_file():
            raise CommandError(f"CSV file not found: {csv_file}")

        required_columns = {
            "name",
            "asset_tag",
            "serial_number",
            "category",
            "status",
            "assigned_to",
            "date_issued",
            "notes",
        }
        category_values = {value for value, label in Asset.CATEGORY_CHOICES}
        status_values = {value for value, label in Asset.STATUS_CHOICES}
        rows = []
        seen_tags = set()

        try:
            with csv_file.open(encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                if not reader.fieldnames:
                    raise CommandError("The CSV file is empty or has no header row.")

                missing_columns = required_columns - set(reader.fieldnames)
                if missing_columns:
                    missing = ", ".join(sorted(missing_columns))
                    raise CommandError(f"CSV is missing required columns: {missing}")

                for line_number, row in enumerate(reader, start=2):
                    name = (row.get("name") or "").strip()
                    asset_tag = (row.get("asset_tag") or "").strip()
                    category = (row.get("category") or "").strip()
                    status = (row.get("status") or "").strip()
                    date_text = (row.get("date_issued") or "").strip()

                    if not name or not asset_tag:
                        raise CommandError(
                            f"Line {line_number}: name and asset_tag are required."
                        )
                    if category not in category_values:
                        raise CommandError(
                            f"Line {line_number}: invalid category '{category}'."
                        )
                    if status not in status_values:
                        raise CommandError(
                            f"Line {line_number}: invalid status '{status}'."
                        )
                    try:
                        date_issued = (
                            datetime.strptime(date_text, "%Y-%m-%d").date()
                            if date_text
                            else None
                        )
                    except ValueError as exc:
                        raise CommandError(
                            f"Line {line_number}: date_issued must use YYYY-MM-DD."
                        ) from exc

                    if asset_tag in seen_tags:
                        continue
                    seen_tags.add(asset_tag)
                    rows.append({
                        "name": name,
                        "asset_tag": asset_tag,
                        "serial_number": (row.get("serial_number") or "").strip(),
                        "category": category,
                        "status": status,
                        "assigned_to": (row.get("assigned_to") or "").strip(),
                        "date_issued": date_issued,
                        "notes": (row.get("notes") or "").strip(),
                    })
        except OSError as exc:
            raise CommandError(f"Could not read CSV file: {exc}") from exc
        except csv.Error as exc:
            raise CommandError(f"Could not parse CSV file: {exc}") from exc

        imported = 0
        skipped = 0
        with transaction.atomic():
            for row in rows:
                asset_tag = row["asset_tag"]
                if Asset.objects.filter(asset_tag=asset_tag).exists():
                    skipped += 1
                    continue
                Asset.objects.create(**row)
                imported += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: {imported} asset(s) imported, "
                f"{skipped} existing or duplicate asset tag(s) skipped."
            )
        )
