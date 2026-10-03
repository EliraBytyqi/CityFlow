# CityFlow: Street Closure Impact AI

CityFlow measures traffic from a camera video. It detects and tracks cars, motorcycles, buses, and trucks, then counts each tracked vehicle once when it crosses a counting line or first enters a polygon zone. The saved counts and event data are a computer-vision baseline for later street-closure scenario comparisons; this prototype does not simulate rerouting or predict traffic on other streets.

## Recommended Windows Folders

Keep using the Python 3.14 virtual environment already created one directory above this project:

```text
C:\Users\fjoll\OneDrive\Desktop\Hackathon\
|-- .venv\                       Existing Python 3.14 environment
|-- CityFlow\
    |-- traffic_counter.py
    |-- detect_cars.py            Existing occupancy script
    |-- requirements.txt
    |-- README.md
    |-- yolo11m.pt                Existing model used by detect_cars.py
    |-- yolo11n.pt                Downloaded automatically for traffic_counter.py
    |-- tests\
    `-- results\                 Created automatically; each run gets its own folder
```

From the `CityFlow` directory, the correct activation command for the existing environment is **`..\.venv\Scripts\Activate.ps1`**. The space in the malformed `..\ .venv` form must not be present. A project-local `.venv` is not needed; keeping the already-created parent environment avoids a second large PyTorch install.

## Setup

Open PowerShell and run:

```powershell
Set-Location "$HOME\OneDrive\Desktop\Hackathon\CityFlow"
..\.venv\Scripts\Activate.ps1
python --version
python -m pip install --upgrade pip
python -m pip install -r .\requirements.txt
```

If activation is blocked by PowerShell policy, allow scripts for this PowerShell process only, then activate:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
..\.venv\Scripts\Activate.ps1
```

The requirements install Ultralytics, OpenCV, and NumPy. Ultralytics installs the required PyTorch dependency. Run the commands from the activated environment; do not rely on `yolo.exe`, `torchrun.exe`, or other scripts being on PATH. If dependencies were installed into a different Python environment, installing from this activated terminal puts them in the correct `.venv`.

## Verify Python and Packages

Run these checks before inference:

```powershell
python --version
where.exe python
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
python -c "from ultralytics import YOLO; print('Ultralytics works')"
Test-Path .\traffic_counter.py
(Get-Location).Path
```

The first command should report Python 3.14.x. The first path from `where.exe python` should be `...\Hackathon\.venv\Scripts\python.exe`, and `Test-Path` should return `True`. `torch.cuda.is_available()` may be `False`; that is okay because the script automatically uses CPU when CUDA is unavailable. If `where.exe python` lists a different Python first, reactivate the correct environment.

## Run a Camera Stream

The requested HLS URL is the default source, so this command works without typing it again:

```powershell
python .\traffic_counter.py --camera gjirafa_cam --show
```

Equivalent explicit URL command:

```powershell
python .\traffic_counter.py "https://gjirafa-video-live.gjirafa.net/gjvideo-slow/jrl-15u-0vp-6r8/tracks-v1a1/mono.ts.m3u8" --camera gjirafa_cam --show
```

`--show` opens a preview; press `q` in the preview to stop and finish the summary. Without the preview, press `Ctrl+C` to request a clean stop after the current frame. HLS connection attempts are retried (five attempts by default, three seconds apart). For a slow network, increase `--reconnect-wait` or `--reconnect-attempts`.

## Run a Local Video

Pass an existing MP4 path instead of the stream URL:

```powershell
python .\traffic_counter.py "C:\path\to\traffic_clip.mp4" --camera local_demo --show
```

Supported local file extensions are `.mp4`, `.avi`, `.mov`, and `.mkv`. Local videos run until the file ends or you stop the preview with `q`.

## Counting Line or Polygon Zone

By default, a horizontal line is placed at 60% of the video frame height. Each persistent tracker ID counts once, on its first crossing in either direction:

```powershell
python .\traffic_counter.py --camera gjirafa_cam --line-position 0.60 --direction any --show
```

`--direction down` counts only top-to-bottom motion; `--direction up` counts only bottom-to-top motion. To count first entry into a polygon instead, give at least three `x,y` points in video-pixel coordinates:

```powershell
python .\traffic_counter.py --camera gjirafa_cam --zone 100,250,700,250,760,650,80,650 --show
```

Coordinates must fit the input frame. To edit the default setup in code, change `DEFAULT_LINE_POSITION` near the top of `traffic_counter.py`; alternatively use the command-line flags above. Polygon mode replaces line mode.

## Tracking, Labels, and Alerts

