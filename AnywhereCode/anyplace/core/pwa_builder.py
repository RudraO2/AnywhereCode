
"""
Make a generated web project installable as a real app.

The native-APK path costs an Expo account, a signing keystore and 8-20 minutes
of cloud build time. For a large share of what people actually ask for — a
habit tracker, a tip calculator, a quiz — a Progressive Web App is a genuinely
good app: Chrome on Android installs it as a WebAPK with its own home-screen
icon, its own task-switcher entry and no browser chrome. It works offline via a
service worker, and deploying it to GitHub Pages is free and takes seconds.

So this is the default delivery path, and EAS becomes the upgrade for ideas
that truly need native device access.

Three things are required before Chrome will offer to install a site:
a web app manifest with 192px and 512px icons, a registered service worker
with a fetch handler, and HTTPS (which GitHub Pages provides).

Icons are generated here as PNGs written by hand — no Pillow, because a native
imaging dependency would break the Termux install this project depends on.
"""

import binascii
import hashlib
import json
import re
import struct
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# A compact 5x7 bitmap font, enough to stamp one initial onto an icon.
# Each glyph is 7 rows of 5 bits, most significant bit leftmost.
_FONT_5X7 = {
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    "0": (0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E),
    "1": (0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "2": (0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F),
    "3": (0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E),
    "4": (0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02),
    "5": (0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E),
    "6": (0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E),
    "7": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08),
    "8": (0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E),
    "9": (0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C),
}

# Pleasant, accessible backgrounds — picked deterministically per app name so
# an icon stays stable across rebuilds instead of flickering colour.
_PALETTE = [
    (37, 99, 235),    # blue
    (219, 39, 119),   # pink
    (5, 150, 105),    # emerald
    (217, 119, 6),    # amber
    (124, 58, 237),   # violet
    (13, 148, 136),   # teal
    (220, 38, 38),    # red
    (79, 70, 229),    # indigo
]


def theme_colour(app_name: str) -> Tuple[int, int, int]:
    """Deterministically pick a brand colour from the app name."""
    digest = hashlib.sha256(app_name.encode("utf-8")).digest()
    return _PALETTE[digest[0] % len(_PALETTE)]


def _rgb_hex(colour: Tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*colour)


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    """Assemble one PNG chunk: length, tag, payload, CRC."""
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", binascii.crc32(tag + payload) & 0xFFFFFFFF)
    )


def render_icon_png(size: int, letter: str, background: Tuple[int, int, int]) -> bytes:
    """
    Render a square PNG: solid background with a centred initial.

    Written by hand rather than with Pillow, which needs a C toolchain and
    therefore does not install on Termux.
    """
    letter = (letter or "A").upper()[:1]
    glyph = _FONT_5X7.get(letter, _FONT_5X7["A"])

    br, bg, bb = background
    # Foreground is white; the palette is dark enough for solid contrast.
    fr, fg, fb = 255, 255, 255

    # Glyph occupies the central ~46% of the canvas, which keeps it inside the
    # safe zone Android crops maskable icons to.
    scale = max(1, int(size * 0.46) // 7)
    glyph_w, glyph_h = 5 * scale, 7 * scale
    origin_x = (size - glyph_w) // 2
    origin_y = (size - glyph_h) // 2

    rows = bytearray()
    for y in range(size):
        rows.append(0)  # PNG per-scanline filter: none
        gy = (y - origin_y) // scale if origin_y <= y < origin_y + glyph_h else -1
        for x in range(size):
            on = False
            if gy >= 0 and origin_x <= x < origin_x + glyph_w:
                gx = (x - origin_x) // scale
                on = bool(glyph[gy] & (1 << (4 - gx)))
            if on:
                rows += bytes((fr, fg, fb))
            else:
                rows += bytes((br, bg, bb))

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(rows), 9))
        + _png_chunk(b"IEND", b"")
    )


SERVICE_WORKER = """\
// Offline support. Cache-first for the app shell, network-first for the rest,
// so a reinstall or refresh still picks up a new deploy.
const CACHE = '{cache_name}';
const SHELL = ['./', './index.html', './manifest.webmanifest'];

self.addEventListener('install', (event) => {{
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting())
  );
}});

self.addEventListener('activate', (event) => {{
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
}});

self.addEventListener('fetch', (event) => {{
  if (event.request.method !== 'GET') return;
  event.respondWith(
    caches.match(event.request).then((cached) => {{
      const live = fetch(event.request)
        .then((response) => {{
          if (response && response.status === 200 && response.type === 'basic') {{
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(event.request, copy));
          }}
          return response;
        }})
        .catch(() => cached);
      return cached || live;
    }})
  );
}});
"""

REGISTER_SNIPPET = """\
    <script>
      // Registered from the page so the app works offline once installed.
      if ('serviceWorker' in navigator) {
        window.addEventListener('load', function () {
          navigator.serviceWorker.register('./sw.js').catch(function () {});
        });
      }
    </script>
"""


