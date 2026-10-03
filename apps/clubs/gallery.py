"""Published club gallery — verified photos and videos campus members can watch."""

from urllib.parse import urlparse

from apps.evidence.models import Evidence

GALLERY_TYPES = {
    Evidence.EvidenceType.IMAGE,
    Evidence.EvidenceType.VIDEO,
    Evidence.EvidenceType.POSTER,
    Evidence.EvidenceType.PROJECT_DOCUMENTATION,
}


def _file_url(item, request):
    if not item.file:
        return ""
    try:
        url = item.file.url
    except ValueError:
        return ""
    if request:
        return request.build_absolute_uri(url)
    return url


def looks_like_video(url: str) -> bool:
    u = (url or "").lower()
    return any(
        token in u
        for token in (
            "youtube.com",
            "youtu.be",
            "vimeo.com",
            ".mp4",
            ".webm",
            ".mov",
            "cc0-videos",
        )
    )


def looks_like_image(url: str) -> bool:
    path = urlparse(url or "").path.lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def serialize_gallery_item(item, request=None) -> dict:
    file_url = _file_url(item, request)
    url = (item.external_link or "").strip() or file_url
    is_video = item.evidence_type == Evidence.EvidenceType.VIDEO or looks_like_video(url)
    is_image = item.evidence_type == Evidence.EvidenceType.IMAGE or (
        not is_video and looks_like_image(url)
    )
    return {
        "id": str(item.id),
        "type": item.evidence_type,
        "caption": item.caption,
        "url": url,
        "file_url": file_url,
        "external_link": item.external_link,
        "is_video": is_video,
        "is_image": is_image,
        "activity_id": str(item.activity_id) if item.activity_id else None,
        "impact_project_id": str(item.impact_project_id) if item.impact_project_id else None,
    }


def club_gallery_items(club, request=None):
    items = (
        Evidence.objects.filter(club=club, status=Evidence.Status.VERIFIED)
        .filter(
            evidence_type__in=GALLERY_TYPES,
        )
        .select_related("activity", "impact_project")
        .order_by("-created_at")
    )
    payload = []
    for item in items:
        row = serialize_gallery_item(item, request)
        if row["url"]:
            payload.append(row)
    payload.sort(key=lambda row: (not row["is_video"], row["caption"]))
    return payload
