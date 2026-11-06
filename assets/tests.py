import csv

from django.contrib import admin
from django.test import TestCase
from django.test import override_settings

from django.contrib.auth import get_user_model
from django.urls import reverse

from .models import Asset, AssetHistory


class DashboardTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.staff_user = user_model.objects.create_user(
            username="staff",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(self.staff_user)

    def test_dashboard_shows_live_totals_and_recent_assets(self):
        Asset.objects.create(
            name="Office laptop",
            asset_tag="LAP-001",
            category="laptop",
            status="in_use",
            assigned_to="Alex",
        )
        Asset.objects.create(
            name="Office printer",
            asset_tag="PRN-001",
            category="printer",
            status="available",
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_assets"], 2)
        self.assertEqual(
            [(item["value"], item["count"]) for item in response.context["status_totals"]],
            [("available", 1), ("in_use", 1), ("repair", 0), ("retired", 0)],
        )
        self.assertContains(response, "Office laptop")
        self.assertContains(response, "Office printer")
        self.assertContains(response, 'href="#status-available"')
        self.assertContains(response, 'id="status-in_use"')
        self.assertContains(response, "No assets under repair.")
        self.assertContains(response, reverse("asset_create"))

    def test_dashboard_shows_empty_state_when_no_assets_exist(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_assets"], 0)
        self.assertContains(response, "No assets available.")

    def test_dashboard_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("dashboard"))

        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_asset_management_pages_require_staff(self):
        asset = Asset.objects.create(
            name="Office laptop",
            asset_tag="LAP-001",
            category="laptop",
        )
        non_staff = get_user_model().objects.create_user(
            username="regular-user",
            password="test-password",
            is_staff=False,
        )
        self.client.force_login(non_staff)

        pages = [
            ("get", reverse("dashboard")),
            ("get", reverse("asset_export")),
            ("get", reverse("asset_report")),
            ("get", reverse("asset_create")),
            ("get", reverse("asset_detail", args=[asset.pk])),
            ("get", reverse("asset_update", args=[asset.pk])),
            ("get", reverse("asset_delete", args=[asset.pk])),
            ("post", reverse("asset_status_update", args=[asset.pk])),
        ]
        for method, url in pages:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 403)

    def test_dashboard_search_and_category_filter(self):
        Asset.objects.create(
            name="Office laptop",
            asset_tag="LAP-001",
            category="laptop",
            assigned_to="Alex",
        )
        Asset.objects.create(
            name="Office printer",
            asset_tag="PRN-001",
            category="printer",
        )

        response = self.client.get(
            reverse("dashboard"),
            {"q": "Alex", "category": "laptop"},
        )

        self.assertEqual(response.context["total_assets"], 1)
        self.assertContains(response, "Office laptop")
        self.assertNotContains(response, "Office printer")

    def test_dashboard_adds_asset_and_reports_duplicate_tag(self):
        asset_data = {
            "name": "Office laptop",
            "asset_tag": "LAP-001",
            "serial_number": "SER-001",
            "category": "laptop",
            "status": "in_use",
            "assigned_to": "Alex",
            "date_issued": "",
            "notes": "Work laptop",
        }

        response = self.client.post(reverse("dashboard"), asset_data)

        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(Asset.objects.filter(asset_tag="LAP-001").exists())

        response = self.client.post(
            reverse("dashboard"),
            {**asset_data, "name": "Duplicate laptop"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An asset with this asset tag already exists.")
        self.assertEqual(Asset.objects.filter(asset_tag="LAP-001").count(), 1)

    def test_asset_create_page_validates_duplicate_tags(self):
        Asset.objects.create(
            name="Existing laptop",
            asset_tag="LAP-001",
            category="laptop",
        )
        asset_data = {
            "name": "New laptop",
            "asset_tag": "LAP-001",
            "serial_number": "",
            "category": "laptop",
            "status": "available",
            "assigned_to": "",
            "date_issued": "",
            "notes": "",
        }

        response = self.client.post(reverse("asset_create"), asset_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An asset with this asset tag already exists.")
        self.assertEqual(Asset.objects.count(), 1)

    def test_asset_edit_page_validates_duplicate_tags_and_allows_unchanged_tag(self):
        first_asset = Asset.objects.create(
            name="First laptop",
            asset_tag="LAP-001",
            category="laptop",
        )
        second_asset = Asset.objects.create(
            name="Second laptop",
            asset_tag="LAP-002",
            category="laptop",
        )
        edit_url = reverse("asset_update", args=[second_asset.pk])
        asset_data = {
            "name": "Updated laptop",
            "asset_tag": "LAP-001",
            "serial_number": "",
            "category": "laptop",
            "status": "available",
            "assigned_to": "",
            "date_issued": "",
            "notes": "",
        }

        response = self.client.post(edit_url, asset_data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An asset with this asset tag already exists.")
        second_asset.refresh_from_db()
        self.assertEqual(second_asset.asset_tag, "LAP-002")

        asset_data["asset_tag"] = "LAP-002"
        asset_data["status"] = "repair"
        asset_data["assigned_to"] = "Support Team"
        response = self.client.post(edit_url, asset_data)

        self.assertRedirects(response, reverse("dashboard"))
        first_asset.refresh_from_db()
        second_asset.refresh_from_db()
        self.assertEqual(first_asset.asset_tag, "LAP-001")
        self.assertEqual(second_asset.name, "Updated laptop")
        self.assertEqual(
            list(
                second_asset.history.order_by("field_changed").values_list(
                    "field_changed",
                    "old_value",
                    "new_value",
                )
            ),
            [
                ("assigned_to", "", "Support Team"),
                ("status", "available", "repair"),
            ],
        )

    def test_asset_status_can_be_changed_from_dashboard(self):
        asset = Asset.objects.create(
            name="Office laptop",
            asset_tag="LAP-001",
            category="laptop",
            status="in_use",
        )

        response = self.client.post(
            reverse("asset_status_update", args=[asset.pk]),
            {"status": "repair"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        asset.refresh_from_db()
        self.assertEqual(asset.status, "repair")
        history = asset.history.get(field_changed="status")
        self.assertEqual(history.old_value, "in_use")
        self.assertEqual(history.new_value, "repair")
        self.assertEqual(history.changed_by, self.staff_user)

        detail_response = self.client.get(reverse("asset_detail", args=[asset.pk]))
        self.assertContains(detail_response, "Under Repair")
        self.assertContains(detail_response, "in_use")
        self.assertContains(detail_response, "staff")

    def test_asset_delete_requires_confirmation(self):
        asset = Asset.objects.create(
            name="Office laptop",
            asset_tag="LAP-001",
            category="laptop",
        )

        response = self.client.get(reverse("asset_delete", args=[asset.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Are you sure?")
        self.assertTrue(Asset.objects.filter(pk=asset.pk).exists())

        response = self.client.put(reverse("asset_delete", args=[asset.pk]))

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Asset.objects.filter(pk=asset.pk).exists())

        response = self.client.post(reverse("asset_delete", args=[asset.pk]))

        self.assertRedirects(response, reverse("dashboard"))
        self.assertFalse(Asset.objects.filter(pk=asset.pk).exists())

    def test_asset_detail_and_edit_views_are_available_to_staff(self):
        asset = Asset.objects.create(
            name="Office laptop",
            asset_tag="LAP-001",
            category="laptop",
        )

        detail_response = self.client.get(reverse("asset_detail", args=[asset.pk]))
        edit_response = self.client.get(reverse("asset_update", args=[asset.pk]))

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, "LAP-001")
        self.assertContains(detail_response, "Record ID")
        self.assertContains(detail_response, "Serial number")
        self.assertContains(detail_response, "Created")
        self.assertEqual(edit_response.status_code, 200)


class AssetListPaginationTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="list-staff",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)

        for number in range(11):
            Asset.objects.create(
                name=f"Office laptop {number:02}",
                asset_tag=f"LAP-{number:03}",
                category="laptop",
                status="available" if number < 10 else "in_use",
                assigned_to="Finance" if number < 10 else "Reception",
            )

    def test_asset_list_shows_ten_assets_per_page(self):
        first_page = self.client.get(reverse("asset_list"))
        second_page = self.client.get(reverse("asset_list"), {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["assets"]), 10)
        self.assertEqual(first_page.context["page_obj"].paginator.count, 11)
        self.assertEqual(len(second_page.context["assets"]), 1)
        self.assertEqual(second_page.context["page_obj"].number, 2)

    def test_asset_list_filters_are_kept_while_paginating(self):
        Asset.objects.create(
            name="Office laptop extra",
            asset_tag="LAP-EXTRA",
            category="laptop",
            status="available",
            assigned_to="Finance",
        )
        response = self.client.get(
            reverse("asset_list"),
            {"q": "Finance", "status": "available", "category": "laptop", "page": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 11)
        self.assertEqual(response.context["search_query"], "Finance")
        self.assertEqual(response.context["selected_status"], "available")
        self.assertEqual(response.context["selected_category"], "laptop")
        self.assertContains(response, "status=available")

    def test_status_change_from_asset_list_returns_to_filtered_page(self):
        asset = Asset.objects.get(asset_tag="LAP-000")
        list_url = reverse("asset_list")
        filtered_url = f"{list_url}?q=Finance&status=available&category=laptop&page=1"

        response = self.client.post(
            reverse("asset_status_update", args=[asset.pk]),
            {"status": "repair", "next": filtered_url},
        )

        self.assertRedirects(response, filtered_url)
        asset.refresh_from_db()
        self.assertEqual(asset.status, "repair")

    def test_status_change_rejects_external_return_url(self):
        asset = Asset.objects.get(asset_tag="LAP-000")

        response = self.client.post(
            reverse("asset_status_update", args=[asset.pk]),
            {"status": "repair", "next": "https://example.com/"},
        )

        self.assertRedirects(response, reverse("dashboard"))


class AssetExportAndReportTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="report-staff",
            password="test-password",
            is_staff=True,
        )
        self.client.force_login(user)
        Asset.objects.create(
            name="Finance laptop",
            asset_tag="LAP-001",
            serial_number="SER-001",
            category="laptop",
            status="available",
            assigned_to="Finance",
        )
        Asset.objects.create(
            name="Reception printer",
            asset_tag="PRN-001",
            category="printer",
            status="repair",
            assigned_to="Reception",
        )

    def test_csv_export_applies_search_status_and_category_filters(self):
        response = self.client.get(
            reverse("asset_export"),
            {"q": "Finance", "status": "available", "category": "laptop"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn('filename="assets.csv"', response["Content-Disposition"])
        rows = list(csv.DictReader(response.content.decode("utf-8").splitlines()))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["Asset tag"], "LAP-001")
        self.assertEqual(rows[0]["Assigned to"], "Finance")

    def test_printable_report_groups_assets_by_status(self):
        response = self.client.get(reverse("asset_report"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_assets"], 2)
        self.assertContains(response, "Available (1)")
        self.assertContains(response, "Under Repair (1)")
        self.assertContains(response, "Finance laptop")
        self.assertContains(response, "Reception printer")

    @override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"])
    def test_custom_404_page_is_shown_to_staff(self):
        response = self.client.get("/page-that-does-not-exist/")

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Page not found", status_code=404)

    def test_asset_models_are_registered_in_admin(self):
        self.assertTrue(admin.site.is_registered(Asset))
        self.assertTrue(admin.site.is_registered(AssetHistory))
