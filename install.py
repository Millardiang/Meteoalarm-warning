# Installer for the weewx-meteoalarm extension.
#
#   weectl extension install weewx-meteoalarm.zip      (WeeWX 5)
#   wee_extension --install weewx-meteoalarm.zip       (WeeWX 4)
#
# During installation you are asked to select your location(s) on a map, which
# opens in your browser; your choice is written into weewx.conf. Options, given
# after the zip file name:
#
#   --emma-ids=UK258,UK259   choose areas without the map
#   --polygon="lat,lon ..."  choose a polygon without the map
#   --min-level=2            1 green, 2 yellow, 3 orange, 4 red
#   --no-map                 don't open the map (run meteoalarm-map/choose_areas.py later)
#   --map-host=0.0.0.0       let another computer on your network open the map
#   --map-port=8765

import argparse
import importlib.util
import json
import os
import sys

from weecfg.extension import ExtensionInstaller

# Every file the extension installs. WeeWX also uses this list to uninstall,
# so it must be complete; tools/check_install_files.py verifies it.
FILES = [
    ('bin/user', ['bin/user/meteoalarm.py']),
    ('skins/Meteoalarm', [
        'skins/Meteoalarm/index.html.tmpl',
        'skins/Meteoalarm/meteoalarm-embed.js',
        'skins/Meteoalarm/meteoalarm.css',
        'skins/Meteoalarm/meteoalarm.json.tmpl',
        'skins/Meteoalarm/skin.conf',
        'skins/Meteoalarm/summary.html.tmpl',
    ]),
    ('skins/Meteoalarm/areas', [
        'skins/Meteoalarm/areas/AT.geojson',
        'skins/Meteoalarm/areas/BA.geojson',
        'skins/Meteoalarm/areas/BE.geojson',
        'skins/Meteoalarm/areas/BG.geojson',
        'skins/Meteoalarm/areas/CY.geojson',
        'skins/Meteoalarm/areas/CZ.geojson',
        'skins/Meteoalarm/areas/DE.geojson',
        'skins/Meteoalarm/areas/DK.geojson',
        'skins/Meteoalarm/areas/EE.geojson',
        'skins/Meteoalarm/areas/EI.geojson',
        'skins/Meteoalarm/areas/ES.geojson',
        'skins/Meteoalarm/areas/FI.geojson',
        'skins/Meteoalarm/areas/FR.geojson',
        'skins/Meteoalarm/areas/GR.geojson',
        'skins/Meteoalarm/areas/HR.geojson',
        'skins/Meteoalarm/areas/HU.geojson',
        'skins/Meteoalarm/areas/IE.geojson',
        'skins/Meteoalarm/areas/IL.geojson',
        'skins/Meteoalarm/areas/IS.geojson',
        'skins/Meteoalarm/areas/IT.geojson',
        'skins/Meteoalarm/areas/LT.geojson',
        'skins/Meteoalarm/areas/LU.geojson',
        'skins/Meteoalarm/areas/LV.geojson',
        'skins/Meteoalarm/areas/MD.geojson',
        'skins/Meteoalarm/areas/ME.geojson',
        'skins/Meteoalarm/areas/MK.geojson',
        'skins/Meteoalarm/areas/MT.geojson',
        'skins/Meteoalarm/areas/NL.geojson',
        'skins/Meteoalarm/areas/NO.geojson',
        'skins/Meteoalarm/areas/PL.geojson',
        'skins/Meteoalarm/areas/PT.geojson',
        'skins/Meteoalarm/areas/RO.geojson',
        'skins/Meteoalarm/areas/RS.geojson',
        'skins/Meteoalarm/areas/SE.geojson',
        'skins/Meteoalarm/areas/SI.geojson',
        'skins/Meteoalarm/areas/SK.geojson',
        'skins/Meteoalarm/areas/aliases.json',
        'skins/Meteoalarm/areas/index.json',
    ]),
    ('skins/Meteoalarm/icons', [
        'skins/Meteoalarm/icons/meteoalarm_000.svg',
        'skins/Meteoalarm/icons/meteoalarm_1.svg',
        'skins/Meteoalarm/icons/meteoalarm_10.svg',
        'skins/Meteoalarm/icons/meteoalarm_12.svg',
        'skins/Meteoalarm/icons/meteoalarm_13.svg',
        'skins/Meteoalarm/icons/meteoalarm_2.svg',
        'skins/Meteoalarm/icons/meteoalarm_3.svg',
        'skins/Meteoalarm/icons/meteoalarm_4.svg',
        'skins/Meteoalarm/icons/meteoalarm_5.svg',
        'skins/Meteoalarm/icons/meteoalarm_6.svg',
        'skins/Meteoalarm/icons/meteoalarm_7.svg',
        'skins/Meteoalarm/icons/meteoalarm_8.svg',
        'skins/Meteoalarm/icons/meteoalarm_9.svg',
        'skins/Meteoalarm/icons/meteoalarm_info.svg',
    ]),
    ('meteoalarm-map', [
        'meteoalarm-map/choose_areas.py',
        'meteoalarm-map/index.html',
    ]),
    ('skins/Meteoalarm/map', [
        'skins/Meteoalarm/map/index.html.tmpl',
        'skins/Meteoalarm/map/map.css',
        'skins/Meteoalarm/map/map.js',
    ]),
]


