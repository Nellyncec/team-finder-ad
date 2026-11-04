import json
from http import HTTPStatus

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from team_finder.utils import versioned_template

from .forms import LoginForm, ProfileEditForm, RegistrationForm
from .models import Skill


User = get_user_model()
SKILLS_AMOUNT = 10
USERS_PER_PAGE = 12


def get_page_object(queryset, request, per_page=USERS_PER_PAGE):
    paginator = Paginator(queryset, per_page)
    return paginator.get_page(request.GET.get("page"))


def skill_error(message, status):
    return JsonResponse({"error": message}, status=status)


@ensure_csrf_cookie
def user_profile(request, user_id):
    user = get_object_or_404(
        User.objects.prefetch_related("skills", "owned_projects__participants"),
        id=user_id,
    )
    return render(
        request,
        versioned_template("users/user-details.html"),
        {"user": user},
    )


def user_list(request):
    participants = User.objects.order_by("-date_joined", "-id")
    skill_name = request.GET.get("skill", "").strip()

    if settings.TASK_VERSION == 2 and skill_name:
        participants = participants.filter(skills__name=skill_name).distinct()

    page_obj = get_page_object(participants, request)
    all_skills = Skill.objects.order_by("name")
    context = {
        "participants": page_obj.object_list,
        "page_obj": page_obj,
        "active_skill": skill_name,
        "all_skills": all_skills,
        "skills": all_skills,
    }
    return render(request, "users/participants.html", context)


@login_required
@require_GET
def search_skills(request):
    query = request.GET.get("q", "").strip()
    skills = (
        Skill.objects.filter(name__istartswith=query)
        .order_by("name")
        .values("id", "name")[:SKILLS_AMOUNT]
    )
    return JsonResponse(list(skills), safe=False)


@login_required
@require_POST
def add_skill(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.user != user:
        return skill_error(
            "Нельзя изменять навыки другого пользователя.",
            HTTPStatus.FORBIDDEN,
        )

    if request.content_type == "application/json":
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return skill_error("Неверный формат данных.", HTTPStatus.BAD_REQUEST)
        if not isinstance(data, dict):
            return skill_error("Ожидался JSON-объект.", HTTPStatus.BAD_REQUEST)
    else:
        data = request.POST

    skill_id = data.get("skill_id")
    raw_name = data.get("name", "")
    name = raw_name.strip() if isinstance(raw_name, str) else ""
    if bool(skill_id) == bool(name):
        return skill_error(
            "Передайте ровно один параметр: skill_id или name.",
            HTTPStatus.BAD_REQUEST,
        )

    if skill_id:
        try:
            skill = Skill.objects.get(id=int(skill_id))
        except (TypeError, ValueError, OverflowError):
            return skill_error("Некорректный skill_id.", HTTPStatus.BAD_REQUEST)
        except Skill.DoesNotExist:
            return skill_error("Навык не найден.", HTTPStatus.NOT_FOUND)
        created = False
    else:
        if len(name) > Skill._meta.get_field("name").max_length:
            return skill_error("Название навыка слишком длинное.", HTTPStatus.BAD_REQUEST)
        skill, created = Skill.objects.get_or_create(
            name__iexact=name,
            defaults={"name": name},
        )

    added = not user.skills.filter(id=skill.id).exists()
    if added:
        user.skills.add(skill)

    return JsonResponse(
        {
            "skill_id": skill.id,
            "created": created,
            "added": added,
        },
    )


@login_required
@require_POST
def remove_skill(request, user_id, skill_id):
    user = get_object_or_404(User, id=user_id)
    if request.user != user:
        return skill_error(
            "Нельзя изменять навыки другого пользователя.",
            HTTPStatus.FORBIDDEN,
        )

    skill = get_object_or_404(Skill, id=skill_id)
    if not user.skills.filter(id=skill.id).exists():
        return skill_error("Этот навык не добавлен пользователю.", HTTPStatus.NOT_FOUND)

    user.skills.remove(skill)
    return JsonResponse({"status": "ok", "skill_id": skill.id, "removed": True})


@require_http_methods(["GET", "POST"])
def register_view(request):
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("users:login")
    return render(request, "users/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def login_view(request):
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            return redirect("projects:project_list")
        form.add_error(None, "Неверный имейл или пароль")
    return render(request, "users/login.html", {"form": form})


@require_http_methods(["GET"])
def logout_view(request):
    logout(request)
    return redirect("projects:project_list")


@login_required
@require_http_methods(["GET", "POST"])
def edit_profile_view(request):
    form = ProfileEditForm(
        request.POST or None,
        request.FILES or None,
        instance=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("users:profile", user_id=request.user.id)
    return render(request, "users/edit_profile.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def change_password_view(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, "Пароль успешно изменён")
        return redirect("users:profile", user_id=user.id)
    return render(request, "users/change_password.html", {"form": form})
