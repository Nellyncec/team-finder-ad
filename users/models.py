import random
from io import BytesIO
from uuid import uuid4

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.core.files import File
from django.db.models.functions import Lower
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from team_finder.validators import validate_github_url, validate_phone


AVATAR_SIZE = 256
AVATAR_COLORS = (
    "#DCEBDD",
    "#DDE7F2",
    "#EFE2D5",
    "#E8DFEF",
    "#DCEBEF",
    "#F0E5DA",
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, name, surname, password, **extra_fields):
        if not email:
            raise ValueError("Email обязателен.")
        if not name:
            raise ValueError("Имя обязательно.")
        if not surname:
            raise ValueError("Фамилия обязательна.")

        user = self.model(
            email=self.normalize_email(email).lower(),
            name=name,
            surname=surname,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, name, surname, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, name, surname, password, **extra_fields)

    def create_superuser(self, email, name, surname, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True.")

        return self._create_user(email, name, surname, password, **extra_fields)

    def get_by_natural_key(self, email):
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": email})


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField("Email", unique=True)
    name = models.CharField("Имя", max_length=124, default="")
    surname = models.CharField("Фамилия", max_length=124, default="")
    avatar = models.ImageField("Аватар", upload_to="users/avatars/", default="")
    about = models.TextField("О себе", max_length=256, blank=True, default="")
    phone = models.CharField(
        "Телефон",
        max_length=12,
        default="",
        validators=(validate_phone,),
    )
    github_url = models.URLField(
        "GitHub",
        blank=True,
        default="",
        validators=(validate_github_url,),
    )
    is_active = models.BooleanField("Активный", default=True)
    is_staff = models.BooleanField("Администратор", default=False)
    date_joined = models.DateTimeField("Дата регистрации", default=timezone.now)
    skills = models.ManyToManyField(
        "Skill",
        related_name="users",
        blank=True,
        verbose_name="Навыки",
    )

    groups = models.ManyToManyField(
        "auth.Group",
        related_name="custom_user_set",
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="custom_user_permission_set",
        blank=True,
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ("name", "surname")

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        constraints = (
            models.UniqueConstraint(
                Lower("email"),
                name="unique_user_email_case_insensitive",
            ),
            models.UniqueConstraint(
                fields=("phone",),
                condition=~models.Q(phone=""),
                name="unique_user_phone_nonempty",
            ),
        )

    def __str__(self):
        full_name = f"{self.name} {self.surname}".strip()
        return full_name or self.email

    def save(self, *args, **kwargs):
        self.email = self.email.lower()
        if self.phone.startswith("8"):
            self.phone = f"+7{self.phone[1:]}"
        if not self.avatar:
            self.avatar = self._generate_avatar()
        super().save(*args, **kwargs)

    def _generate_avatar(self):
        image = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), random.choice(AVATAR_COLORS))
        draw = ImageDraw.Draw(image)
        initial = (self.name[:1] or self.email[:1]).upper()

        try:
            font = ImageFont.truetype("DejaVuSans.ttf", 128)
        except OSError:
            font = ImageFont.load_default()

        left, top, right, bottom = draw.textbbox((0, 0), initial, font=font)
        position = (
            (AVATAR_SIZE - (right - left)) / 2 - left,
            (AVATAR_SIZE - (bottom - top)) / 2 - top,
        )
        draw.text(position, initial, fill="#263238", font=font)

        output = BytesIO()
        image.save(output, format="PNG")
        output.seek(0)
        return File(output, name=f"{uuid4().hex}.png")


class Skill(models.Model):
    name = models.CharField("Название навыка", max_length=124, unique=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "Навык"
        verbose_name_plural = "Навыки"
        constraints = (
            models.UniqueConstraint(
                Lower("name"),
                name="unique_skill_name_case_insensitive",
            ),
        )

    def __str__(self):
        return self.name
