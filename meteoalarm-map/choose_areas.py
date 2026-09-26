#!/usr/bin/env python3
#
#    Copyright (c) 2026 Ian Millard
#    Released under the GNU General Public License v3; see LICENSE.
#
"""Choose the MeteoAlarm warning areas for WeeWX on a map.

The WeeWX installer for the meteoalarm extension runs this automatically:
it asks you to select your location(s), opens the map in your browser, and
writes what you pick into the [Meteoalarm] section of weewx.conf.

Run it again at any time to change your areas:

    python3 ~/weewx-data/meteoalarm-map/choose_areas.py

Options:
    --config PATH    weewx.conf to update (default: the one next to this folder)
    --host ADDRESS   address to listen on; 0.0.0.0 lets another computer on your
                     network open the map (default 127.0.0.1, this computer only)
    --port N         port to listen on (default 8765, or any free port)
    --no-browser     just print the link instead of opening a browser

The map is served by a small web server that runs only while you choose,
listens on this computer only unless you say otherwise, and uses a random
link so no other page or person can change your settings.
"""

import argparse
import http.server
import json
import os
import re
import secrets
import shutil
import getpass
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PORT = 8765
MAX_CORNERS = 200
TYPES = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".json": "application/json", ".geojson": "application/json"}
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


# ----------------------------------------------------------------------------- settings

def as_text(value):
    """A weewx.conf value (ConfigObj may have split it into a list at the commas) as text."""
    if isinstance(value, (list, tuple)):
        return ",".join(str(v) for v in value)
    return str(value or "")


def current_settings(config_dict):
    sec = config_dict.get("Meteoalarm") or {}
    ids = [c.strip().upper() for c in as_text(sec.get("emma_ids")).split(",") if c.strip()]
    try:
        level = int(sec.get("min_level", 2))
    except (TypeError, ValueError):
        level = 2
    station = None
    try:
        st = config_dict["Station"]
        lat, lon = float(st["latitude"]), float(st["longitude"])
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            station = [lat, lon]
    except (KeyError, TypeError, ValueError):
        pass
    return {"emma_ids": ids, "polygon": " ".join(as_text(sec.get("polygon")).split()),
            "min_level": min(4, max(1, level)), "station": station}


def clean_polygon(text):
    """Validate a CAP polygon "lat,lon lat,lon ..." and return it normalised ("" if empty)."""
    pts = []
    for pair in str(text or "").split():
        try:
            lat, lon = (float(v) for v in pair.split(","))
        except ValueError:
            raise ValueError("polygon corner %r is not lat,lon" % pair)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("polygon corner %r is off the map" % pair)
        pts.append((lat, lon))
    if pts and pts[0] == pts[-1]:
        pts.pop()
    if not pts:
        return ""
    if len(pts) < 3:
        raise ValueError("a polygon needs at least 3 corners")
    if len(pts) > MAX_CORNERS:
        raise ValueError("a polygon can have at most %d corners" % MAX_CORNERS)
    pts.append(pts[0])
    return " ".join("%.4f,%.4f" % p for p in pts)


def clean_selection(data, known_codes):
    """Check a selection sent by the map (or given on the command line)."""
    ids = data.get("emma_ids") or []
    if isinstance(ids, str):
        ids = ids.split(",")
    codes = []
    for c in ids:
        c = str(c).strip().upper()
        if not c:
            continue
        if known_codes and c not in known_codes:
            raise ValueError("unknown area code %s" % c)
        if not re.fullmatch(r"[A-Z]{2}[0-9]{3,4}", c):
            raise ValueError("%s is not an EMMA code" % c)
        if c not in codes:
            codes.append(c)
    polygon = clean_polygon(data.get("polygon"))
    try:
        level = int(data.get("min_level", 2))
    except (TypeError, ValueError):
        raise ValueError("min_level must be 1 to 4")
    if not 1 <= level <= 4:
        raise ValueError("min_level must be 1 to 4")
    if not codes and not polygon:
        raise ValueError("choose at least one area or draw a polygon")
    return {"emma_ids": sorted(codes), "polygon": polygon, "min_level": level}


def apply_selection(config_dict, sel):
    """Write a selection into the [Meteoalarm] section of a ConfigObj dictionary."""
    if "Meteoalarm" not in config_dict:
        config_dict["Meteoalarm"] = {}
    sec = config_dict["Meteoalarm"]
    sec["emma_ids"] = ", ".join(sel["emma_ids"])
    sec["polygon"] = sel["polygon"]
    sec["min_level"] = str(sel["min_level"])


def describe(sel, names=None):
    names = names or {}
    parts = ["%s (%s)" % (c, names[c][0]) if c in names else c for c in sel["emma_ids"]]
    if sel["polygon"]:
        parts.append("a polygon with %d corners" % (len(sel["polygon"].split()) - 1))
    return ", ".join(parts)


# ----------------------------------------------------------------------------- web server

