import django.db.models.functions.text
from django.db import migrations, models


def copy_user_skills(apps, schema_editor):
    User = apps.get_model("users", "User")
    UserSkill = apps.get_model("users", "UserSkill")
    through = User.skills.through
    relations = (
        through(user_id=user_skill.user_id, skill_id=user_skill.skill_id)
        for user_skill in UserSkill.objects.all().iterator()
    )
    through.objects.bulk_create(relations, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_alter_skill_options_alter_userskill_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="skills",
            field=models.ManyToManyField(
                blank=True,
                related_name="users",
                to="users.skill",
                verbose_name="Навыки",
            ),
        ),
        migrations.RunPython(copy_user_skills, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="userskill",
            name="unique_user_skill",
        ),
        migrations.RemoveField(
            model_name="userskill",
            name="skill",
        ),
        migrations.RemoveField(
            model_name="userskill",
            name="user",
        ),
        migrations.AddConstraint(
            model_name="skill",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("name"),
                name="unique_skill_name_case_insensitive",
            ),
        ),
        migrations.DeleteModel(
            name="UserSkill",
        ),
    ]