class PWABuilder:
    """Adds the manifest, icons and service worker a web project needs."""

    def __init__(self, project_dir: Path, app_name: Optional[str] = None):
        self.project_dir = Path(project_dir).resolve()
        self.app_name = app_name or self.project_dir.name
        self.colour = theme_colour(self.app_name)

    # ── layout ──────────────────────────────────────────────────────────

    def static_dir(self) -> Path:
        """
        Where static assets belong for this project.

        Vite copies `public/` to the output root verbatim; without that
        directory we fall back to the project root.
        """
        public = self.project_dir / "public"
        if public.is_dir():
            return public
        if (self.project_dir / "vite.config.ts").exists() or (
            self.project_dir / "vite.config.js"
        ).exists():
            public.mkdir(parents=True, exist_ok=True)
            return public
        return self.project_dir

    def display_name(self) -> str:
        """Human-facing app title: 'habit-tracker' -> 'Habit Tracker'."""
        return re.sub(r"[-_]+", " ", self.app_name).strip().title() or "App"

    # ── artefacts ───────────────────────────────────────────────────────

    def manifest(self, base_path: str = "./") -> Dict:
        """Build the web app manifest."""
        name = self.display_name()
        return {
            "name": name,
            "short_name": name.split()[0][:12] if name else "App",
            "description": f"{name} — built with AnywhereCode",
            "start_url": base_path,
            "scope": base_path,
            "display": "standalone",
            "orientation": "portrait",
            "background_color": "#ffffff",
            "theme_color": _rgb_hex(self.colour),
            "icons": [
                {
                    "src": f"{base_path}icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    "src": f"{base_path}icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any",
                },
                {
                    # Android crops maskable icons into its own shape; a
                    # separate entry stops the initial being clipped.
                    "src": f"{base_path}icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable",
                },
            ],
        }

    def write_icons(self, target: Path) -> List[Path]:
        """Write the 192px and 512px icons Chrome requires for install."""
        letter = self.display_name()[:1] or "A"
        written = []
        for size in (192, 512):
            path = target / f"icon-{size}.png"
            path.write_bytes(render_icon_png(size, letter, self.colour))
            written.append(path)
        return written

    def patch_index_html(self, base_path: str = "./") -> Optional[Path]:
        """
        Link the manifest and register the service worker in index.html.

        Idempotent — re-running will not duplicate the tags.
        """
        index = self.project_dir / "index.html"
        if not index.exists():
            return None

        html = index.read_text(encoding="utf-8", errors="ignore")
        if "manifest.webmanifest" in html:
            return None

        tags = (
            f'    <link rel="manifest" href="{base_path}manifest.webmanifest" />\n'
            f'    <meta name="theme-color" content="{_rgb_hex(self.colour)}" />\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1, '
            'viewport-fit=cover" />\n'
            f'    <link rel="apple-touch-icon" href="{base_path}icon-192.png" />\n'
            '    <meta name="mobile-web-app-capable" content="yes" />\n'
        )

        if "</head>" in html:
            html = html.replace("</head>", tags + REGISTER_SNIPPET + "  </head>", 1)
        else:
            html = tags + REGISTER_SNIPPET + html

        index.write_text(html, encoding="utf-8")
        return index

    def make_installable(self, base_path: str = "./") -> List[str]:
        """
        Write everything needed for Chrome to offer "Install app".

        Args:
            base_path: URL prefix the app is served under. GitHub Pages project
                sites live at /<repo>/, so relative paths keep the manifest
                valid wherever it lands.

        Returns:
            Paths written, as strings.
        """
        target = self.static_dir()
        target.mkdir(parents=True, exist_ok=True)
        written: List[Path] = []

        manifest_path = target / "manifest.webmanifest"
        manifest_path.write_text(json.dumps(self.manifest(base_path), indent=2) + "\n")
        written.append(manifest_path)

        # Cache name is tied to the app so two apps on the same Pages domain
        # never share a cache.
        sw_path = target / "sw.js"
        sw_path.write_text(SERVICE_WORKER.format(cache_name=f"{self.app_name}-v1"))
        written.append(sw_path)

        written.extend(self.write_icons(target))

        patched = self.patch_index_html(base_path)
        if patched:
            written.append(patched)

        return [str(p) for p in written]

    # ── deployment shape ────────────────────────────────────────────────

    def needs_build_step(self) -> bool:
        """
        True when this project must be compiled before it can be served.

        A Vite/Next/bundler project has an index.html in its root, but that
        file is *source* — it references /src/main.tsx, which no browser can
        load. Publishing it would deploy a blank page.
        """
        for marker in ("vite.config.ts", "vite.config.js", "next.config.js",
                       "next.config.mjs", "webpack.config.js"):
            if (self.project_dir / marker).exists():
                return True

        package_json = self.project_dir / "package.json"
        if package_json.exists():
            try:
                scripts = json.loads(package_json.read_text()).get("scripts", {})
            except (json.JSONDecodeError, OSError):
                return False
            return "build" in scripts

        return False

    def find_build_output(self) -> Optional[Path]:
        """
        Locate the static site that should actually be published.

        Returns None when the project still needs compiling — the caller must
        run the build first rather than deploy unusable source.
        """
        for candidate in ("dist", "build", "out", "_site"):
            path = self.project_dir / candidate
            if path.is_dir() and (path / "index.html").exists():
                return path

        # Only a genuinely static site can be served straight from its root.
        if not self.needs_build_step() and (self.project_dir / "index.html").exists():
            return self.project_dir

        return None
