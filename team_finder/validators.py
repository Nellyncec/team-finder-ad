import re
from urllib.parse import urlparse

from django.core.exceptions import ValidationError


PHONE_PATTERN = re.compile(r"(?:8\d{10}|\+7\d{10})")
ALLOWED_GITHUB_HOSTS = {"github.com", "www.github.com"}


def normalize_phone(value):
    value = (value or "").strip()
    if value.startswith("8"):
        return f"+7{value[1:]}"
    return value


def validate_phone(value):
    if not PHONE_PATTERN.fullmatch(value or ""):
        raise ValidationError(
            "Введите телефон в формате 8XXXXXXXXXX или +7XXXXXXXXXX."
        )


def validate_github_url(value):
    if not value:
        return

    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.hostname not in ALLOWED_GITHUB_HOSTS
    ):
        raise ValidationError("Ссылка должна вести на GitHub.")
