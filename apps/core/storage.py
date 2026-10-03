"""Evidence storage: local disk unless a bucket is configured (PRS §7 / §14)."""
import os


def default_storage_backend() -> str:
    if os.environ.get("AWS_STORAGE_BUCKET_NAME", "").strip():
        return "storages.backends.s3boto3.S3Boto3Storage"
    return os.environ.get(
        "DEFAULT_FILE_STORAGE",
        "django.core.files.storage.FileSystemStorage",
    )


def static_storage_backend() -> str:
    debug = os.environ.get("DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
    if debug:
        return "django.contrib.staticfiles.storage.StaticFilesStorage"
    return "whitenoise.storage.CompressedStaticFilesStorage"