def loader():
    return MeteoalarmInstaller()


class MeteoalarmInstaller(ExtensionInstaller):
    def __init__(self):
        super().__init__(
            version="4.0.0",
            name="meteoalarm",
            description="Weather warnings from www.meteoalarm.org, with an area picker map.",
            author="Ian Millard",
            config={
                "Meteoalarm": {
                    "emma_ids": "",
                    "polygon": "",
                    "min_level": "2",
                    "cache_max_age": "300",
                },
                "StdReport": {
                    "Meteoalarm": {
                        "skin": "Meteoalarm",
                        "HTML_ROOT": "meteoalarm",
                        "enable": "true",
                    },
                },
            },
            files=FILES,
        )
        self.options = self._parse([])

    @staticmethod
    def _parse(args):
        p = argparse.ArgumentParser(prog="weectl extension install <zip>", add_help=False)
        p.add_argument("--emma-ids", default="")
        p.add_argument("--polygon", default="")
        p.add_argument("--min-level", default="2")
        p.add_argument("--no-map", action="store_true")
        p.add_argument("--map-host", default=None)
        p.add_argument("--map-port", type=int, default=8765)
        options, _unknown = p.parse_known_args(args)
        return options

    def process_args(self, args):
        self.options = self._parse(args or [])

    def configure(self, engine):
        """Ask for the warning areas: from the command line, or on the map."""
        if getattr(engine, "dry_run", False):
            return False
        weewx_root = engine.root_dict["WEEWX_ROOT"]
        tool = os.path.join(weewx_root, "meteoalarm-map", "choose_areas.py")
        later = "To choose your areas later, run:  %s %s" % (sys.executable or "python3", tool)
        keep = sys.dont_write_bytecode
        sys.dont_write_bytecode = True   # no __pycache__ left in meteoalarm-map to block uninstall
        try:
            spec = importlib.util.spec_from_file_location("meteoalarm_choose_areas", tool)
            chooser = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(chooser)
        except (OSError, ImportError, SyntaxError) as e:
            print("Could not load the area chooser (%s). %s" % (e, later))
            return False
        finally:
            sys.dont_write_bytecode = keep

        opts, config_dict = self.options, engine.config_dict
        skin_dir = os.path.join(weewx_root, "skins", "Meteoalarm")
        if opts.emma_ids or opts.polygon:
            try:
                with open(os.path.join(skin_dir, "areas", "index.json"), encoding="utf-8") as fh:
                    known = json.load(fh)
            except (OSError, ValueError):
                known = None
            try:
                sel = chooser.clean_selection({"emma_ids": opts.emma_ids, "polygon": opts.polygon,
                                               "min_level": opts.min_level}, known)
            except ValueError as e:
                print("Ignoring the area options: %s. %s" % (e, later))
                return False
            chooser.apply_selection(config_dict, sel)
            print("Warning areas set to " + chooser.describe(sel))
            return True
        if opts.no_map:
            print(later)
            return False
        if not sys.stdin.isatty():
            print("Not running in a terminal, so the area map was not opened. " + later)
            return False

        print()
        print("Please select your location(s) from the map.")
        try:
            sel = chooser.choose(config_dict, skin_dir,
                                 host=opts.map_host, port=opts.map_port)
        except (OSError, RuntimeError) as e:
            print("Could not start the area map: %s. %s" % (e, later))
            return False
        if not sel:
            print("No areas chosen. " + later)
            return False
        chooser.apply_selection(config_dict, sel)
        return True
