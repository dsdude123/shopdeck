"""Reusable CIA -> Shopdeck import logic.

Given a path to a ``.cia`` file this module extracts the content (``.app``)
files and ``tmd.bin`` into ``cdn/<TITLE_ID>/`` (exactly the layout the Flask
CDN in ``cdn.py`` serves), extracts the SMDH icon into
``assetcdn/icons/<TITLE_ID>.png``, and creates/updates the matching ``Title``
database row (plus the ``publisher`` / ``genre`` / ``platform`` lookup rows it
depends on).

This is the shared engine behind the ``import_cia`` and ``watch_intake``
management commands. It reuses the parsing approach proven in the top-level
``cia-helper.py`` tool, but writes to the correct locations and wires up the
database so a dropped CIA becomes an immediately browsable, downloadable title.
"""

import io
import os
import struct

from django.conf import settings
from django.db import transaction

from pyctr.type.cia import CIAReader, CIASection

from shopdeckdb.models import Title, publisher, genre, platform

# Defaults for metadata that simply is not present in a CIA file.
DEFAULT_GENRE = "Homebrew"
DEFAULT_PLATFORM = "Nintendo 3DS"

# SMDH large icon: 48x48 RGB565, stored tiled, at offset 0x24C0 in the SMDH.
_SMDH_LARGE_ICON_OFFSET = 0x24C0
_LARGE_ICON_SIZE = 48


class CIAImportError(Exception):
    """Raised when a CIA cannot be imported (bad file, missing data, etc.)."""


def _cdn_dir():
    return os.path.join(settings.BASE_DIR, "cdn")


def _asset_icons_dir():
    return os.path.join(settings.BASE_DIR, "assetcdn", "icons")


def _tile_to_linear_large(raw):
    """Untile a 3DS 48x48 RGB565 icon into a linear RGB pixel list.

    3DS icons are stored in 8x8 tiles, and pixels within each tile follow
    Morton (Z-order) ordering. This reverses that swizzle. Returns a flat list
    of (r, g, b) tuples in row-major order.
    """
    size = _LARGE_ICON_SIZE
    pixels = [(0, 0, 0)] * (size * size)
    i = 0
    for ty in range(0, size, 8):
        for tx in range(0, size, 8):
            for p in range(64):
                x = (p & 1) | ((p >> 1) & 2) | ((p >> 2) & 4)
                y = ((p >> 1) & 1) | ((p >> 2) & 2) | ((p >> 3) & 4)
                (value,) = struct.unpack_from("<H", raw, i * 2)
                i += 1
                r = ((value >> 11) & 0x1F) * 255 // 31
                g = ((value >> 5) & 0x3F) * 255 // 63
                b = (value & 0x1F) * 255 // 31
                pixels[(ty + y) * size + (tx + x)] = (r, g, b)
    return pixels


def _extract_icon_png(app):
    """Return PNG bytes for the application's large SMDH icon, or None.

    Tries pyctr's own icon decoder first (its API has shifted across
    versions); falls back to manually decoding the raw SMDH icon bytes so this
    works regardless of the installed pyctr build.
    """
    from PIL import Image

    smdh = app.exefs.icon

    # Preferred path: let pyctr hand us a PIL image if it can.
    for attempt in (
        lambda: smdh.get_icon("large"),
        lambda: smdh.get_icon(),
        lambda: smdh.icon_large,
    ):
        try:
            image = attempt()
        except Exception:
            continue
        if image is not None:
            buf = io.BytesIO()
            image.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()

    # Fallback: decode the raw SMDH icon bytes ourselves.
    try:
        with app.exefs.open("icon") as f:
            raw = f.read()
        icon_data = raw[_SMDH_LARGE_ICON_OFFSET:_SMDH_LARGE_ICON_OFFSET
                        + _LARGE_ICON_SIZE * _LARGE_ICON_SIZE * 2]
        if len(icon_data) < _LARGE_ICON_SIZE * _LARGE_ICON_SIZE * 2:
            return None
        pixels = _tile_to_linear_large(icon_data)
        image = Image.new("RGB", (_LARGE_ICON_SIZE, _LARGE_ICON_SIZE))
        image.putdata(pixels)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def _extract_content_files(cia, tid):
    """Write tmd.bin and the .app content files into cdn/<tid>/.

    Mirrors the chunk-record iteration used by cia-helper.py, but writes to the
    CDN directory instead of the current working directory.
    """
    target = os.path.join(_cdn_dir(), tid)
    os.makedirs(target, exist_ok=True)

    chunks = [c for c in cia.tmd.chunk_records if c.cindex in cia.contents]

    section_for_index = {
        0: CIASection.Application,
        1: CIASection.Manual,
        2: CIASection.DownloadPlayChild,
    }
    for position, chunk in enumerate(chunks):
        section = section_for_index.get(position)
        if section is None:
            continue
        app_path = os.path.join(target, chunk.id.upper() + ".app")
        with open(app_path, "wb") as out:
            out.write(cia.open_raw_section(section).read())

    with open(os.path.join(target, "tmd.bin"), "wb") as out:
        out.write(cia.open_raw_section(CIASection.TitleMetadata).read())


