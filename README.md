# CityFlow: Street Closure Impact AI

CityFlow measures **current vehicle occupancy** in a selected polygonal area of a traffic-camera video. It detects cars, motorcycles, buses, and trucks; tracks them across consecutive frames; and counts the currently visible tracked IDs whose bounding-box centers are inside the polygon. The alert is based only on the current in-area vehicle total. This is a live congestion-risk measurement prototype, not a complete city traffic simulator and it does not model rerouting after a street closure.

## Recommended Folder Structure

Keep the existing Python 3.14 virtual environment one level above the project:

```text
C:\Users\fjoll\OneDrive\Desktop\Hackathon\
|-- .venv\
`-- CityFlow\
    |-- traffic_counter.py
    |-- detect_cars.py
    |-- requirements.txt
    |-- README.md
    |-- yolo11m.pt
    |-- yolo11n.pt                 Downloaded automatically when needed
    |-- tests\
    `-- results\                  Created automatically
        `-- gjirafa_cam_YYYYMMDD_HHMMSS\
            |-- annotated.mp4
            |-- live_counts.csv
            |-- vehicle_tracks.csv
            |-- alerts.csv
            `-- summary.json
```

The provided `yolo11m.pt` remains available to `detect_cars.py`. `traffic_counter.py` defaults to the lighter pretrained `yolo11n.pt`; Ultralytics downloads it on first use if it is not already present. The downloaded weights are ignored by Git.

## Exact PowerShell Setup

Run these commands in order. The activation path is absolute because `.venv` is outside `CityFlow`:

```powershell
cd "C:\Users\fjoll\OneDrive\Desktop\Hackathon"
& "C:\Users\fjoll\OneDrive\Desktop\Hackathon\.venv\Scripts\Activate.ps1"
cd .\CityFlow
python --version
where.exe python
python -c "import torch; print('Torch:', torch.__version__); print('CUDA:', torch.cuda.is_available())"
python -c "from ultralytics import YOLO; print('Ultralytics works')"
Test-Path .\traffic_counter.py
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
```

