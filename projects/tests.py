from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Project


User = get_user_model()


def create_user(email, name="Иван", surname="Иванов"):
    return User.objects.create_user(
        email=email,
        name=name,
        surname=surname,
        password="test-password-123",
    )


class ProjectTestCase(TestCase):
    def setUp(self):
        self.owner = create_user("owner@example.com", "Владелец")
        self.other_user = create_user("other@example.com", "Другой")
        self.project = Project.objects.create(
            owner=self.owner,
            name="Первый проект",
            description="Описание",
            github_url="https://github.com/owner/project",
        )
        self.project.participants.add(self.owner)


class ProjectListViewTests(ProjectTestCase):
    def test_root_redirects_to_project_list(self):
        response = self.client.get("/")
        self.assertRedirects(response, reverse("projects:project_list"))

    def test_project_list_is_paginated_by_twelve(self):
        for index in range(12):
            Project.objects.create(owner=self.owner, name=f"Проект {index}")

        first_page = self.client.get(reverse("projects:project_list"))
        second_page = self.client.get(reverse("projects:project_list"), {"page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context["projects"]), 12)
        self.assertEqual(len(second_page.context["projects"]), 1)

    def test_project_list_is_sorted_from_newest_to_oldest(self):
        newest = Project.objects.create(owner=self.owner, name="Новый проект")
        response = self.client.get(reverse("projects:project_list"))
        self.assertEqual(response.context["projects"][0], newest)


class ProjectCreateViewTests(ProjectTestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("projects:create_project"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("users:login"), response.url)

    def test_owner_is_set_and_added_to_participants(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:create_project"),
            {
                "name": "Новый проект",
                "description": "",
                "github_url": "https://github.com/owner/new-project",
                "status": Project.Status.OPEN,
            },
        )

        project = Project.objects.get(name="Новый проект")
        self.assertRedirects(response, reverse("projects:detail", args=(project.id,)))
        self.assertEqual(project.owner, self.owner)
        self.assertIn(self.owner, project.participants.all())
        self.assertEqual(project.description, "")

    def test_github_url_is_validated(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:create_project"),
            {
                "name": "Новый проект",
                "description": "",
                "github_url": "https://example.com/repository",
                "status": Project.Status.OPEN,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("github_url", response.context["form"].errors)
        self.assertFalse(Project.objects.filter(name="Новый проект").exists())


class ProjectEditViewTests(ProjectTestCase):
    def test_owner_can_edit_project(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:edit", args=(self.project.id,)),
            {
                "name": "Обновлённое название",
                "description": self.project.description,
                "github_url": self.project.github_url,
                "status": Project.Status.OPEN,
            },
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=(self.project.id,)),
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.name, "Обновлённое название")

    def test_other_user_cannot_edit_project(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse("projects:edit", args=(self.project.id,)))
        self.assertEqual(response.status_code, 403)


class ProjectActionTests(ProjectTestCase):
    def test_project_detail_sets_csrf_cookie_for_ajax_actions(self):
        response = self.client.get(reverse("projects:detail", args=(self.project.id,)))
        self.assertIn("csrftoken", response.cookies)

    def test_owner_can_complete_open_project(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("projects:complete", args=(self.project.id,)))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "project_status": Project.Status.CLOSED},
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.Status.CLOSED)

    def test_closed_project_cannot_be_completed_again(self):
        self.project.status = Project.Status.CLOSED
        self.project.save()
        self.client.force_login(self.owner)

        response = self.client.post(reverse("projects:complete", args=(self.project.id,)))
        self.assertEqual(response.status_code, 409)

    def test_other_user_cannot_complete_project(self):
        self.client.force_login(self.other_user)
        response = self.client.post(reverse("projects:complete", args=(self.project.id,)))
        self.assertEqual(response.status_code, 403)

    def test_participation_can_be_toggled(self):
        self.client.force_login(self.other_user)
        url = reverse("projects:toggle_participate", args=(self.project.id,))

        joined = self.client.post(url)
        self.assertEqual(joined.json(), {"status": "ok", "participant": True})
        self.assertIn(self.project, self.other_user.participated_projects.all())

        left = self.client.post(url)
        self.assertEqual(left.json(), {"status": "ok", "participant": False})
        self.assertNotIn(self.project, self.other_user.participated_projects.all())

    def test_owner_cannot_leave_own_project_through_toggle(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:toggle_participate", args=(self.project.id,)),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(self.owner, self.project.participants.all())


class ProjectModelTests(ProjectTestCase):
    def test_only_open_and_closed_statuses_are_available(self):
        self.assertEqual(
            Project.Status.values,
            [Project.Status.OPEN, Project.Status.CLOSED],
        )
        self.assertEqual(Project._meta.get_field("status").max_length, 6)
