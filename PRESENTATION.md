# CITYFLOW AI — PRESENTATION DECK

> **Central Pitch**: *"Don't just measure today's traffic. Model tomorrow's traffic."*

---

## SLIDE 1: THE PROBLEM
### "Closing streets without knowing where traffic will go."

* Cities frequently close streets for construction, pedestrianization, or major events.
* Traditional planning relies on **static traffic counts**.
* A static count tells you how many vehicles are on a street today, but **zero information** about where those 2,430 vehicles will turn when you put up a barrier tomorrow.
* **The Result**: Unintended bottlenecks, gridlocked emergency routes, and frustrated citizens.

---

## SLIDE 2: WHY TRAFFIC COUNTS AREN'T ENOUGH
### "Detection is observation; decision support requires prediction."

* Existing AI models (YOLO, ByteTrack) excel at counting cars, trucks, and buses.
* But knowing **"Weststraat has 2,430 vehicles today"** is only 10% of the equation.
* Planners need to know:
  * Which alternative streets will absorb the displaced vehicles?
  * Will surrounding corridors exceed 90% capacity?
  * What is the net travel time delay for the urban grid?

---

## SLIDE 3: CITYFLOW AI
### "See the impact before you change the street."

* **CityFlow AI** is a smart-city decision-support platform built on top of vehicle-detection AI.
* We connect directly to existing vision models via a clean API adapter.
* We transform raw camera counts into an interactive, network-wide predictive simulator.

---

## SLIDE 4: HOW THE SYSTEM WORKS
### "From raw AI detection to graph-based traffic redistribution."

1. **Ingest**: Existing AI models send vehicle counts via `POST /api/traffic/ingest`.
2. **Graph Model**: The city is represented as a directed graph (Intersections = Nodes, Roads = Edges).
3. **Closure Simulation**: When a user selects a road and a closure percentage (e.g. 100%), NetworkX reroutes displaced vehicles along $k$-shortest paths.
4. **Congestion & Delay**: Speeds and travel delays are updated dynamically based on road capacity utilization.
5. **AI Synthesis**: Natural-language explanation summarizes network trade-offs.

---

## SLIDE 5: LIVE DEMO
### "Interactive What-If Simulation."

* **Select a Road**: Weststraat (2,430 vehicles/day, 78% capacity).
* **Set Closure**: 100% Closure.
* **Simulate**: Real-time redistribution across surrounding corridors.
* **Observe Impact**:
  * 1,850 vehicles displaced during morning peak.
  * Noordweg traffic increases by +17% (700 → 819 veh/hr).
  * Kerkstraat traffic increases by +12% (620 → 695 veh/hr).
  * Average modeled travel delay: +11%.

---

## SLIDE 6: WHAT-IF SCENARIOS & TRADE-OFFS
### "Comparing closure levels across different hours of the day."

* **Partial Closures**: Compare 25%, 50%, 75%, and 100% closures side-by-side.
* **Time-Based Dynamics**: Rerouting 100% of traffic at 08:00 (Morning Peak) creates 3 critical bottlenecks, whereas closing the same road at 22:00 (Nighttime) yields negligible delay.
* **Objective Trade-Offs**: CityFlow AI does not assign arbitrary scores; it displays measurable vehicle displacements and delay metrics to empower human decision-makers.

---

## SLIDE 7: FUTURE VISION
### "Building the digital twin for urban mobility."

* **Dynamic Signal Optimization**: Automatically adjust traffic light timing loops on surrounding streets to absorb redistributed flow.
* **Transit Rerouting**: Real-time bus rerouting and schedule adjustments.
* **Multi-Modal Modeling**: Simulating bicycle, pedestrian, and micro-mobility shift when car capacity is reduced.

> *"Don't just measure today's traffic. Model tomorrow's traffic with CityFlow AI."*
