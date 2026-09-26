#!/usr/bin/env python3
"""Fetch weather warnings from www.meteoalarm.org and render them as HTML.

Python port of get-meteoalarm-warning-inc.php (V3.16) by Ken True
(saratoga-weather.org), itself adapted from wrnWarningEU-CAP.php by
Wim van der Kuil (pwsdashboard.com). No PHP required.

The script reads the MeteoAlarm JSON feed for each country in the
configured EMMA_ID list, caches the matching warnings, and writes two
HTML fragments:

  meteoalarm-summary.html  compact icon summary, linking to the details page
  meteoalarm-details.html  full warning text with a tab per language

Run it from cron (every 5-15 minutes) and include the fragments in your
pages with a server-side include, or load them in the browser with
meteoalarm-embed.js.

Usage:
  python3 meteoalarm_warning.py --areas DK002,DK004
  python3 meteoalarm_warning.py --config meteoalarm.json

Only the Python 3.9+ standard library is used.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

VERSION = "meteoalarm_warning.py - V4.00 - 26-Sep-2026"
HERE = Path(__file__).resolve().parent

FEED_URL = "https://feeds.meteoalarm.org/api/v1/warnings/feeds-{slug}"
USER_AGENT = "Mozilla/5.0 (compatible; meteoalarm-warning/4.0)"

CACHE_FILE = "meteoalarm-cache.json"
SUMMARY_FILE = "meteoalarm-summary.html"
DETAILS_FILE = "meteoalarm-details.html"

# ---------------------------------------------------------------- reference data

WARN_COLORS = {0: "#fff", 1: "#29d660", 2: "#FFDB23", 3: "#FF9500", 4: "#FF0100"}
WARN_LEVELS = {0: "--", 1: "None", 2: "Moderate", 3: "Severe", 4: "Extreme"}
LEVEL_NAMES = ["Green", "Yellow", "Orange", "Red"]
# words stripped from the event name to get a clean event title
COLOR_WORDS = ["Green", "Yellow", "Orange", "Red", "Amber", "Moderate", "Severe", "Extreme"]

COUNTRIES = {
    "AT": "austria", "BA": "bosnia-herzegovina", "BE": "belgium", "BG": "bulgaria",
    "CH": "switzerland", "CY": "cyprus", "CZ": "czechia", "DE": "germany",
    "DK": "denmark", "EE": "estonia", "ES": "spain", "FI": "finland",
    "FR": "france", "GR": "greece", "HR": "croatia", "HU": "hungary",
    "IE": "ireland", "IL": "israel", "IS": "iceland", "IT": "italy",
    "LT": "lithuania", "LU": "luxembourg", "LV": "latvia", "MD": "moldova",
    "ME": "montenegro", "MK": "republic-of-north-macedonia", "MT": "malta",
    "NL": "netherlands", "NO": "norway", "PL": "poland", "PT": "portugal",
    "RO": "romania", "RS": "serbia", "SE": "sweden", "SI": "slovenia",
    "SK": "slovakia", "UK": "united-kingdom",
}

# display names for language tabs (values are already HTML)
LANG_NAMES = {
    "af": "Afrikaans",
    "bg": "&#1073;&#1098;&#1083;&#1075;&#1072;&#1088;&#1089;&#1082;&#1080; &#1077;&#1079;&#1080;&#1082;",
    "ct": "Catal&agrave;", "da": "Dansk", "dk": "Dansk", "nl": "Nederlands", "en": "English",
    "fi": "Suomi", "fr": "Fran&ccedil;ais", "de": "Deutsch",
    "el": "&Epsilon;&lambda;&lambda;&eta;&nu;&iota;&kappa;&#940;",
    "ga": "Gaeilge", "hu": "Magyar", "it": "Italiano",
    "he": "&#1506;&#1460;&#1489;&#1456;&#1512;&#1460;&#1497;&#1514;",
    "lt": "lietuvi&#371; kalba", "lv": "latvie&#353;u valoda", "no": "Norsk",
    "pl": "Polski", "pt": "Portugu&ecirc;s", "ro": "limba rom&#226;n&#259;",
    "es": "Espa&ntilde;ol", "se": "Svenska", "si": "Sloven&#353;&#269;ina",
    "sk": "Sloven&#269;ina", "sr": "Srpski",
    "de-DE": "Deutsch", "en-GB": "English", "es-ES": "Espa&ntilde;ol",
    "et-ET": "eesti keel", "fi-FI": "Suomi", "fr-FR": "Fran&ccedil;ais",
    "gr-GR": "&Epsilon;&lambda;&lambda;&eta;&nu;&iota;&kappa;&#940;",
    "hr-HR": "Hrvatski", "it-IT": "Italiano", "ne-NL": "Nederlands",
    "po-PL": "Polski", "pt-PT": "Portugu&ecirc;s",
    "ru-RU": "&#1088;&#1091;&#1089;&#1089;&#1082;&#1080;&#1081; &#1103;&#1079;&#1099;&#1082;",
    "sv-SE": "Svenska",
}

DISCLAIMER = (
    "This warning data is courtesy of and is Copyright &copy; by EUMETNET-METEOalarm "
    "(http://www.meteoalarm.org/) and respective National Meteorological Services.<br/>\n"
    'Used with permission per www.meteoalarm.org <a href="https://meteoalarm.org/page/terms-and-conditions" '
    'target="_blank">Terms &amp; Conditions of Reuse</a>.<br/>\n'
    "Time delays between this website and the www.meteoalarm.org website are possible.<br/>\n"
    "For the most up to date information about alert levels as published by the participating "
    'National Meteorological Services please use <a href="https://www.meteoalarm.org/">www.meteoalarm.org</a>.\n'
)

CREDITS = (
    f"<small>{VERSION}<br/>adapted from get-meteoalarm-warning-inc.php by "
    '<a href="https://saratoga-weather.org/wxtemplates/" target="_blank">Saratoga-Weather.org</a> '
    "with permission from wrnWarningEU-CAP.php script in "
    '<a href="https://pwsdashboard.com" target="_blank">pwsdashboard.com</a>.</small>'
)

BOX_STYLE = "width: 625px; margin: 0 auto !important;"
NOTE_STYLE = ("width: 100%; margin: 8px auto; padding-bottom: 5px; background-color: #DCDCDC; "
              "text-align: center; border: 1px solid black;")

TAB_ASSETS = """<style>
.meteoalarm-tab { overflow: hidden; display: block; background-color: white; text-align: left; margin: 4px 4px 4px 0; }
.meteoalarm-tab > span { text-align: left; margin: 4px; }
.meteoalarm-tab label { float: left; border-radius: 4px; background-color: #ccc; border: 1px solid #ddd; cursor: pointer; margin: 3px 3px 0 3px; padding: 3px; }
.meteoalarm-tab label:hover { background-color: white; }
.meteoalarm-tab label.active { border-bottom-right-radius: 0; border-bottom-left-radius: 0; background-color: transparent; border: 1px solid black; border-bottom: 1px solid white; }
.meteoalarm-tab .tabcontent { display: none; }
.meteoalarm-tab a { text-decoration: underline; color: blue !important; }
</style>
<script>
(function () {
  if (window.meteoalarmTabsBound) { return; }
  window.meteoalarmTabsBound = true;
  document.addEventListener("click", function (evt) {
    var label = evt.target.closest ? evt.target.closest("label[data-meteoalarm-tab]") : null;
    if (!label) { return; }
    var box = label.closest(".meteoalarm-tab");
    box.querySelectorAll(".tabcontent").forEach(function (el) { el.style.display = "none"; });
    box.querySelectorAll("label[data-meteoalarm-tab]").forEach(function (el) { el.classList.remove("active"); });
    document.getElementById(label.getAttribute("data-meteoalarm-tab")).style.display = "block";
    label.classList.add("active");
  });
})();
</script>
"""


# ---------------------------------------------------------------- configuration

@dataclass
class Config:
    areas: list[str] = field(default_factory=list)
    cache_dir: Path = Path(".")
    tz: str = "Europe/Brussels"
    date_format: str = "%Y-%m-%d"
    time_format: str = "%H:%M %Z"
    min_level: int = 2          # 1=green 2=yellow 3=orange 4=red
    cache_max_age: int = 300    # seconds
    detail_page_url: str = "./wxadvisory.html"
    image_url: str = "./ajax-images/meteoalarm_##.svg"
    image_dir: Path = HERE / "ajax-images"
    force: bool = False
    test_file: Path | None = None   # read a saved feed instead of fetching

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)


def parse_areas(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        value = ",".join(value)
    return [a.strip().upper() for a in value.split(",") if a.strip()]


def load_config(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(description="Fetch MeteoAlarm warnings and write HTML fragments.")
    p.add_argument("--config", help="JSON file with any of the settings below (CLI flags win)")
    p.add_argument("--areas", help="comma-separated EMMA_IDs, e.g. DK002,DK004")
    p.add_argument("--cache-dir", help="directory for cache and output files (default .)")
    p.add_argument("--tz", help="IANA time zone for displayed times (default Europe/Brussels)")
    p.add_argument("--date-format", help="strftime date format (default %%Y-%%m-%%d)")
    p.add_argument("--time-format", help="strftime time format (default %%H:%%M %%Z)")
    p.add_argument("--min-level", type=int, help="1=green 2=yellow 3=orange 4=red (default 2)")
    p.add_argument("--cache-max-age", type=int, help="seconds before refetching (default 300)")
    p.add_argument("--detail-page-url", help="page that shows meteoalarm-details.html")
    p.add_argument("--image-url", help="icon URL pattern, ## is the icon number")
    p.add_argument("--image-dir", help="local folder holding the icons (to check they exist)")
    p.add_argument("--test-file", help="use a saved feed JSON file instead of fetching")
    p.add_argument("--force", action="store_true", help="ignore the cache and refetch")
    args = p.parse_args(argv)

    settings: dict = {}
    if args.config:
        settings = json.loads(Path(args.config).read_text(encoding="utf-8"))
    for key, val in vars(args).items():
        if key != "config" and val not in (None, False):
            settings[key] = val

    cfg = Config()
    for key, val in settings.items():
        key = key.replace("-", "_")
        if not hasattr(cfg, key):
            raise SystemExit(f"unknown setting: {key}")
        if key == "areas":
            val = parse_areas(val)
        elif key in ("cache_dir", "image_dir", "test_file"):
            val = Path(val)
        setattr(cfg, key, val)
    if env_areas := os.environ.get("METEOALARM_AREAS"):
        cfg.areas = cfg.areas or parse_areas(env_areas)
    if not 1 <= int(cfg.min_level) <= 4:
        cfg.min_level = 2
    return cfg


def load_json(name: str) -> dict:
    path = HERE / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log(f"unable to load {name}: {exc}")
        return {}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------- fetching

def fetch_feed(country: str, cfg: Config, status: list[str]) -> dict | None:
    if cfg.test_file:
        status.append(f"test file {cfg.test_file} used for {country}")
        return json.loads(cfg.test_file.read_text(encoding="utf-8"))
    url = FEED_URL.format(slug=COUNTRIES[country])
    start = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        status.append(f"{country}: {time.monotonic() - start:.3f}s - PROBLEM {exc} for {url}")
        return None
    status.append(f"{country}: {time.monotonic() - start:.3f}s - OK for {url}")
    return data


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def match_areas(info: dict, areas: set[str], aliases: dict) -> list[dict]:
    """Return the configured areas an alert <info> block covers."""
    hits = []
    for area in as_list(info.get("area")):
        for geo in as_list(area.get("geocode")):
            value, name = geo.get("value"), geo.get("valueName")
            if not isinstance(value, str) or not isinstance(name, str):
                continue
            desc = area.get("areaDesc", "")
            if name == "EMMA_ID" and value in areas:
                hits.append({"code": value, "desc": desc, "note": ""})
                continue
            alias = aliases.get(f"{value}|{name}")
            if alias in areas:
                note = f"Note: EMMA_ID [{alias}] alias of {name} geocode [{value}] was used for this alert."
                hits.append({"code": alias + "*", "desc": desc, "note": note})
    return hits


def collect_warnings(feeds: dict[str, dict], areas: list[str], aliases: dict, now: datetime) -> dict:
    """{warning id: {language: info}} for alerts in our areas that are current or start within 24h."""
    wanted = set(areas)
    warns: dict[str, dict] = {}
    for country, feed in feeds.items():
        for warning in feed.get("warnings") or []:
            wid = f"{COUNTRIES[country]}/{warning.get('uuid', '')}"
            for alert in warning.values():
                if not isinstance(alert, dict) or "info" not in alert:
                    continue
                infos = as_list(alert["info"])
                if not infos:
                    continue
                expires = parse_time(infos[0].get("expires"))
                if expires is None or now > expires:
                    continue
                effective = parse_time(infos[0].get("effective")) or now
                if (effective - now).total_seconds() > 24 * 3600:
                    continue
                for info in infos:
                    hits = match_areas(info, wanted, aliases)
                    if not hits:
                        continue
                    entry = {k: v for k, v in info.items() if k != "area"}
                    entry.update(forus=hits, sent=alert.get("sent"), sender=alert.get("sender"))
                    warns.setdefault(wid, {})[info.get("language", "")] = entry
    return warns


def get_warnings(cfg: Config, aliases: dict, status: list[str]) -> dict:
    cache = cfg.cache_dir / CACHE_FILE
    now = time.time()
    fresh = cache.exists() and now - cache.stat().st_mtime <= cfg.cache_max_age
    if fresh and not cfg.force and not cfg.test_file:
        stamp = datetime.fromtimestamp(cache.stat().st_mtime, cfg.zone)
        status.append(f"Loaded warning data from {cache}. Updated: {fmt(stamp, cfg)}")
        return json.loads(cache.read_text(encoding="utf-8"))

    feeds = {}
    for country in dict.fromkeys(a[:2] for a in cfg.areas):
        if country not in COUNTRIES:
            status.append(f"{country}: unknown country code, skipped")
            continue
        data = fetch_feed(country, cfg, status)
        if data and data.get("warnings"):
            feeds[country] = data
        elif data is not None:
            status.append(f"{country}: no warnings in feed")
    warns = collect_warnings(feeds, cfg.areas, aliases, datetime.now(timezone.utc))
    cache.write_text(json.dumps(warns, ensure_ascii=False, indent=1), encoding="utf-8")
    return warns


# ---------------------------------------------------------------- rendering

def fmt(dt: datetime, cfg: Config, date: bool = True) -> str:
    dt = dt.astimezone(cfg.zone)
    return dt.strftime(f"{cfg.date_format} {cfg.time_format}" if date else cfg.time_format)


def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def linkify(escaped: str, url: str) -> str:
    """Turn occurrences of the alert's web URL into a link (text already escaped)."""
    if not url:
        return escaped
    e = esc(url)
    return escaped.replace(e, f'<a href="{e}" target="_blank">{e}</a>')


def icon_url(number: str, cfg: Config) -> str:
    if number != "info" and not (cfg.image_dir / f"meteoalarm_{number}.svg").exists():
        number = "000"
    return cfg.image_url.replace("##", number)


def title_case(slug: str) -> str:
    return slug.replace("-", " ").title()


def parse_parameters(info: dict) -> tuple[int, int, str]:
    """(level, event number, event slug) from awareness_level / awareness_type."""
    level_raw = type_raw = ""
    for param in as_list(info.get("parameter")):
        if param.get("valueName") == "awareness_level":
            level_raw = param.get("value", "")
        elif param.get("valueName") == "awareness_type" or not type_raw:
            type_raw = param.get("value", "")

    def leading_int(s: str) -> int:
        try:
            return int(s.split(";")[0].strip())
        except ValueError:
            return 0

    parts = type_raw.split(";")
    event = parts[1].strip() if len(parts) > 1 else ""
    return leading_int(level_raw), leading_int(type_raw), event


def area_names(areas: list[str], codenames: dict) -> str:
    out = []
    for code in areas:
        name = codenames.get(code, "Name not available for")
        out.append(f"{esc(name)} ({code})".replace(" ", "&nbsp;"))
    return "; ".join(out)


def render(warns: dict, cfg: Config, codenames: dict, status: list[str]) -> tuple[str, str]:
    """Return (details_html, summary_html)."""
    rows: list[str] = []
    by_country: dict[str, dict[str, dict[tuple, list[str]]]] = {}
    anchor_no = tab_no = block_no = 0

    for languages in warns.values():
        info = next(iter(languages.values()))
        level, event_no, event = parse_parameters(info)
        if level < cfg.min_level or not 1 <= level <= 4:
            continue
        color = WARN_COLORS[level]
        image = icon_url(str(event_no), cfg)
        onset = parse_time(info.get("onset")) or parse_time(info.get("effective"))
        expires = parse_time(info.get("expires"))
        valid = ""
        if onset and expires:
            same_day = onset.astimezone(cfg.zone).date() == expires.astimezone(cfg.zone).date()
            valid = (f"<b>Valid:&nbsp;</b>{esc(fmt(onset, cfg))}&nbsp;&nbsp;-&nbsp;&nbsp;"
                     f"{esc(fmt(expires, cfg, date=not same_day))}")
        title = info.get("event", "")
        for word in COLOR_WORDS:
            title = title.replace(word, "")
        title = title.strip()
        title = title[:1].upper() + title[1:]

        anchor_no += 1
        anchor = f"alert{anchor_no}"
        for i, region in enumerate(info["forus"]):
            a = f'<a id="{anchor}"></a>' if i == 0 else ""
            rows.append(
                f'<tr style="background-color: {color}"><td colspan="2">{a}'
                f'<span style="margin-left: 5px; float: left;"><b>{esc(title)}&nbsp;&nbsp;&nbsp;'
                f'{esc(region["desc"])}</b> <small>({esc(region["code"])})</small></span>'
                f'<span style="float: right; margin-right: 5px;">{valid}</span></td></tr>')
            key = (color, image, event)
            country_areas = by_country.setdefault(region["code"][:2], {})
            country_areas.setdefault(region["desc"], {}).setdefault(key, []).append(anchor)

        # one tab per language, plus an info tab
        block_no += 1
        web = (info.get("web") or "").strip()
        labels, panels = [], []

        def add_tab(label_html: str, body: str) -> None:
            nonlocal tab_no
            tab_no += 1
            tab_id = f"t{block_no}-{tab_no}"
            first = not labels
            margin = ' style="margin-left: 20px;"' if first else ""
            labels.append(f'<label class="{"active" if first else ""}"{margin} '
                          f'data-meteoalarm-tab="{tab_id}">&nbsp;{label_html}&nbsp;</label>')
            panels.append(f'<span id="{tab_id}" class="tabcontent" '
                          f'style="clear: left; display: {"block" if first else "none"};">\n{body}</span>')

        for lang, text in languages.items():
            name = LANG_NAMES.get(lang) or LANG_NAMES.get(lang[:2]) or esc(lang)
            headline = esc((text.get("headline") or "").strip())
            desc = linkify(esc((text.get("description") or "").strip()), web)
            if desc == headline:
                desc = ""
            body = ""
            if headline or desc:
                sep = "<br />" if headline and desc else ""
                body += f'<b style="text-align: center; width: 100%; display: block;">{headline}{sep}</b>\n<br />\n'
            body += desc.replace("\n", "<br />") + "<br />\n"
            instruction = linkify(esc((text.get("instruction") or "").strip()), web)
            if instruction:
                body += f"<br />{instruction.replace(chr(10), '<br />')}<br />\n"
            add_tab(name, body)

        if web:
            u = urlparse(web)
            origin = f"{u.scheme}://{u.netloc}/" if u.scheme and u.netloc else "/"
            info_body = f'Originator: <a href="{esc(origin)}" target="_blank">{esc(info.get("senderName"))}</a><br/>\n'
        else:
            info_body = "Originator: n/a<br/>\n"
        sent = parse_time(info.get("sent"))
        if sent:
            info_body += f"Issued: <b>{esc(fmt(sent, cfg))}</b><br/>\n"
        for region in info["forus"]:
            if region["note"]:
                info_body += esc(region["note"]) + "<br/>\n"
        add_tab(f'<img src="{esc(icon_url("info", cfg))}" alt="info" title="info"/>',
                '<b style="text-align: center; width: 100%; display: block;">Information<br />\n</b>\n<br />\n'
                + info_body)

        rows.append(
            f'<tr style="background-color: {color}"><td style="vertical-align: top; width: 110px;">'
            f'<img src="{esc(image)}" style="margin: 4px; width: 100px; max-width: 128px;" '
            f'alt="{esc(title_case(event))}" title="{esc(title_case(event))}"/></td>\n'
            f'<td style="text-align: left;"><span class="meteoalarm-tab">\n'
            + "\n".join(labels) + "\n" + "\n".join(panels) + "\n</span></td></tr>\n"
            "<tr><td>&nbsp;</td></tr>")

    status_comment = "<!-- Fetch status:\n" + esc("\n".join(status)) + "\n-->\n"

    if not by_country:
        box = (f'<div class="advisoryBox" style="text-align: center; background-color: #29d660; {BOX_STYLE}">\n'
               f"{status_comment}No current alerts for: &quot;{area_names(cfg.areas, codenames)}&quot;.\n</div>\n")
        return wrap(box, DETAILS_FILE), wrap(box, SUMMARY_FILE)

    # summary: one row per area, one icon per distinct (colour, icon, event)
    cell = "width: 40px !important; height: 40px !important; border: 1px solid black; margin: 2px; display: block; float: left;"
    icon_style = "margin: 4px; width: 32px; height: 32px;"
    summary = [f'<div class="advisoryBox" style="text-align: left; background-color: lightyellow; {BOX_STYLE}">',
               '<p style="text-align: center; width: 99%;"><strong>Watches/Warnings/Advisories</strong></p>',
               "<table>"]
    for country in sorted(by_country):
        country_name = title_case(COUNTRIES.get(country, country))
        for area, alerts in by_country[country].items():
            icons = []
            for (color, image, event), anchors in alerts.items():
                label = esc(title_case(event))
                icons.append(f'<div style="background-color: {color} !important; {cell}">'
                             f'<a href="{esc(cfg.detail_page_url)}#{anchors[0]}">'
                             f'<img src="{esc(image)}" style="{icon_style}" alt="{label}" title="{label}"/>'
                             f"</a></div>&nbsp;")
            summary.append(f'<tr><td>{"".join(icons)}</td>'
                           f'<td style="text-align: left;">{esc(area)}, {esc(country_name)}</td></tr>')
    summary += ["</table>", "</div>"]

    details = (status_comment + TAB_ASSETS
               + '<table style="width: 100%; border-collapse: collapse; margin-top: 8px;">\n'
               + "\n".join(rows) + "\n</table>\n"
               + f'<p style="{NOTE_STYLE}">{DISCLAIMER}<br />\n{CREDITS}</p>\n')
    return wrap(details, DETAILS_FILE), wrap("\n".join(summary) + "\n", SUMMARY_FILE)


def wrap(body: str, name: str) -> str:
    return f"<!-- {VERSION}: begin {name} -->\n{body}<!-- end {name} -->\n"


def config_needed_html() -> str:
    return (f'<p style="{NOTE_STYLE}">{VERSION}<br/><br/><b>Configuration needed:</b><br/>\n'
            "No EMMA_ID(s) were given. Use "
            '<a href="https://saratoga-weather.org/meteoalarm-map/" target="_blank">the meteoalarm map</a> '
            "to find the EMMA_ID for your area, then run for example<br/><br/>\n"
            "<b>python3 meteoalarm_warning.py --areas DK002,DK004,DK005</b><br/><br/>\n"
            "Areas in more than one country work, but each extra country adds a feed download.</p>\n")


# ---------------------------------------------------------------- main

def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    log(f"saved {path}")


def main(argv: list[str] | None = None) -> int:
    cfg = load_config(argv)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    details_path = cfg.cache_dir / DETAILS_FILE
    summary_path = cfg.cache_dir / SUMMARY_FILE
    log(f"{VERSION}; showing '{LEVEL_NAMES[cfg.min_level - 1]}' or more severe alerts")

    if not cfg.areas or any(len(a) < 5 for a in cfg.areas):
        page = config_needed_html()
        write(details_path, page)
        write(summary_path, page)
        return 2

    status: list[str] = []
    warns = get_warnings(cfg, load_json("meteoalarm-geocode-aliases.json"), status)
    for line in status:
        log(line)
    details, summary = render(warns, cfg, load_json("meteoalarm-codenames.json"), status)
    write(details_path, details)
    write(summary_path, summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
