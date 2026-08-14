"""
Tests for the one-shot flow: prompt → intent → installable app.

Offline. No LLM, no network, no accounts.

Run with: python3 test_create.py
"""

import json
import struct
import sys
import tempfile
import zlib
from pathlib import Path

from anyplace.core.intent import (
    BuildIntent,
    infer_intent,
    name_from_prompt,
    slugify,
    template_from_keywords,
)
from anyplace.core.pwa_builder import PWABuilder, render_icon_png, theme_colour


PASSED = []
FAILED = []


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        PASSED.append(name)
        print(f"  ✅ {name}")
    else:
        FAILED.append(f"{name}: {detail}")
        print(f"  ❌ {name} — {detail}")


def make_vite_project(tmp: Path, name: str = "app") -> Path:
    """A directory shaped like what the generator leaves behind."""
    project = tmp / name
    project.mkdir(parents=True, exist_ok=True)
    (project / "vite.config.ts").write_text("export default {}")
    (project / "index.html").write_text(
        "<!doctype html><html><head><title>x</title></head>"
        '<body><div id="root"></div></body></html>'
    )
    return project


def test_slugify():
    print("\n[1] Slug and name derivation")
    check("lowercases and hyphenates", slugify("My Cool App") == "my-cool-app", slugify("My Cool App"))
    check("collapses repeated separators", slugify("a  --  b") == "a-b", slugify("a  --  b"))
    check("strips leading/trailing dashes", not slugify("--x--").startswith("-"), slugify("--x--"))
    check("falls back when empty", slugify("!!!", fallback="my-app") == "my-app", slugify("!!!"))
    check("caps length", len(slugify("x" * 200)) <= 40, len(slugify("x" * 200)))

    check("drops filler words",
          name_from_prompt("build me a simple habit tracker") == "habit-tracker",
          name_from_prompt("build me a simple habit tracker"))
    check("handles a bare noun",
          name_from_prompt("calculator") == "calculator",
          name_from_prompt("calculator"))
    check("never returns empty",
          bool(name_from_prompt("a the of and")), name_from_prompt("a the of and"))


def test_keyword_routing():
    print("\n[2] Template routing without a model")
    cases = [
        ("a habit tracker with streaks", "web-react-vite"),
        ("build me a tip calculator", "web-react-vite"),
        ("an android app that scans barcodes with the camera", "mobile-expo-rn"),
        ("a react native app for the play store", "mobile-expo-rn"),
        ("a REST api for a todo list", "backend-nodejs"),
        ("python ml api for image classification", "backend-python-fastapi"),
        ("a full stack saas with login and a database", "fullstack-nextjs"),
    ]
    for prompt, expected in cases:
        actual = template_from_keywords(prompt)
        check(f'"{prompt[:38]}" → {expected}', actual == expected, f"got {actual}")

    check("unrecognised input still returns a real template",
          template_from_keywords("zzzz qqqq") == "web-react-vite",
          template_from_keywords("zzzz qqqq"))


def test_intent_resilience():
    print("\n[3] Intent inference degrades instead of crashing")

    intent = infer_intent("a habit tracker", llm_provider=None)
    check("works with no model at all", intent.template == "web-react-vite")
    check("marks the inference source", intent.inferred_by == "keywords", intent.inferred_by)

    class ExplodingLLM:
        def generate_json(self, **kwargs):
            raise RuntimeError("429 rate limited")

    intent = infer_intent("a habit tracker", llm_provider=ExplodingLLM())
    check("survives an LLM failure", intent.template == "web-react-vite")
    check("falls back to keywords", intent.inferred_by == "keywords", intent.inferred_by)

    class BogusLLM:
        def generate_json(self, **kwargs):
            return {"template": "not-a-real-template", "project_name": "x"}

    intent = infer_intent("a todo list", llm_provider=BogusLLM())
    check("rejects a hallucinated template name",
          intent.template == "web-react-vite", intent.template)

    class GoodLLM:
        def generate_json(self, **kwargs):
            return {
                "template": "mobile-expo-rn",
                "project_name": "Barcode Scanner",
                "reasoning": "needs the camera",
            }

    intent = infer_intent("scan barcodes", llm_provider=GoodLLM())
    check("uses a valid model choice", intent.template == "mobile-expo-rn", intent.template)
    check("slugifies the model's project name",
          intent.project_name == "barcode-scanner", intent.project_name)
    check("records the source as llm", intent.inferred_by == "llm", intent.inferred_by)

    intent = infer_intent("anything", llm_provider=GoodLLM(), template_override="web-react-vite")
    check("explicit override wins over the model",
          intent.template == "web-react-vite" and intent.inferred_by == "explicit",
          f"{intent.template}/{intent.inferred_by}")


