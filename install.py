# Installer for the weewx-meteoalarm extension.
#
#   weectl extension install weewx-meteoalarm.zip      (WeeWX 5)
#   wee_extension --install weewx-meteoalarm.zip       (WeeWX 4)

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
