"""Long-running watcher that auto-imports CIA files dropped into the intake dir.

Usage:
    python manage.py watch_intake

Watches settings.INTAKE_DIR for new *.cia files. Each one is imported via
shopdeckdb.cia_import.import_cia and then moved into intake/processed/ on
success or intake/failed/ on error, so the watch root only ever holds files
still waiting to be processed. Files already present when the watcher starts
(e.g. dropped while it was down) are swept on startup.
"""

import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from shopdeckdb.cia_import import import_cia, CIAImportError

# How long a file's size must stay unchanged before we consider the copy
# finished (guards against importing a half-written file).
_STABLE_CHECKS = 3
_STABLE_INTERVAL = 1.0


def _is_cia(path):
    return os.path.isfile(path) and path.lower().endswith(".cia")


def _wait_until_stable(path):
    """Block until the file size stops changing (or the file disappears)."""
    last = -1
    stable = 0
    while stable < _STABLE_CHECKS:
        try:
            size = os.path.getsize(path)
        except OSError:
            return False
        if size == last:
            stable += 1
        else:
            stable = 0
            last = size
        time.sleep(_STABLE_INTERVAL)
    return True


class _CIAHandler(FileSystemEventHandler):
    def __init__(self, command):
        self.command = command

    def on_created(self, event):
        if not event.is_directory:
            self.command.process(event.src_path)

    def on_moved(self, event):
        # e.g. an atomic mv/rename into the watch dir
        if not event.is_directory:
            self.command.process(event.dest_path)


class Command(BaseCommand):
    help = "Watch the intake directory and auto-import dropped CIA files."

    def handle(self, *args, **options):
        self.intake_dir = settings.INTAKE_DIR
        self.processed_dir = os.path.join(self.intake_dir, "processed")
        self.failed_dir = os.path.join(self.intake_dir, "failed")
        for d in (self.intake_dir, self.processed_dir, self.failed_dir):
            os.makedirs(d, exist_ok=True)

        self.stdout.write("Watching {} for CIA files...".format(self.intake_dir))

        # Sweep anything already sitting in the intake root.
        for name in sorted(os.listdir(self.intake_dir)):
            candidate = os.path.join(self.intake_dir, name)
            if _is_cia(candidate):
                self.process(candidate)

        observer = Observer()
        observer.schedule(_CIAHandler(self), self.intake_dir, recursive=False)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write("Stopping watcher...")
        finally:
            observer.stop()
            observer.join()

    def process(self, path):
        if not _is_cia(path):
            return
        name = os.path.basename(path)
        if not _wait_until_stable(path):
            return  # file vanished or never settled; ignore

        self.stdout.write("Importing {}...".format(name))
        try:
            title = import_cia(path)
        except CIAImportError as exc:
            self.stderr.write(self.style.ERROR("Failed: {}".format(exc)))
            self._move(path, self.failed_dir)
            return
        except Exception as exc:  # never let one bad file kill the watcher
            self.stderr.write(self.style.ERROR("Unexpected error on {}: {}".format(name, exc)))
            self._move(path, self.failed_dir)
            return

        self.stdout.write(self.style.SUCCESS(
            "Imported {} (tid={}, version={})".format(title.name, title.tid, title.version)
        ))
        self._move(path, self.processed_dir)

    def _move(self, path, dest_dir):
        """Move path into dest_dir, avoiding clobbering an existing file."""
        name = os.path.basename(path)
        dest = os.path.join(dest_dir, name)
        if os.path.exists(dest):
            base, ext = os.path.splitext(name)
            dest = os.path.join(dest_dir, "{}-{}{}".format(base, int(time.time()), ext))
        try:
            os.replace(path, dest)
        except OSError as exc:
            self.stderr.write(self.style.WARNING("Could not move {}: {}".format(name, exc)))