def test_icon_png():
    print("\n[4] Icon generation (no Pillow)")
    png = render_icon_png(192, "H", (37, 99, 235))

    check("emits the PNG magic number", png[:8] == b"\x89PNG\r\n\x1a\n")
    width, height = struct.unpack(">II", png[16:24])
    check("has the requested dimensions", (width, height) == (192, 192), f"{width}x{height}")
    check("declares 8-bit RGB", png[24] == 8 and png[25] == 2, f"depth={png[24]} type={png[25]}")
    # IEND is a full 12-byte chunk: 4 length + 4 tag + 4 CRC.
    check("ends with a well-formed IEND chunk",
          png[-12:] == b"\x00\x00\x00\x00IEND\xaeB`\x82", repr(png[-12:]))

    # Decompress the pixel data and confirm both colours are present, i.e. the
    # glyph actually rendered rather than a blank square.
    start = png.index(b"IDAT") + 4
    end = png.rindex(b"IEND") - 8
    raw = zlib.decompress(png[start:end])
    stride = 192 * 3 + 1
    row = raw[stride * 96 + 1 : stride * 97]  # middle scanline, minus filter byte
    pixels = {tuple(row[i : i + 3]) for i in range(0, len(row), 3)}
    check("background colour present", (37, 99, 235) in pixels, str(list(pixels)[:3]))
    check("glyph colour present", (255, 255, 255) in pixels, str(list(pixels)[:3]))

    check("unknown characters do not crash", len(render_icon_png(64, "→", (0, 0, 0))) > 0)
    check("colour is stable for a given name",
          theme_colour("habit-tracker") == theme_colour("habit-tracker"))
    check("different names get different colours",
          len({theme_colour(n) for n in ("a", "b", "c", "d", "e")}) > 1)


def test_pwa_installability():
    print("\n[5] PWA installability requirements")
    with tempfile.TemporaryDirectory() as tmpdir:
        project = make_vite_project(Path(tmpdir), "habit-tracker")
        builder = PWABuilder(project, app_name="habit-tracker")
        builder.make_installable()

        static = project / "public"
        check("assets land in public/ for Vite", static.is_dir())

        manifest = json.loads((static / "manifest.webmanifest").read_text())
        # These are exactly Chrome's criteria for offering "Install app".
        check("manifest has a name", bool(manifest.get("name")))
        check("display is standalone", manifest["display"] == "standalone", manifest["display"])
        check("has a start_url", bool(manifest.get("start_url")))
        sizes = {icon["sizes"] for icon in manifest["icons"]}
        check("ships a 192px icon", "192x192" in sizes, str(sizes))
        check("ships a 512px icon", "512x512" in sizes, str(sizes))
        check("ships a maskable icon",
              any(i.get("purpose") == "maskable" for i in manifest["icons"]))

        check("icon files exist", (static / "icon-192.png").exists()
              and (static / "icon-512.png").exists())

        sw = (static / "sw.js").read_text()
        check("service worker handles fetch", "addEventListener('fetch'" in sw)
        check("service worker precaches the shell", "SHELL" in sw)
        check("cache name is app-specific", "habit-tracker-v1" in sw)

        html = (project / "index.html").read_text()
        check("index.html links the manifest", "manifest.webmanifest" in html)
        check("index.html registers the worker", "serviceWorker.register" in html)
        check("index.html sets theme-color", "theme-color" in html)
        check("index.html sets a viewport", "viewport" in html)

        # Re-running must not duplicate tags.
        before = html
        builder.make_installable()
        check("patching index.html is idempotent",
              (project / "index.html").read_text() == before)


def test_pwa_layout_detection():
    print("\n[6] Output layout detection")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        project = make_vite_project(tmp, "vite-app")
        check("uses public/ for a Vite project",
              PWABuilder(project).static_dir().name == "public")

        plain = tmp / "plain"
        plain.mkdir()
        (plain / "index.html").write_text("<html></html>")
        check("uses the root for a plain static site",
              PWABuilder(plain).static_dir() == plain)

        check("a Vite project is flagged as needing a build",
              PWABuilder(project).needs_build_step())
        check("a plain static site needs no build",
              not PWABuilder(plain).needs_build_step())

        # Publishing a Vite root would deploy source, not a working app.
        check("refuses to publish unbuilt Vite source",
              PWABuilder(project).find_build_output() is None,
              str(PWABuilder(project).find_build_output()))
        check("publishes a plain static site from its root",
              PWABuilder(plain).find_build_output() == plain)

        dist = project / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("<html></html>")
        check("finds dist/ after building",
              PWABuilder(project).find_build_output() == dist)

        check("derives a display name",
              PWABuilder(tmp / "habit-tracker").display_name() == "Habit Tracker",
              PWABuilder(tmp / "habit-tracker").display_name())


def main():
    print("=" * 62)
    print("  AnywhereCode — one-shot create flow")
    print("=" * 62)

    test_slugify()
    test_keyword_routing()
    test_intent_resilience()
    test_icon_png()
    test_pwa_installability()
    test_pwa_layout_detection()

    print("\n" + "=" * 62)
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    print("=" * 62)

    if FAILED:
        for failure in FAILED:
            print(f"  ❌ {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
