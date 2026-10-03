# CITYFLOW — LIVE CAMERA + CLOSURE MODEL WALKTHROUGH

## 1. Start with a real feed

Open **Live cameras** and choose **Fushë Kosovë** (or another configured Kosovo location). The backend opens the HLS feed, runs the YOLO detector, and returns annotated frames. Point out the labeled boxes and the per-frame class counts. The model status changes to **Inference running** after the first prediction arrives.

The configured feeds are Fushë Kosovë, Ulpianë, Bregu i Diellit, Pejton, Magjistralja Vushtrri–Mitrovicë, and Ortakoll: Wesley Clark, Prizren. Ulpianë and Bregu i Diellit have separate URLs now.

## 2. Explain the data clearly

Open **Traffic patterns** to see the current hourly series. The source badge distinguishes demo baseline values, live observed counts, mixed values, and simulation output. The live camera panel also separates the active frame detections from the historical volume chart.

## 3. Show the planning model

Return to **Overview** and choose a closure percentage and hour in the planning desk, then run the scenario. Review displaced volume, modeled delay, and the links receiving the largest modeled changes. The result summary is generated from the simulator's numerical output.

Be explicit: the camera feeds are real, while the closure planner still uses a sample road graph and baseline volumes. It is not a surveyed Kosovo road network. Avoid presenting the sample network's figures as measured city traffic.

## 4. Compare closure levels

Open **Closure planner** to compare 25%, 50%, 75%, and 100% closures for a selected network link. Point out the model-scope note before interpreting the results.