class Chooser:
    """Serves the map and waits for the user to save a selection."""

    def __init__(self, config_dict, skin_dir, page_dir=HERE):
        self.page_dir = page_dir
        self.map_dir = os.path.join(skin_dir, "map")
        self.areas_dir = os.path.join(skin_dir, "areas")
        try:
            with open(os.path.join(self.areas_dir, "index.json"), encoding="utf-8") as fh:
                self.index = json.load(fh)
        except (OSError, ValueError) as e:
            raise RuntimeError("cannot read the area list in %s: %s" % (self.areas_dir, e))
        self.token = secrets.token_urlsafe(18)
        self.base = "/s/%s/" % self.token
        self.settings = current_settings(config_dict)
        self.result = None
        self.saved = threading.Event()
        self.host_names = set()

    # routing -------------------------------------------------------------
    def file_for(self, path):
        """(file path, content type) for a GET, or None."""
        if not path.startswith(self.base):
            return None
        rest = path[len(self.base):]
        if rest in ("map", "map/"):
            rest = "map/index.html"
        folder, _, name = rest.partition("/")
        if not SAFE_NAME.match(name or "-") or "/" in name:
            return None
        if folder == "map" and name == "index.html":
            full = os.path.join(self.page_dir, name)
        elif folder == "map" and name in ("map.js", "map.css"):
            full = os.path.join(self.map_dir, name)
        elif folder == "areas":
            full = os.path.join(self.areas_dir, name)
        else:
            return None
        ext = os.path.splitext(name)[1]
        if ext not in TYPES or not os.path.isfile(full):
            return None
        return full, TYPES[ext]

    def config_js(self):
        cfg = dict(self.settings, save_url=self.base + "save")
        return ("window.MA_CONFIG = %s;\n" % json.dumps(cfg).replace("</", "<\\/")).encode("utf-8")

    def make_handler(self):
        chooser = self

        class Handler(http.server.BaseHTTPRequestHandler):
            server_version = "meteoalarm-setup"

            def log_message(self, *args):
                pass

            def _host_ok(self):
                # refuse requests addressed to some other host name (DNS rebinding)
                return not chooser.host_names or self.headers.get("Host", "") in chooser.host_names

            def _send(self, code, body, ctype="text/plain; charset=utf-8"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if not self._host_ok():
                    return self._send(403, b"Forbidden")
                path = self.path.split("?", 1)[0]
                if path in ("/s/%s" % chooser.token, chooser.base):
                    self.send_response(302)
                    self.send_header("Location", chooser.base + "map/")
                    self.end_headers()
                    return
                if path == chooser.base + "map/config.js":
                    return self._send(200, chooser.config_js(), TYPES[".js"])
                found = chooser.file_for(path)
                if not found:
                    return self._send(404, b"Not found. Use the link printed by the WeeWX installer.")
                with open(found[0], "rb") as fh:
                    self._send(200, fh.read(), found[1])

            def do_POST(self):
                if not self._host_ok() or self.path != chooser.base + "save":
                    return self._send(404, b"Not found")
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if length > 100000:
                        raise ValueError("request too large")
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                    sel = clean_selection(data, chooser.index)
                except (ValueError, TypeError, AttributeError) as e:
                    return self._send(400, json.dumps({"error": str(e)}).encode(), TYPES[".json"])
                chooser.result = sel
                self._send(200, json.dumps({"ok": True}).encode(), TYPES[".json"])
                chooser.saved.set()

        return Handler

    def serve(self, host, port):
        """Start the server; returns the port in use."""
        handler = self.make_handler()
        try:
            self.httpd = http.server.ThreadingHTTPServer((host, port), handler)
        except OSError:
            self.httpd = http.server.ThreadingHTTPServer((host, 0), handler)
        self.httpd.daemon_threads = True
        port = self.httpd.server_address[1]
        if host in ("127.0.0.1", "localhost", "::1"):
            self.host_names = {"localhost:%d" % port, "127.0.0.1:%d" % port, "[::1]:%d" % port}
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return port

    def stop(self):
        time.sleep(0.5)   # let the browser receive the "saved" reply
        self.httpd.shutdown()
        self.httpd.server_close()


# ----------------------------------------------------------------------------- terminal side

def has_desktop():
    if sys.platform.startswith("linux") or "bsd" in sys.platform:
        return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return True


def lan_addresses():
    """This computer's IPv4 addresses, most likely reachable first.

    If you are logged in over SSH, the address you connected to comes first:
    that one certainly works from your own computer."""
    found = []
    ssh = os.environ.get("SSH_CONNECTION", "").split()
    if len(ssh) == 4:
        found.append(ssh[2])
    try:
        found += subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout.split()
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))   # no packet is sent; just picks the outgoing interface
            found.append(s.getsockname()[0])
    except OSError:
        pass
    out = []
    for a in found:
        if re.fullmatch(r"\d+\.\d+\.\d+\.\d+", a) and not a.startswith(("127.", "169.254.")) and a not in out:
            out.append(a)
    return out or [socket.gethostname()]


def user_name():
    try:
        return getpass.getuser()
    except Exception:
        return "pi"