@transaction.atomic
def _write_title(*, tid, name, desc, product_code, version, size,
                 publisher_name, make_public):
    """Create or update the Title row (and its lookup rows) for this CIA."""
    pub, _ = publisher.objects.get_or_create(publisher_name=publisher_name[:20])
    gen, _ = genre.objects.get_or_create(name=DEFAULT_GENRE)
    plat, _ = platform.objects.get_or_create(name=DEFAULT_PLATFORM)

    icon_url = "http://{}/assets/icons/{}.png".format(settings.ASSET_URL, tid)

    title, _ = Title.objects.update_or_create(
        tid=tid,
        defaults={
            "name": name[:25],
            "desc": desc,
            "product_code": product_code[:30],
            "version": version,
            "size": size,
            "publisher": pub,
            "genre": gen,
            "platform": plat,
            "price": 0,
            "public": make_public,
            "icon_url": icon_url,
            "thumbnail_url": icon_url,
            "banner_url": icon_url,
        },
    )
    return title


def import_cia(cia_path, *, make_public=True):
    """Import a single CIA file into Shopdeck.

    Extracts content files into cdn/<tid>/, the icon into assetcdn/icons/, and
    creates/updates the matching Title row. Returns the Title instance.

    Idempotent: re-importing the same CIA updates the existing title and files
    rather than creating duplicates. Raises CIAImportError on failure.
    """
    try:
        cia_cm = CIAReader(cia_path)
    except Exception as exc:  # InvalidCIAError, BootromNotFoundError, IO, ...
        raise CIAImportError("Could not open CIA {!r}: {}".format(cia_path, exc)) from exc

    with cia_cm as cia:
        try:
            tid = cia.tmd.title_id.upper()
            version = int(cia.tmd.title_version)
            size = int(cia.total_size)

            app = cia.contents[CIASection.Application]
            try:
                app_title = app.exefs.icon.get_app_title("English")
                name = (app_title.short_desc or "").strip()
                desc = (app_title.long_desc or "").strip()
                publisher_name = (app_title.publisher or "").strip()
            except Exception:
                name = desc = publisher_name = ""

            product_code = getattr(app, "product_code", "") or ""
            if not name:
                name = product_code or tid
            if not publisher_name:
                publisher_name = "Unknown"

            _extract_content_files(cia, tid)

            icon_png = _extract_icon_png(app)
            if icon_png is not None:
                os.makedirs(_asset_icons_dir(), exist_ok=True)
                with open(os.path.join(_asset_icons_dir(), tid + ".png"), "wb") as out:
                    out.write(icon_png)
        except CIAImportError:
            raise
        except Exception as exc:
            raise CIAImportError(
                "Failed to process CIA {!r}: {}".format(cia_path, exc)
            ) from exc

    return _write_title(
        tid=tid,
        name=name,
        desc=desc,
        product_code=product_code,
        version=version,
        size=size,
        publisher_name=publisher_name,
        make_public=make_public,
    )
