from django.urls import path

from . import views


app_name = "projects"

urlpatterns = [
    path("list/", views.project_list_view, name="project_list"),
    path("create-project/", views.create_project_view, name="create_project"),
    path("<int:project_id>/edit/", views.edit_project_view, name="edit"),
    path("<int:project_id>/complete/", views.complete_project_view, name="complete"),
    path(
        "<int:project_id>/toggle-participate/",
        views.toggle_participate,
        name="toggle_participate",
    ),
    path("<int:project_id>/", views.project_detail, name="detail"),
]