The script calls Ultralytics `model.track()` once per frame with `persist=True` and `tracker="bytetrack.yaml"`. If `yolo11n.pt` is not already beside the script, Ultralytics downloads the named pretrained weights on first run; the downloaded file is ignored by Git. It filters COCO IDs 2, 3, 5, and 7 (car, motorcycle, bus, truck). The preview/output labels include class, tracker ID, and detection confidence. Persistent IDs are meaningful across consecutive frames in one running video stream; one still image cannot establish persistent identity.

The on-video counters are unique vehicles that crossed the line/entered the zone, grouped by vehicle class, plus the recent vehicles-per-minute rate and alert status. `--alert-total-vehicles` defaults to 45 unique counted IDs and `--alert-vehicles-per-minute` defaults to 45. Set either threshold to `0` to disable that trigger. For example:

```powershell
python .\traffic_counter.py --camera gjirafa_cam --alert-total-vehicles 30 --alert-vehicles-per-minute 20 --show
```

Alerts are logged when the alert state starts and then at most once per `--alert-cooldown` seconds while it remains active (30 seconds by default). The annotation includes a red `CONGESTION ALERT` banner while a threshold is active.

## Output Files

Each run creates a timestamped directory under `CityFlow\results`, for example:

```text
results\gjirafa_cam_20261003_142233\
|-- annotated.mp4
|-- vehicle_events.csv
|-- summary.json
`-- alerts.csv
```

- `annotated.mp4`: processed video with boxes, class/ID/confidence labels, counters, line or zone, and alert banner.
- `vehicle_events.csv`: per-frame detection rows and event type (`detection`, `line_crossing_down`, `line_crossing_up`, or `zone_entry`), with timestamp, frame, tracker ID, class, confidence, and box coordinates.
- `summary.json`: final frame count, unique counted IDs, totals per vehicle class, alert thresholds, tracker/model, and device.
- `alerts.csv`: alert timestamp, frame, current total, recent rate, and threshold reason. The file is created with a header even when no alert triggers.

After inference finishes, find the latest folder and check files before reading CSV data:

```powershell
$run = Get-ChildItem .\results -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$run.FullName
Get-ChildItem $run.FullName
$events = Join-Path $run.FullName 'vehicle_events.csv'
if (Test-Path $events) { Import-Csv $events | Select-Object -First 20 | Format-Table -AutoSize } else { Write-Warning "Event CSV does not exist: $events" }
Get-Content (Join-Path $run.FullName 'summary.json') -Raw
```

## Tests (No Model or Camera Needed)

From `CityFlow`, run:

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\traffic_counter.py .\detect_cars.py .\tests\test_project_helpers.py
```

The tests cover source parsing, line crossings, polygon geometry, and existing helper behavior without downloading a model or contacting a stream.

## Troubleshooting

- **`ModuleNotFoundError: torch` or `ultralytics`**: activate the parent environment from `CityFlow` with `..\.venv\Scripts\Activate.ps1`, then run `python -m pip install -r .\requirements.txt`. Confirm the first `where.exe python` result points inside `Hackathon\.venv`.
- **`Error: initialization failed`**: run the import checks above in the same activated terminal. This generic startup failure can come from missing packages, a mismatched Python environment, PyTorch DLL/runtime issues, or an OpenCV video backend; use the first printed traceback/error rather than assuming the URL is the cause.
- **HLS stream fails to open/read**: confirm the URL is reachable in a browser/VLC and remains an `.m3u8` URL. OpenCV needs FFmpeg support for HLS; reinstall the standard `opencv-python` package with `python -m pip install --force-reinstall opencv-python`. The camera/network may block access or expire.
- **`Could not create output video`**: check free disk space and that `results` is writable. MP4 encoding uses OpenCV's `mp4v` codec.
- **Very slow or CUDA unavailable**: CPU inference is supported. Use a smaller `--imgsz` such as 416 to reduce work. CUDA requires a compatible NVIDIA driver and PyTorch build; the script does not require a GPU.
- **Missed or incorrect detections**: a generic COCO model may miss tiny distant vehicles, difficult lighting, occlusions, or unusual camera angles. Later, fine-tune a supported YOLO model with representative local traffic-camera images.
- **Tracker ID changes**: ByteTrack IDs can change after long occlusion, stream interruption, or when a vehicle leaves and later re-enters. The unique crossing/zone counter deduplicates by tracker ID within a run, not by real-world license plate identity.
- **No counts in summary**: detections are not counted just because they appear in frames; a tracked vehicle must cross the configured line or enter the zone. Place the line/zone where target vehicles pass and ensure coordinates fit the frame.