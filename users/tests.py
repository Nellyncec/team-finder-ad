import json
from unittest import skipUnless

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import ProfileEditForm
from .models import Skill


User = get_user_model()


def create_user(email="user@example.com", name="Иван", surname="Иванов", **extra):
    return User.objects.create_user(
        email=email,
        name=name,
        surname=surname,
        password="test-password-123",
        **extra,
    )


class UserModelTests(TestCase):
    def test_user_is_created_with_email_login_and_generated_avatar(self):
        user = create_user(email="USER@EXAMPLE.COM")

        self.assertEqual(user.email, "user@example.com")
        self.assertEqual(User.USERNAME_FIELD, "email")
        self.assertFalse(hasattr(user, "username"))
        self.assertTrue(user.avatar)
        self.assertTrue(user.avatar.name.endswith(".png"))
        with user.avatar.open("rb") as avatar:
            self.assertEqual(avatar.read(8), b"\x89PNG\r\n\x1a\n")
        self.assertTrue(user.check_password("test-password-123"))

    def test_superuser_has_required_permissions(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            name="Админ",
            surname="Админов",
            password="test-password-123",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_active)

    def test_phone_is_normalized_on_save(self):
        user = create_user(phone="89991112233")
        self.assertEqual(user.phone, "+79991112233")


class ProfileFormTests(TestCase):
    def setUp(self):
        self.user = create_user()

    def form(self, **overrides):
        data = {
            "name": self.user.name,
            "surname": self.user.surname,
            "about": "О себе",
            "phone": "89991112233",
            "github_url": "https://github.com/example",
        }
        data.update(overrides)
        return ProfileEditForm(data=data, instance=self.user)

    def test_phone_is_normalized(self):
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "+79991112233")

    def test_phone_format_is_validated(self):
        form = self.form(phone="+7 (999) 111-22-33")
        self.assertFalse(form.is_valid())
        self.assertIn("phone", form.errors)

    def test_equivalent_phone_numbers_cannot_belong_to_different_users(self):
        create_user(email="other@example.com", phone="+79991112233")
        form = self.form(phone="89991112233")

        self.assertFalse(form.is_valid())
        self.assertIn("уже используется", str(form.errors["phone"]))

    def test_current_user_can_keep_phone(self):
        self.user.phone = "+79991112233"
        self.user.save()
        self.assertTrue(self.form(phone="89991112233").is_valid())

    def test_existing_avatar_does_not_need_reupload(self):
        self.user.avatar = "users/avatars/alice.png"
        self.user.save()
        form = self.form()
        self.assertTrue(form.is_valid(), form.errors)

    def test_github_host_is_validated(self):
        for url in ("https://example.com/user", "https://github.com.evil.example/user"):
            with self.subTest(url=url):
                form = self.form(github_url=url)
                self.assertFalse(form.is_valid())
                self.assertIn("github_url", form.errors)