def self_check(port, chooser):
    """Make sure the server answers on this computer before sending anyone to it."""
    url = "http://127.0.0.1:%d%smap/config.js" % (port, chooser.base)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(urllib.request.Request(url, headers={"Host": "127.0.0.1:%d" % port}), timeout=5) as r:
            return r.status == 200
    except OSError:
        return False


def ask(question, default="n"):
    try:
        answer = input(question).strip().lower()
    except EOFError:
        return default
    return answer or default


def choose(config_dict, skin_dir, host=None, port=DEFAULT_PORT, open_browser=True,
           timeout=1800, out=print):
    """Show the map and wait. Returns the saved selection, or None if skipped."""
    chooser = Chooser(config_dict, skin_dir)
    desktop = has_desktop()
    interactive = sys.stdin.isatty()

    if host is None:
        host = "127.0.0.1"
        if not desktop and interactive:
            out("There is no desktop on this computer, so the map has to be opened from another one.")
            if ask("Make the map reachable from other computers on your network while you choose? [y/N] ") == "y":
                host = "0.0.0.0"
    port = chooser.serve(host, port)
    local_url = "http://localhost:%d%smap/" % (port, chooser.base)

    out("")
    addresses = lan_addresses()
    tunnel = "    ssh -L %d:localhost:%d %s@%s" % (port, port, user_name(), addresses[0])
    if not self_check(port, chooser):
        out("Warning: the map server on port %d is not answering on this computer." % port)
    if host == "0.0.0.0":
        out("Open this link in a browser on another computer on your network:")
        out("    http://%s:%d%smap/" % (addresses[0], port, chooser.base))
        if len(addresses) > 1:
            out("If it doesn't load, this computer also has these addresses:")
            for a in addresses[1:]:
                out("    http://%s:%d%smap/" % (a, port, chooser.base))
        out("If none of them load (a firewall, or macOS blocking your browser from the local")
        out("network), use an SSH tunnel instead. On your own computer run")
        out(tunnel)
        out("and, while that stays open, open this link there:")
        out("    " + local_url)
    elif desktop and open_browser and webbrowser.open(local_url):
        out("The map has opened in your browser. If it didn't, open this link:")
        out("    " + local_url)
    elif desktop:
        out("Open this link in your browser:")
        out("    " + local_url)
    else:
        out("On your own computer, open an SSH tunnel:")
        out(tunnel)
        out("and, while that stays open, open this link there:")
        out("    " + local_url)
    out("")
    out("Choose your areas, then press 'Save to WeeWX' on the map.")

    skipped = threading.Event()
    if interactive:
        out("(Or press Enter here to skip; you can run this again later.)")

        def wait_for_enter():
            try:
                sys.stdin.readline()
            except (OSError, ValueError):
                return
            skipped.set()
        threading.Thread(target=wait_for_enter, daemon=True).start()

    deadline = time.time() + timeout
    try:
        while not chooser.saved.is_set() and not skipped.is_set() and time.time() < deadline:
            chooser.saved.wait(0.3)
    except KeyboardInterrupt:
        out("")
    chooser.stop()
    if chooser.result:
        out("Saved: " + describe(chooser.result, chooser.index))
    return chooser.result


# ----------------------------------------------------------------------------- run by hand

def save_config(config, path):
    backup = "%s.%s" % (path, time.strftime("%Y%m%d%H%M%S"))
    shutil.copy2(path, backup)
    config.write()
    return backup


def main(argv=None):
    weewx_root = os.path.dirname(HERE)
    p = argparse.ArgumentParser(description="Choose MeteoAlarm warning areas for WeeWX on a map.")
    p.add_argument("--config", default=os.path.join(weewx_root, "weewx.conf"), help="weewx.conf to update")
    p.add_argument("--skin-dir", default=os.path.join(weewx_root, "skins", "Meteoalarm"),
                   help="the installed Meteoalarm skin (for the map and area outlines)")
    p.add_argument("--host", help="address to listen on (default this computer only)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--no-browser", action="store_true", help="print the link instead of opening a browser")
    args = p.parse_args(argv)

    try:
        import configobj
    except ImportError:
        sys.exit("This needs the configobj module that comes with WeeWX. Run it with WeeWX's Python, "
                 "e.g. ~/weewx-venv/bin/python3 %s" % os.path.abspath(__file__))
    if not os.path.isfile(args.config):
        sys.exit("Cannot find weewx.conf at %s; use --config." % args.config)
    config = configobj.ConfigObj(args.config, encoding="utf-8", interpolation=False, file_error=True)

    print("Please select your location(s) from the map.")
    sel = choose(config, args.skin_dir, host=args.host, port=args.port, open_browser=not args.no_browser)
    if not sel:
        print("Nothing changed.")
        return 1
    apply_selection(config, sel)
    backup = save_config(config, args.config)
    print("Updated %s (previous version kept as %s)." % (args.config, backup))
    print("Restart WeeWX to use the new areas, e.g.  sudo systemctl restart weewx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
