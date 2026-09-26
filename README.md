weewx-meteoalarm
================

Weather warnings from [**www.meteoalarm.org**](https://www.meteoalarm.org/) for your [WeeWX](https://weewx.com/) station, covering the countries that take part in [**EUMETNET**](https://www.eumetnet.eu.org/). The countries/areas in colour are available.

![METEOalarm countries](./meteoalarm-coverage-area.png)

The extension adds:

* a **warnings page** (`meteoalarm/index.html`) with each warning in every language the national service publishes;
* a **summary box** (`meteoalarm/summary.html`) to show on your main site;
* a **JSON file** (`meteoalarm/meteoalarm.json`) for other programs;
* an **area picker map**, shown during installation, where you click MeteoAlarm areas or draw your own polygon;
* the **`$meteoalarm` tag**, so any skin can show the warnings in its own templates.

It is a Python rewrite of Ken True's `get-meteoalarm-warning-inc.php`; no PHP is needed.

Requirements
------------

WeeWX 5 (WeeWX 4.x should also work) on Python 3.7 or later. Nothing else to install.

Installing
----------

```sh
weectl extension install https://github.com/Millardiang/meteoalarm-warning/archive/refs/heads/main.zip
```

(On WeeWX 4 use `wee_extension --install` with a downloaded copy of the zip.)

The installer copies the area map into your WeeWX folder (`~/weewx-data/meteoalarm-map/` on a standard WeeWX 5 install) and then asks:

```
Please select your location(s) from the map.
The map has opened in your browser. If it didn't, open this link:
    http://localhost:8765/s/…/map/
Choose your areas, then press 'Save to WeeWX' on the map.
(Or press Enter here to skip; you can run this again later.)
```

The map starts at your station (from `[Station]` in `weewx.conf`). Pick your areas or draw a polygon (see below), then press **Save to WeeWX**. Your choice goes straight into the `[Meteoalarm]` section of `weewx.conf` and the install finishes. Restart WeeWX; the warning pages appear after the next report cycle in `public_html/meteoalarm/`.

**No desktop on the WeeWX computer** (for example a Raspberry Pi you reach over SSH): the installer notices and offers two ways in.

* Answer **y** to make the map reachable from other computers on your network while you choose. It prints a link such as `http://192.168.1.20:8765/s/…/map/` to open on your laptop or phone.
* Or answer **n** and use the SSH tunnel it prints (`ssh -L 8765:localhost:8765 pi@192.168.1.20`), then open the `localhost` link on your own computer.

The map's small web server runs only until you save or skip. The link contains a random code, so nobody else on the network can change your settings.

**Installing without the map.** Give the areas on the command line, after the zip:

```sh
weectl extension install weewx-meteoalarm.zip --emma-ids=UK258,UK259 --min-level=2
weectl extension install weewx-meteoalarm.zip --polygon="51.3,-0.5 51.7,-0.5 51.7,0.2 51.3,0.2"
weectl extension install weewx-meteoalarm.zip --no-map          # choose later
```

Other options: `--map-host=0.0.0.0` (reachable on your network without asking), `--map-port=N`. When the install isn't run from a terminal (a script, Ansible, and so on) the map is skipped automatically.

Changing your areas later
-------------------------

Run the chooser again with WeeWX's Python. It opens on your current settings:

```sh
~/weewx-venv/bin/python3 ~/weewx-data/meteoalarm-map/choose_areas.py
```

(With a Debian/RPM package install: `sudo /usr/bin/python3 /etc/weewx/meteoalarm-map/choose_areas.py`.) It keeps a dated backup of `weewx.conf` before saving. Then restart WeeWX. It accepts the same `--host`, `--port` and `--no-browser` options, and `--config` for a `weewx.conf` somewhere else.

The report also publishes the map at `meteoalarm/map/index.html` on your website. There it can't save; it shows the settings to paste into `weewx.conf` instead, for example:

```ini
[Meteoalarm]
    emma_ids = DK002, DK004
    polygon = "57.4272,9.4537 57.3976,10.8820 56.8309,10.8270 56.8610,9.5087 57.4272,9.4537"
    min_level = 2
```

On either map:

* **Pick areas:** click areas to add or remove them, or search by name or EMMA code (e.g. `UK258`, `Wien`). *Near me* jumps to your location.
* **Draw polygon:** click to place corners; click the first corner, double-click or press *Finish* to close it.

### What a polygon does

A polygon (CAP style: `lat,lon` pairs separated by spaces) is used in two ways:

1. Every MeteoAlarm area it touches is watched, as if you had listed its EMMA code. This is worked out on your station from the area outlines the skin ships with.
2. Warnings whose own outline (a CAP `polygon` or `circle`) crosses your polygon are shown too, even if they don't name one of your areas. Some services, such as the UK Met Office, draw their warnings this way.

You can use `emma_ids`, `polygon`, or both.

### UK and Switzerland

There are no public outlines for the UK and Swiss MeteoAlarm areas, so these two countries aren't drawn on the map. You can still pick their areas by searching (they're marked *no outline*). A polygon drawn over them still catches warnings that come with their own outline. If you have outline data, see *Rebuilding the area data* below.

Settings
--------

In `[Meteoalarm]` in `weewx.conf`. A `[Meteoalarm]` section in a skin's `skin.conf` overrides these for that skin only.