class AuthenticationViewTests(TestCase):
    def test_registration_creates_user_and_redirects_to_login(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "name": "Анна",
                "surname": "Смирнова",
                "email": "anna@example.com",
                "password": "test-password-123",
            },
        )

        self.assertRedirects(response, reverse("users:login"))
        user = User.objects.get(email="anna@example.com")
        self.assertTrue(user.avatar)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
                "OPTIONS": {"min_length": 10},
            },
        ],
    )
    def test_registration_uses_configured_password_validators(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "name": "Анна",
                "surname": "Смирнова",
                "email": "anna@example.com",
                "password": "short",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("password", response.context["form"].errors)
        self.assertFalse(User.objects.filter(email="anna@example.com").exists())

    def test_login_uses_email(self):
        user = create_user()
        response = self.client.post(
            reverse("users:login"),
            {"email": user.email.upper(), "password": "test-password-123"},
        )

        self.assertRedirects(response, reverse("projects:project_list"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.id)

    def test_invalid_login_adds_form_error(self):
        create_user()
        response = self.client.post(
            reverse("users:login"),
            {"email": "user@example.com", "password": "wrong"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Неверный имейл или пароль", response.context["form"].non_field_errors())

    def test_logout_redirects_to_project_list(self):
        self.client.force_login(create_user())
        response = self.client.get(reverse("users:logout"))

        self.assertRedirects(response, reverse("projects:project_list"))
        self.assertNotIn("_auth_user_id", self.client.session)


class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.client.force_login(self.user)

    def test_profile_edit_updates_user(self):
        response = self.client.post(
            reverse("users:edit_profile"),
            {
                "name": "Пётр",
                "surname": "Петров",
                "about": "Backend",
                "phone": "89991112233",
                "github_url": "https://github.com/petr",
            },
        )

        self.assertRedirects(response, reverse("users:profile", args=(self.user.id,)))
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, "Пётр")
        self.assertEqual(self.user.phone, "+79991112233")

    def test_password_change_keeps_session_and_accepts_new_password(self):
        response = self.client.post(
            reverse("users:change_password"),
            {
                "old_password": "test-password-123",
                "new_password1": "new-strong-password-456",
                "new_password2": "new-strong-password-456",
            },
        )

        self.assertRedirects(response, reverse("users:profile", args=(self.user.id,)))
        self.assertEqual(
            self.client.get(reverse("users:edit_profile")).status_code,
            200,
        )
        self.client.logout()
        self.assertTrue(
            self.client.login(
                username=self.user.email,
                password="new-strong-password-456",
            ),
        )


class UserListTests(TestCase):
    def test_user_list_is_paginated_by_twelve(self):
        for index in range(13):
            create_user(email=f"user{index}@example.com")

        first_page = self.client.get(reverse("users:user_list"))
        second_page = self.client.get(reverse("users:user_list"), {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["participants"]), 12)
        self.assertEqual(len(second_page.context["participants"]), 1)


@skipUnless(settings.TASK_VERSION == 2, "Тесты варианта 2")
class SkillModelTests(TestCase):
    def test_user_and_skill_are_linked_by_required_related_names(self):
        user = create_user()
        skill = Skill.objects.create(name="Python")

        user.skills.add(skill)

        self.assertIn(skill, user.skills.all())
        self.assertIn(user, skill.users.all())


@skipUnless(settings.TASK_VERSION == 2, "Тесты варианта 2")
class SkillSearchViewTests(TestCase):
    def setUp(self):
        self.client.force_login(create_user())

    def test_search_returns_json_list_sorted_and_limited_to_ten(self):
        for index in range(12):
            Skill.objects.create(name=f"Python {index:02}")
        Skill.objects.create(name="Django")

        response = self.client.get(reverse("users:search_skills"), {"q": "py"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 10)
        self.assertEqual(
            [item["name"] for item in data],
            sorted(item["name"] for item in data),
        )
        self.assertEqual(set(data[0]), {"id", "name"})

    def test_search_matches_only_beginning_of_name(self):
        Skill.objects.create(name="Django")
        response = self.client.get(reverse("users:search_skills"), {"q": "ang"})
        self.assertEqual(response.json(), [])


@skipUnless(settings.TASK_VERSION == 2, "Тесты варианта 2")
class SkillAddViewTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.other_user = create_user(email="other@example.com")
        self.skill = Skill.objects.create(name="Python")
        self.client.force_login(self.user)
        self.url = reverse("users:add_skill", args=(self.user.id,))

    def test_existing_skill_is_added_by_id(self):
        response = self.client.post(self.url, {"skill_id": self.skill.id})

        self.assertEqual(
            response.json(),
            {"skill_id": self.skill.id, "created": False, "added": True},
        )
        self.assertIn(self.skill, self.user.skills.all())

    def test_duplicate_relation_returns_added_false(self):
        self.user.skills.add(self.skill)
        response = self.client.post(self.url, {"skill_id": self.skill.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"skill_id": self.skill.id, "created": False, "added": False},
        )

    def test_new_skill_is_created_by_name(self):
        response = self.client.post(self.url, {"name": "Django"})

        skill = Skill.objects.get(name="Django")
        self.assertEqual(
            response.json(),
            {"skill_id": skill.id, "created": True, "added": True},
        )
        self.assertIn(skill, self.user.skills.all())

    def test_existing_name_is_reused_case_insensitively(self):
        response = self.client.post(self.url, {"name": "python"})

        self.assertEqual(
            response.json(),
            {"skill_id": self.skill.id, "created": False, "added": True},
        )
        self.assertEqual(Skill.objects.count(), 1)

    def test_json_body_is_supported(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"name": "React"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["created"])

    def test_invalid_parameters_return_bad_request(self):
        for data in (
            {},
            {"skill_id": self.skill.id, "name": "Django"},
            {"skill_id": "invalid"},
            {"name": "x" * 125},
        ):
            with self.subTest(data=data):
                response = self.client.post(self.url, data)
                self.assertEqual(response.status_code, 400)

    def test_non_object_json_and_overflow_return_bad_request(self):
        for body in ("null", "[]", '"text"', "123"):
            with self.subTest(body=body):
                response = self.client.post(
                    self.url,
                    data=body,
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)

        overflow = self.client.post(
            self.url,
            data='{"skill_id": 1e999}',
            content_type="application/json",
        )
        self.assertEqual(overflow.status_code, 400)

    def test_missing_skill_returns_not_found(self):
        response = self.client.post(self.url, {"skill_id": 99999})
        self.assertEqual(response.status_code, 404)

    def test_other_profile_is_forbidden(self):
        url = reverse("users:add_skill", args=(self.other_user.id,))
        response = self.client.post(url, {"skill_id": self.skill.id})
        self.assertEqual(response.status_code, 403)


@skipUnless(settings.TASK_VERSION == 2, "Тесты варианта 2")
class SkillRemoveViewTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.other_user = create_user(email="other@example.com")
        self.skill = Skill.objects.create(name="Python")
        self.user.skills.add(self.skill)
        self.client.force_login(self.user)
        self.url = reverse("users:remove_skill", args=(self.user.id, self.skill.id))

    def test_skill_is_unlinked_but_not_deleted(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "skill_id": self.skill.id, "removed": True},
        )
        self.assertNotIn(self.skill, self.user.skills.all())
        self.assertTrue(Skill.objects.filter(id=self.skill.id).exists())

    def test_unlinked_skill_returns_not_found(self):
        self.user.skills.remove(self.skill)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_other_profile_is_forbidden(self):
        url = reverse("users:remove_skill", args=(self.other_user.id, self.skill.id))
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)


@skipUnless(settings.TASK_VERSION == 2, "Тесты варианта 2")
class SkillFilterAndTemplateTests(TestCase):
    def setUp(self):
        self.python_user = create_user(email="python@example.com")
        self.django_user = create_user(email="django@example.com")
        self.python = Skill.objects.create(name="Python")
        self.django = Skill.objects.create(name="Django")
        self.python_user.skills.add(self.python)
        self.django_user.skills.add(self.django)

    def test_user_list_filters_by_exact_skill_name(self):
        response = self.client.get(reverse("users:user_list"), {"skill": "Python"})

        self.assertEqual(list(response.context["participants"]), [self.python_user])
        self.assertEqual(response.context["active_skill"], "Python")
        self.assertCountEqual(response.context["all_skills"], [self.python, self.django])

        wrong_case = self.client.get(reverse("users:user_list"), {"skill": "python"})
        self.assertEqual(list(wrong_case.context["participants"]), [])
        self.assertContains(response, "Фильтр по навыку")

    def test_special_characters_in_skill_name_are_encoded_and_filterable(self):
        skill = Skill.objects.create(name="C++")
        self.python_user.skills.add(skill)

        response = self.client.get(reverse("users:user_list"))
        self.assertContains(response, "?skill=C%2B%2B")
        filtered = self.client.get(reverse("users:user_list"), {"skill": "C++"})
        self.assertEqual(list(filtered.context["participants"]), [self.python_user])

    def test_owner_sees_controls_and_guest_sees_read_only_skills(self):
        url = reverse("users:profile", args=(self.python_user.id,))
        guest_response = self.client.get(url)
        self.assertContains(guest_response, "Python")
        self.assertNotContains(guest_response, "show-skill-form-btn")
        self.assertNotContains(guest_response, "remove-skill-btn")

        self.client.force_login(self.python_user)
        owner_response = self.client.get(url)
        self.assertContains(owner_response, "show-skill-form-btn")
        self.assertContains(owner_response, "remove-skill-btn")
        self.assertIn("csrftoken", owner_response.cookies)
