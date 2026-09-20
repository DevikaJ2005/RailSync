# RailSync — Geographic Data Sources & Railway Network Representation

This document records the geographic data sources, licensing, and representation principles used for the railway network in RailSync.

## 1. Geographic Network Data

RailSync models the Southern Railway trunk and chord corridors across Tamil Nadu, India.

| Corridor / Section | From | To | Distance | Track Alignment Waypoints Source |
|---|---|---|---|---|
| `SEC1` | Chennai Central | Katpadi Junction | 129 km | OpenStreetMap Railway Alignment (via Arakkonam Junction corridor) |
| `SEC2` | Katpadi Junction | Jolarpettai Junction | 88 km | OpenStreetMap Railway Alignment (via Vaniyambadi / Ambur) |
| `SEC3` | Jolarpettai Junction | Salem Junction | 98 km | OpenStreetMap Railway Alignment (via Morappur / Bommidi) |
| `SEC4` | Salem Junction | Tiruchirapalli Junction | 148 km | OpenStreetMap Railway Alignment (via Namakkal / Karur Junction) |
| `SEC5` | Tiruchirapalli Junction | Madurai Junction | 129 km | OpenStreetMap Railway Alignment (via Dindigul Junction) |
| `SEC6` | Chennai Central | Villupuram Junction | 160 km | OpenStreetMap Railway Alignment (Chord line via Tambaram / Chengalpattu) |
| `SEC7` | Villupuram Junction | Tiruchirapalli Junction | 171 km | OpenStreetMap Railway Alignment (Chord line via Vriddhachalam / Ariyalur) |
| `SEC8` | Salem Junction | Coimbatore Junction | 172 km | OpenStreetMap Railway Alignment (via Erode Junction / Tiruppur) |

## 2. Station Geographic Coordinates & Platforms

Station coordinates represent real-world passenger terminal coordinates across Tamil Nadu:

- **Chennai Central (`MAS`)**: `13.0827° N, 80.2707° E` (12 Platforms)
- **Katpadi Junction (`KPD`)**: `12.9698° N, 79.1417° E` (6 Platforms)
- **Jolarpettai Junction (`JTJ`)**: `12.5764° N, 78.5747° E` (4 Platforms)
- **Salem Junction (`SA`)**: `11.6643° N, 78.1460° E` (1 Platform simulated bottleneck)
- **Tiruchirapalli Junction (`TPJ`)**: `10.8038° N, 78.6858° E` (8 Platforms)
- **Madurai Junction (`MDU`)**: `9.9195° N, 78.1193° E` (6 Platforms)
- **Villupuram Junction (`VM`)**: `11.9401° N, 79.4861° E` (5 Platforms)
- **Coimbatore Junction (`CBE`)**: `11.0018° N, 76.9629° E` (2 Platforms)

## 3. Data Licensing & Attribution

- **Base Map & Geography**: OpenStreetMap contributors (`https://www.openstreetmap.org/copyright`).
- **License**: Open Data Commons Open Database License (ODbL) 1.0.
- **Cartographic Representation**: Standard GIS railway track symbology (solid ballast base + sleeper centerline) representing the physical railway corridor alignment without fabricating multi-track infrastructure.

## 4. Architectural Separation: Physical Geometry vs Logical Simulation

- **Physical Railway Geometry**: Visual and geographic context on the Leaflet map layer. Shows real-world rail corridors connecting cities.
- **Logical Section**: The authoritative simulation and conflict model in `conflict_detection.py` and `simulator.py`. Concurrency is evaluated on station-to-station movement authority, independent of physical track counts, blocks, or interlocking signals.