| Setting | Default | Meaning |
| --- | --- | --- |
| `emma_ids` | *(empty)* | EMMA codes to watch, comma separated |
| `polygon` | *(empty)* | Polygon as `"lat,lon lat,lon ..."` |
| `min_level` | `2` | Lowest level shown: 1 green, 2 yellow, 3 orange, 4 red |
| `cache_max_age` | `300` | Seconds before the feeds are downloaded again |
| `timeout` | `30` | Seconds to wait for each feed |
| `date_format` | `%Y-%m-%d` | [strftime](https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes) format for dates |
| `time_format` | `%H:%M` | strftime format for times |
| `cache_file` | `<SQLITE_ROOT>/meteoalarm-cache.json` | Where downloaded warnings are kept |
| `areas_dir` | `<SKIN_ROOT>/Meteoalarm/areas` | Area names, outlines and geocode aliases |

Warnings are downloaded while reports are generated, in WeeWX's report thread, and at most once every `cache_max_age` seconds. Each country you watch is one download from meteoalarm.org.

Showing warnings on your main site
----------------------------------

### Option 1: the summary box (any skin, no template changes)

Add this where you want the box, for example in the Seasons skin's `index.html.tmpl`:

```html
<div data-meteoalarm-src="meteoalarm/summary.html"></div>
<script src="meteoalarm/meteoalarm-embed.js" defer></script>
```

The script loads the box, fixes up its links, and refreshes it every five minutes.

### Option 2: the `$meteoalarm` tag in your own templates

Add the search list extension to the other skin's `skin.conf`:

```ini
[CheetahGenerator]
    search_list_extensions = user.meteoalarm.MeteoalarmSearchList
```

Then, for example:

```html
#if $meteoalarm.has_alerts
  #for $a in $meteoalarm.alerts
    <p style="border-left: 6px solid $a.color">
      <img src="meteoalarm/icons/$a.icon" width="24" alt=""> $a.level_name $a.title,
      $a.onset_text &ndash; $a.expires_text
    </p>
  #end for
#end if
```

Everything text-like is already HTML-escaped. Available tags:

| Tag | Value |
| --- | --- |
| `$meteoalarm.configured` | true if any areas or a polygon are set |
| `$meteoalarm.has_alerts`, `$meteoalarm.count` | whether there are warnings at `min_level` or above, and how many |
| `$meteoalarm.alerts` | list of warnings, most severe first (see below) |
| `$meteoalarm.max_level`, `$meteoalarm.max_color` | highest level in force (including below `min_level`) and its colour |
| `$meteoalarm.summary` | warnings grouped by area: `area`, `country`, `icons` (`color`, `icon`, `title`, `anchor`, `level_name`) |
| `$meteoalarm.area_list` | watched areas: `code`, `name` |
| `$meteoalarm.updated` | when the warnings were last downloaded |
| `$meteoalarm.min_level`, `$meteoalarm.min_level_name` | the `min_level` setting |
| `$meteoalarm.json` | the warnings as JSON |

Each warning in `$meteoalarm.alerts` has: `level` (1-4), `level_name`, `severity`, `color`, `advice`, `title`, `event_type`, `icon` (file name in `icons/`), `anchor` (id on the warnings page), `onset_text`, `expires_text`, `sent_text` (plus `onset`, `expires`, `sent` as datetimes), `sender_name`, `origin_url`, `web`, `areas` (`code`, `desc`, `note`, `country`) and `languages` (`code`, `name`, `headline`, `description`, `instruction`).

Testing a configuration
-----------------------

The module can be run on its own to see what it would show:

```sh
python3 bin/user/meteoalarm.py --emma-ids UK258,DK002
python3 bin/user/meteoalarm.py --polygon "51.4,-0.2 51.6,-0.2 51.6,0.1 51.4,0.1"
```

Add `--json` for the JSON document. `tests/make_fixtures.py` writes sample feeds to `tests/feeds/`; pass `--test-file tests/feeds` to use them instead of downloading.

Rebuilding the area data
------------------------

`skins/Meteoalarm/areas/` holds simplified area outlines (one file per country), an index of names, and the NUTS/FIPS→EMMA alias table. They are built with:

```sh
pip install shapely
python3 tools/build_areas.py geocodes.json [more-areas.geojson ...]
```

`geocodes.json` is the MeteoAlarm area file shipped in the MIT-licensed [`meteoalarm`](https://github.com/NiklasJordan/meteoalarm) Python package (`src/meteoalarm/assets/geocodes.json`). Extra GeoJSON files with the same properties (`code`, `country`, `name`, `type: "EMMA_ID"`) add or replace areas; that is how UK or Swiss outlines could be added. Names for areas without outlines come from `data/meteoalarm-codenames.json`.

Credits
-------

* Original PHP script by Ken True, [saratoga-weather.org](https://saratoga-weather.org/), adapted with permission from wrnWarningEU-CAP.php by Wim van der Kuil, [pwsdashboard.com](https://pwsdashboard.com/).
* Warning data © EUMETNET-METEOalarm and the respective National Meteorological Services, used per the [meteoalarm.org terms and conditions](https://meteoalarm.org/page/terms-and-conditions).
* Area outlines from the [`meteoalarm`](https://github.com/NiklasJordan/meteoalarm) package by Niklas Jordan (MIT licence), simplified.
* Map by [Leaflet](https://leafletjs.com/), tiles © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.

Licensed under the GNU General Public License v3 (see `LICENSE`).
