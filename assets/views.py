import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import AssetForm
from .models import Asset, AssetHistory


def record_asset_changes(asset, old_status, old_assigned_to, changed_by):
    changes = []
    if old_status != asset.status:
        changes.append(AssetHistory(
            asset=asset,
            field_changed="status",
            old_value=old_status,
            new_value=asset.status,
            changed_by=changed_by,
        ))
    if old_assigned_to != asset.assigned_to:
        changes.append(AssetHistory(
            asset=asset,
            field_changed="assigned_to",
            old_value=old_assigned_to,
            new_value=asset.assigned_to,
            changed_by=changed_by,
        ))
    if changes:
        AssetHistory.objects.bulk_create(changes)


def filter_assets(request, assets):
    search_query = request.GET.get("q", "").strip()
    selected_category = request.GET.get("category", "")

    if search_query:
        assets = assets.filter(
            Q(name__icontains=search_query)
            | Q(asset_tag__icontains=search_query)
            | Q(serial_number__icontains=search_query)
            | Q(assigned_to__icontains=search_query)
        )

    category_values = {value for value, label in Asset.CATEGORY_CHOICES}
    if selected_category in category_values:
        assets = assets.filter(category=selected_category)
    else:
        selected_category = ""

    return assets, search_query, selected_category


def staff_required(view_func):
    @wraps(view_func)
    @login_required(login_url="login")
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped_view


@staff_required
def asset_list(request):
    assets, search_query, selected_category = filter_assets(
        request,
        Asset.objects.all(),
    )
    assets = assets.order_by("name")
    selected_status = request.GET.get("status", "")

    status_values = {value for value, label in Asset.STATUS_CHOICES}
    if selected_status in status_values:
        assets = assets.filter(status=selected_status)
    else:
        selected_status = ""

    paginator = Paginator(assets, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "assets/asset_list.html", {
        "assets": page_obj.object_list,
        "page_obj": page_obj,
        "query_string": query_params.urlencode(),
        "search_query": search_query,
        "selected_status": selected_status,
        "selected_category": selected_category,
        "status_choices": Asset.STATUS_CHOICES,
        "category_choices": Asset.CATEGORY_CHOICES,
    })


@staff_required
def asset_export(request):
    assets, _, _ = filter_assets(request, Asset.objects.all())
    selected_status = request.GET.get("status", "")
    valid_statuses = {value for value, label in Asset.STATUS_CHOICES}
    if selected_status in valid_statuses:
        assets = assets.filter(status=selected_status)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="assets.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Name",
        "Asset tag",
        "Serial number",
        "Category",
        "Status",
        "Assigned to",
        "Date issued",
        "Notes",
        "Created",
    ])
    for asset in assets.order_by("name"):
        writer.writerow([
            asset.name,
            asset.asset_tag,
            asset.serial_number,
            asset.get_category_display(),
            asset.get_status_display(),
            asset.assigned_to,
            asset.date_issued or "",
            asset.notes,
            asset.created_at.isoformat(),
        ])
    return response


@staff_required
def asset_report(request):
    status_sections = [
        {
            "value": value,
            "label": label,
            "assets": Asset.objects.filter(status=value).order_by("name"),
        }
        for value, label in Asset.STATUS_CHOICES
    ]
    return render(request, "assets/asset_report.html", {
        "status_sections": status_sections,
        "total_assets": Asset.objects.count(),
    })


@staff_required
def asset_create(request):
    if request.method == "POST":
        form = AssetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Asset added successfully.")
            return redirect("dashboard")
        messages.error(request, "Asset was not added. Please correct the errors below.")
    else:
        form = AssetForm()

    return render(request, "assets/asset_form.html", {
        "form": form,
        "page_title": "Add Asset",
        "submit_label": "Add Asset",
    })


@staff_required
def asset_detail(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    return render(request, "assets/asset_detail.html", {
        "asset": asset,
        "history_entries": asset.history.select_related("changed_by").all(),
    })


@staff_required
def asset_update(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == "POST":
        old_status = asset.status
        old_assigned_to = asset.assigned_to
        form = AssetForm(request.POST, instance=asset)
        if form.is_valid():
            with transaction.atomic():
                asset = form.save()
                record_asset_changes(
                    asset,
                    old_status,
                    old_assigned_to,
                    request.user,
                )
            messages.success(request, "Asset updated successfully.")
            return redirect("dashboard")
        messages.error(request, "Asset was not updated. Please correct the errors below.")
    else:
        form = AssetForm(instance=asset)

    return render(request, "assets/asset_form.html", {
        "form": form,
        "page_title": "Edit Asset",
        "submit_label": "Save Changes",
    })


@staff_required
@require_http_methods(["GET", "POST"])
def asset_delete(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == "POST":
        asset.delete()
        messages.success(request, "Asset deleted successfully.")
        return redirect("dashboard")
    return render(request, "assets/asset_confirm_delete.html", {"asset": asset})


@staff_required
@require_POST
def asset_status_update(request, pk):
    asset = get_object_or_404(Asset, pk=pk)
    return_to = request.POST.get("next", "")
    if not return_to or not url_has_allowed_host_and_scheme(
        return_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return_to = ""

    selected_status = request.POST.get("status", "")
    valid_statuses = {value for value, label in Asset.STATUS_CHOICES}
    if selected_status not in valid_statuses:
        messages.error(request, "Choose a valid asset status.")
        return redirect(return_to or "dashboard")

    old_status = asset.status
    with transaction.atomic():
        asset.status = selected_status
        asset.save(update_fields=["status"])
        record_asset_changes(
            asset,
            old_status,
            asset.assigned_to,
            request.user,
        )
    messages.success(request, f"{asset.name} status updated.")
    return redirect(return_to or "dashboard")


def staff_login(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_staff:
                login(request, user)
                next_url = request.POST.get("next") or request.GET.get("next", "")
                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure(),
                ):
                    return redirect(next_url)
                return redirect("dashboard")
            form.add_error(None, "Only staff accounts can use the asset tracker.")
    else:
        form = AuthenticationForm(request)

    return render(request, "assets/login.html", {
        "form": form,
        "next": request.GET.get("next", ""),
    })


@staff_required
@require_POST
def staff_logout(request):
    logout(request)
    return redirect("login")


@staff_required
def dashboard(request):
    if request.method == "POST":
        form = AssetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Asset added successfully.")
            return redirect("dashboard")
        messages.error(request, "Asset was not added. Please correct the errors below.")
    else:
        form = AssetForm()

    assets, search_query, selected_category = filter_assets(
        request,
        Asset.objects.all(),
    )
    status_totals = []
    for status, label in Asset.STATUS_CHOICES:
        status_assets = assets.filter(status=status).order_by("name")
        status_totals.append({
            "value": status,
            "label": label,
            "count": status_assets.count(),
            "assets": status_assets,
        })

    return render(request, "assets/dashboard.html", {
        "total_assets": assets.count(),
        "status_totals": status_totals,
        "recent_assets": assets.order_by("-created_at", "-pk")[:5],
        "asset_form": form,
        "search_query": search_query,
        "selected_category": selected_category,
        "category_choices": Asset.CATEGORY_CHOICES,
        "status_choices": Asset.STATUS_CHOICES,
    })


@staff_required
def custom_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


@staff_required
def custom_500(request):
    return render(request, "errors/500.html", status=500)