`where.exe python` is used rather than `where` because PowerShell defines `where` as an alias. The first result should be `C:\Users\fjoll\OneDrive\Desktop\Hackathon\.venv\Scripts\python.exe`. CUDA may report `False`; CPU inference is supported and selected automatically. If PowerShell blocks activation, run this in the current terminal and activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
& "C:\Users\fjoll\OneDrive\Desktop\Hackathon\.venv\Scripts\Activate.ps1"
```

Dependencies are installed with `python -m pip`, not standalone command-line executables. `supervision` is included for the existing `detect_cars.py`; the occupancy counter uses Ultralytics tracking, OpenCV, NumPy, and ByteTrack's `lap` dependency.

## Run the Live Stream

From the `CityFlow` directory, the camera name is the second positional argument:

```powershell
python .\traffic_counter.py "https://gjirafa-video-live.gjirafa.net/gjvideo-slow/jrl-15u-0vp-6r8/tracks-v1a1/mono.ts.m3u8" gjirafa_cam --show
```

`--show` opens the preview. Press `q` to stop. Without a preview, press `Ctrl+C`; the program finishes the current frame and writes the final summary. The stream is opened frame-by-frame, and a failed HLS read triggers up to five reconnection attempts with a three-second delay by default.

## Run a Local MP4

```powershell
python .\traffic_counter.py ".\videos\traffic.mp4" local_cam --show
```

The MP4 must exist. Both source and camera name may also be supplied with the supported defaults/options (`--camera` can be used instead of the positional camera name).

## Configure the Monitored Area

The default polygon is defined near the top of `traffic_counter.py`:

```python
ROI_POLYGON = [(100, 200), (1100, 200), (1200, 700), (50, 700)]
ALERT_TOTAL_VEHICLES = 15
ALERT_COOLDOWN_SECONDS = 30.0
```

Change `ROI_POLYGON` to pixel coordinates that outline the road in your camera image. Every point must fit the video frame. You can override the polygon on the command line using at least three `x,y` pairs:

```powershell
python .\traffic_counter.py ".\videos\traffic.mp4" local_cam --roi 100,200,1100,200,1200,700,50,700 --show
```

The program uses the **center of each bounding box** for ROI membership. At every frame it rebuilds the current in-area tracker-ID map; an ID no longer visible or whose center leaves the polygon is removed from the current count. There is no line crossing, direction, or cumulative-flow count.

Useful options:

```powershell
python .\traffic_counter.py --help
python .\traffic_counter.py ".\videos\traffic.mp4" local_cam --threshold 15 --model yolo11n.pt --conf 0.35 --output-dir results --show
```

`--threshold` sets the current occupancy alert threshold (default 15); `--conf` changes YOLO's detection confidence (default 0.35); `--csv-interval` controls current-count snapshots (default one second); `--model` selects YOLO weights; and `--output-dir` sets the output root. `--device auto` uses CUDA if available and otherwise CPU.

## What the Display and CSVs Contain

The preview and annotated video draw the ROI polygon, class/ID/confidence labels, and current counts for cars, motorcycles, buses, trucks, and the total. Vehicles inside the ROI are green normally and change to a distinct alert color while an alert is active. Detections outside the ROI are drawn gray. A large red `CONGESTION ALERT: N VEHICLES IN AREA` banner appears only while the current in-ROI total meets or exceeds the threshold.

Each run makes a timestamped directory under `results` with:

- `annotated.mp4`: processed video, boxes, labels, ROI, current occupancy, and alert banner.
- `live_counts.csv`: periodic snapshots with timestamp, frame number, class counts, current total, alert state, and threshold.
- `vehicle_tracks.csv`: one row for each visible tracked vehicle per frame, including tracker ID, class, confidence, bounding box, center, and `inside_roi`.
- `alerts.csv`: `ALERT_STARTED`, cooldown `ALERT_REMINDER`, and `ALERT_CLEARED` events with current total and threshold.
- `summary.json`: source, camera/model/tracker, times, frames processed, maximum concurrent total and per-class occupancy, alert threshold/count, and output paths.

The alert condition is exactly `current_total_vehicles_in_roi >= threshold`. An alert row is written on the NORMAL-to-ALERT transition and then no more often than the configured cooldown. A clear event is written when occupancy falls below the threshold.

## Inspect Results After the Run

Wait until inference has stopped successfully before importing the CSV. From `CityFlow`:

```powershell
Get-ChildItem .\results -Recurse
$run = Get-ChildItem .\results -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$liveCounts = Join-Path $run.FullName 'live_counts.csv'
if (Test-Path $liveCounts) { Import-Csv $liveCounts | Format-Table -AutoSize } else { Write-Warning "CSV was not created: $liveCounts" }
Get-Content (Join-Path $run.FullName 'summary.json') -Raw
```

Deactivate the parent environment when finished:

```powershell
deactivate
```

## Tests

The focused tests do not load YOLO or access a camera/stream:

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\traffic_counter.py .\detect_cars.py .\tests\test_project_helpers.py
```

## Troubleshooting and Limitations

- **`can't open file ... traffic_counter.py`**: first check `(Get-Location).Path`. Change to the project directory with `cd "C:\Users\fjoll\OneDrive\Desktop\Hackathon\CityFlow"`; do not prefix the script with another `CityFlow\` when already inside it.
- **`ModuleNotFoundError` for Torch or Ultralytics**: activate the parent `.venv` using the absolute activation command above, then run `python -m pip install -r .\requirements.txt`. Confirm `where.exe python` lists that environment first.
- **Stream cannot open or returns no frames**: verify the `.m3u8` URL is reachable. HLS requires an OpenCV build with FFmpeg support. The program retries a limited number of times and reports the last open/read failure; the remote server/network may deny or interrupt access.
- **ROI is outside the frame**: adjust `ROI_POLYGON` or pass `--roi` with coordinates matching the camera's actual resolution.
- **No vehicles counted**: detections are filtered to COCO car, motorcycle, bus, and truck classes, and only tracked bounding-box centers inside the ROI count. Check ROI placement and try adjusting `--conf`.
- **Tracker IDs change**: IDs persist across consecutive frames while ByteTrack can match the vehicle, but may change after long occlusion, detection failure, stream interruption, or when a vehicle leaves and returns. IDs are object-track labels for this video session, not identities for people, drivers, or license plates.
- **Missed detections**: a generic COCO model may miss vehicles in darkness, poor weather, unusual camera angles, or tiny distant scenes. Fine-tuning on representative local traffic-camera images could improve accuracy later.
- **Slow inference or CUDA is false**: the script uses CPU automatically. Try a smaller `--imgsz`, or configure a compatible CUDA-enabled PyTorch build for an NVIDIA GPU.

This prototype reports live occupancy and congestion risk in one monitored street area. It does not yet simulate what routes vehicles take when a street is closed; those occupancy measurements can later feed a map/scenario dashboard.