"""One-shot CIA importer.

Usage:
    python manage.py import_cia <file.cia>
    python manage.py import_cia <directory>   # imports every *.cia inside

A thin wrapper over shopdeckdb.cia_import.import_cia for manual imports and for
migrating a batch of existing CIA files into Shopdeck.
"""

import os

from django.core.management.base import BaseCommand, CommandError

from shopdeckdb.cia_import import import_cia, CIAImportError


class Command(BaseCommand):
    help = "Import one CIA file (or every .cia in a directory) into Shopdeck."

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to a .cia file or a directory of them")
        parser.add_argument(
            "--hidden",
            action="store_true",
            help="Import titles as non-public (public=False) instead of live.",
        )

    def handle(self, *args, **options):
        path = options["path"]
        make_public = not options["hidden"]

        if os.path.isdir(path):
            cia_files = sorted(
                os.path.join(path, name)
                for name in os.listdir(path)
                if name.lower().endswith(".cia")
            )
            if not cia_files:
                raise CommandError("No .cia files found in {!r}".format(path))
        elif os.path.isfile(path):
            cia_files = [path]
        else:
            raise CommandError("Path does not exist: {!r}".format(path))

        failures = 0
        for cia_file in cia_files:
            try:
                title = import_cia(cia_file, make_public=make_public)
            except CIAImportError as exc:
                failures += 1
                self.stderr.write(self.style.ERROR(str(exc)))
                continue
            self.stdout.write(self.style.SUCCESS(
                "Imported {} -> {} (tid={}, version={})".format(
                    os.path.basename(cia_file), title.name, title.tid, title.version
                )
            ))

        if failures:
            raise CommandError("{} file(s) failed to import".format(failures))
