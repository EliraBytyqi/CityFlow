# CITYFLOW AI — 3-MINUTE DEMO SCRIPT

> **Goal**: Complete a polished, compelling hackathon demo in under 3 minutes, showcasing existing AI model integration, real-time closure simulation, map animations, scenario comparisons, and natural-language AI explanations.

---

### [0:00 - 0:20] THE PROBLEM
**Presenter**:
> "Good morning, judges! Cities close streets every single day for repairs, events, or urban developments. But city planners face a huge challenge: when you close a street, where do all those vehicles go? Counting today's traffic doesn't tell you where people will drive tomorrow. That's why we built **CityFlow AI: See the impact before you change the street.**"

---

### [0:20 - 0:40] EXISTING AI MODEL INTEGRATION
*(Navigate to `/cameras` on screen)*

**Presenter**:
> "We don't need to rebuild computer vision models—we already have a trained AI vehicle detection system. Here in our Camera Monitors dashboard, you can see live edge cameras like CAM_01 on Weststraat and CAM_02 on Noordweg. Our model sends real-time vehicle counts directly into CityFlow AI via a standard REST adapter interface (`POST /api/traffic/ingest`). Notice the blue `[OBSERVED]` badge—CityFlow clearly distinguishes real observations from model estimates."

---

### [0:40 - 1:00] 24-HOUR TRAFFIC ANALYTICS
*(Navigate to `/analytics` on screen)*

**Presenter**:
> "Over on the Traffic Analytics tab, CityFlow aggregates these observations across 24 hours. We automatically identify peak traffic hours—in our case, 08:00 AM with over 4,800 vehicles per hour—and track vehicle classification split between cars, freight trucks, transit buses, and motorcycles."

---

### [1:00 - 1:30] SELECT STREET & ROAD DETAILS
*(Navigate to `/` Dashboard, click on Weststraat on the interactive map)*

**Presenter**:
> "Now let's head to the centerpiece: our interactive Road Network Map. All roads are color-coded by capacity utilization: Green for low traffic, Yellow for moderate, Orange for high, and Red for critical bottlenecks.
> 
> Let's select **Weststraat**. The detail panel shows it carries 2,430 vehicles a day at 78% capacity utilization, with an average speed of 31 km/h."

---

### [1:30 - 2:00] SIMULATE 100% CLOSURE & TRAFFIC REDISTRIBUTION
*(In the What-If panel, select 100% Closure, click [ SIMULATE CLOSURE ])*

**Presenter**:
> "Now, what happens if city council decides to close Weststraat for a street fair?
> Let's select **100% Closure** and click **SIMULATE CLOSURE**.
> 
> Watch the animated loading state: CityFlow analyzes the directed road graph using NetworkX, finds alternative shortest paths, redistributes 1,850 displaced peak vehicles, and recalculates travel delays.
> 
> Look at the map change! Weststraat turns grey and dashed. Neighboring corridors like Noordweg turn from Green to Orange (+17% traffic increase), and Kerkstraat turns Yellow (+12%)."

---

### [2:00 - 2:20] BEFORE / AFTER VIEW & AI EXPLANATION
*(Scroll down to Before/After View and AI Impact Synthesis)*

**Presenter**:
> "In the Before/After impact panel, animated bars show exact flow shifts for every corridor. We see 1,850 vehicles displaced, 3 roads hitting critical capacity, and an average travel delay of +11%.
> 
> Down here, our **AI Impact Analysis** generates a natural-language synthesis derived strictly from numerical simulation data: *'Closing Weststraat redirects modeled traffic toward Noordweg and Kerkstraat... During the morning peak, 3 roads exceed the configured threshold.'*"

---

### [2:20 - 2:40] TIME-BASED & SCENARIO COMPARISONS
*(Navigate to `/scenarios`)*

**Presenter**:
> "CityFlow AI also lets planners compare partial closures. On our Scenarios page, we compare 25%, 50%, 75%, and 100% closures side-by-side. 
> Furthermore, we can change the simulation hour from 08:00 AM (morning peak) to 22:00 PM (nighttime), demonstrating that the same closure has vastly different impacts depending on time of day."

---

### [2:40 - 2:55] FINAL CLOSING STATEMENT
*(Navigate back to Dashboard, click `RUN HACKATHON DEMO` if automated rerun requested)*

**Presenter**:
> "Instead of guessing or discovering gridlock after closing a street, CityFlow AI empowers planners to explore scenarios, test trade-offs, and see the impact *before* they change the street. Thank you!"
