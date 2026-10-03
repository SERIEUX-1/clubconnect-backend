import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Write a timestamped database backup under BACKUP_DIR (default var/backups)."

    def handle(self, *args, **options):
        dest = Path(getattr(settings, "BACKUP_DIR", settings.BASE_DIR / "var" / "backups"))
        dest.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        db = settings.DATABASES["default"]
        engine = db.get("ENGINE", "")
        if "sqlite" in engine:
            source = Path(db["NAME"])
            if not source.exists():
                raise CommandError(f"SQLite database not found: {source}")
            target = dest / f"clubconnect-{stamp}.sqlite3"
            shutil.copy2(source, target)
        elif "postgres" in engine or "postgis" in engine:
            target = dest / f"clubconnect-{stamp}.sql"
            env = os.environ.copy()
            if db.get("PASSWORD"):
                env["PGPASSWORD"] = db["PASSWORD"]
            cmd = [
                "pg_dump",
                "-h",
                db.get("HOST") or "localhost",
                "-p",
                str(db.get("PORT") or 5432),
                "-U",
                db.get("USER") or "postgres",
                "-d",
                db.get("NAME"),
                "-f",
                str(target),
            ]
            try:
                subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
            except FileNotFoundError as exc:
                raise CommandError("pg_dump is not installed on this machine.") from exc
            except subprocess.CalledProcessError as exc:
                raise CommandError(exc.stderr or str(exc)) from exc
        else:
            raise CommandError(f"No backup method for {engine}")
        self.stdout.write(self.style.SUCCESS(f"Backup written to {target}"))
