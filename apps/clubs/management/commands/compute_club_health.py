from django.core.management.base import BaseCommand

from apps.clubs.health import compute_for_all_clubs


class Command(BaseCommand):
    """
    Run nightly (e.g. via Celery Beat or a plain cron entry calling
    `manage.py compute_club_health`) to refresh every recognized club's
    Club Health snapshot. Deliberately idempotent for a given date --
    running it twice in one day just updates the same row.
    """

    help = "Recompute Club Health snapshots for every recognized club."

    def handle(self, *args, **options):
        count = compute_for_all_clubs()
        self.stdout.write(self.style.SUCCESS(f"Computed Club Health for {count} club(s)."))
