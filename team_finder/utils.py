from django.conf import settings


TEMPLATE_NAMES_VAR2 = {
    "projects/create-project.html": "projects/create_project.html",
    "projects/project-details.html": "projects/project_details.html",
    "users/user-details.html": "users/user_details.html",
}


def versioned_template(template_name):
    """Возвращает имя шаблона с учётом наименований в исходных наборах."""
    if settings.TASK_VERSION == 2:
        return TEMPLATE_NAMES_VAR2.get(template_name, template_name)
    return template_name
