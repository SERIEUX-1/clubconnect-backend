from django.core.management.base import BaseCommand

from apps.notifications.reminders import send_deadline_reminders


class Command(BaseCommand):
    help = (
        "Email club leaders whose monthly report is due in 3 days or today. "
        "Run daily from cron, e.g. 7:00 in the campus timezone."
    )

    def handle(self, *args, **options):
        sent = send_deadline_reminders()
        self.stdout.write(self.style.SUCCESS(f"Sent {sent} deadline emails."))
