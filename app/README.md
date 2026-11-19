# Desktop app

## Folder layout (the app finds the tracking code by itself)
    Urban_Safety_AI/
        tracking/     <- your existing folder (yolov8m.pt, zones.json, tracker.py ...)
        app/          <- this folder

## Run
    pip install PySide6
    cd app
    python main.py            real use: start empty, open a video in Live Monitoring
    python main.py --demo     fake live events, for showing the screens

## What works
* Live Monitoring: Open Video / Webcam / Pause / Stop, boxes and labels on the video,
  counters, alert feed, event timeline. "Crowded mode" = tiled detection.
* Overview and Risk Events show the real events from the analysis.
* Uses tracking/zones.json (ignore areas, road directions) and tracking/config.py settings.

## Saved runs
Every analysis is saved automatically in `Urban_Safety_AI/data/` (safety.db plus a snapshots folder).
Open an earlier run from the **Saved runs** menu on Risk Events. Click an event in the Live timeline to see it with its snapshot.

## Files
| File | Purpose |
|---|---|
| main.py | starts the app |
| main_window.py | header, sidebar, screen switching |
| live_page.py | Live Monitoring screen |
| analysis.py | runs the video analysis in the background |
| pages.py | Overview, Risk Events, placeholders |
| widgets.py | counter cards, alert feed, line chart, donut, heatmap picture, pipeline strip |
| theme.py | colors and look, measured from the design PDF (change the look here) |
| icons.py, icon_data.py | the outline icons (packed into one file, no folders needed) |
| fake_data.py | event store (real events, saves to the database) + optional demo data |
| database.py | the SQLite database (sessions, events, tracked objects) |

## Next
Risk rules (near miss, braking, lane change, congestion) -> database -> Zone Setup screen ->
heatmap -> PDF report -> priority simulation.
