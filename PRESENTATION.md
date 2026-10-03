# CITYFLOW — KOSOVO TRAFFIC OBSERVATORY

> **Pitch:** See what is moving at a real camera. Explore what a road change could mean.

## 1. The planning question

Street closures shift traffic. Planners need a way to inspect current conditions and compare possible closure impacts before making a change.

## 2. What CityFlow does today

- Opens six configured public camera streams at locations in Kosovo.
- Runs the bundled YOLO vehicle detector on the backend and overlays class labels and boxes on the returned live frames.
- Displays per-frame counts for cars, trucks, buses, and motorcycles.
- Accepts traffic observations through the existing ingestion API.
- Compares simulated traffic redistribution at 25%, 50%, 75%, and 100% closure levels.

## 3. Camera locations

- Fushë Kosovë
- Ulpianë
- Bregu i Diellit
- Pejton
- Magjistralja Vushtrri–Mitrovicë
- Ortakoll: Wesley Clark, Prizren

## 4. How the planning model works

1. The detector or another producer submits vehicle observations through the traffic ingestion API.
2. CityFlow evaluates closures against a directed road graph.
3. The simulator estimates displaced traffic, affected links, congestion, and delay.
4. The result summary is built from simulation output.

## 5. Data scope

The camera streams are real. The current closure model uses a sample network and baseline volumes; it is not a surveyed Kosovo road graph, and its volumes must not be presented as measured local traffic. The interface labels sample, observed, mixed, and simulated data separately.

## 6. Next step for a city-ready model

Replace the sample network and baseline measurements with validated Kosovo road geometry, capacities, and locally measured traffic volumes. Until those inputs are available, use the closure planner to demonstrate the model workflow, not to make operational road decisions.
