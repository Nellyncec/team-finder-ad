from http import HTTPStatus

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from team_finder.utils import versioned_template

from .forms import ProjectForm
from .models import Project


PROJECTS_PER_PAGE = 12


def get_page_object(queryset, request, per_page=PROJECTS_PER_PAGE):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def project_list_view(request):
    projects = Project.objects.select_related("owner").order_by("-created_at", "-id")
    page_obj = get_page_object(projects, request)
    return render(
        request,
        "projects/project_list.html",
        {"projects": page_obj.object_list, "page_obj": page_obj},
    )


@login_required
@require_http_methods(["GET", "POST"])
def create_project_view(request):
    form = ProjectForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.owner = request.user
        project.save()
        project.participants.add(request.user)
        return redirect("projects:detail", project_id=project.id)
    return render(
        request,
        versioned_template("projects/create-project.html"),
        {"form": form, "is_edit": False},
    )


@ensure_csrf_cookie
def project_detail(request, project_id):
    project = get_object_or_404(
        Project.objects.select_related("owner").prefetch_related("participants"),
        id=project_id,
    )
    return render(
        request,
        versioned_template("projects/project-details.html"),
        {"project": project},
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit_project_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.owner != request.user:
        raise PermissionDenied

    form = ProjectForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("projects:detail", project_id=project.id)
    return render(
        request,
        versioned_template("projects/create-project.html"),
        {"form": form, "is_edit": True},
    )


@login_required
@require_http_methods(["POST"])
def complete_project_view(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    if project.owner != request.user:
        return JsonResponse(
            {"status": "error", "message": "Недостаточно прав."},
            status=HTTPStatus.FORBIDDEN,
        )
    if project.status != Project.Status.OPEN:
        return JsonResponse(
            {"status": "error", "message": "Проект уже завершён."},
            status=HTTPStatus.CONFLICT,
        )

    project.status = Project.Status.CLOSED
    project.save(update_fields=("status",))
    return JsonResponse({"status": "ok", "project_status": Project.Status.CLOSED})


@login_required
@require_http_methods(["POST"])
def toggle_participate(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    user = request.user

    if project.owner == user:
        return JsonResponse(
            {
                "status": "error",
                "message": "Автор уже является участником своего проекта.",
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    if project.participants.filter(id=user.id).exists():
        project.participants.remove(user)
        participant = False
    else:
        project.participants.add(user)
        participant = True

    return JsonResponse({"status": "ok", "participant": participant})
