# RailSync Map Assets & Train Sprites

This document describes the visual assets and rendering specifications used by RailSync's interactive geographic map visualization.

## 1. Train Sprite Assets

All train sprites reside locally within the client package at `frontend/public/trains/`. They are bundled and served locally with zero external network dependencies, ensuring 100% offline capability.

| Asset File | Train Category / Type | Visual Design Details |
|---|---|---|
| `frontend/public/trains/express_train.svg` | **Express / High-Speed** (`express`, `superfast`, `vande_bharat`, `rajdhani`, `shatabdi`) | Sleek aerodynamic tapered nose cab in deep navy & silver metallic finish, continuous dark-tinted wraparound windshield, recessed AC cooling pods, precision pantograph, coach window bands, and micro-point headlights/tail lights. |
| `frontend/public/trains/passenger_train.svg` | **Passenger / Regional** (`passenger`, `commuter`, `local`, `intercity`) | Classic electric locomotive (WAP-4 silhouette) in deep Indian Railway maroon/crimson with cream belt line, roof resistor banks, pantographs, and coupled passenger coach with realistic window apertures. |
| `frontend/public/trains/freight_train.svg` | **Freight / Goods** (`freight`, `goods`, `cargo`) | Heavy industrial locomotive (WAG-9 silhouette) in dark evergreen & slate with hazard buffer beam, roof cooling fans, and coupled flatbed wagons carrying corrugated ISO shipping containers (oxide red and deep maritime teal) with corner castings. |

## 2. Technical Specifications

- **Format**: Scalable Vector Graphics (SVG 1.1)
- **ViewBox**: `0 0 20 100` (1:5 realistic railway vehicle aspect ratio)
- **Orientation**: Default heading points True North ($0^\circ$, directly upwards).
- **Rotation**: Dynamically rotated via CSS `transform: rotate(${bearing}deg)` computed from track segment vectors with continuous angle unwrapping.
- **Zoom-Dependent Dynamic Scaling**:
  - Zoom $\le$ 6: $7\text{px} \times 22\text{px}$ (compact regional marker)
  - Zoom 7 (Default Regional Overview): $9\text{px} \times 26\text{px}$ (clean miniature train neatly riding track lines)
  - Zoom 8: $11\text{px} \times 32\text{px}$
  - Zoom 9: $13\text{px} \times 38\text{px}$
  - Zoom $\ge$ 10: $15\text{px} \times 46\text{px}$ (detailed junction closeup)
- **Status Indicators**:
  - Moving: Clean train with zero extra icons.
  - Waiting: 5px amber dot (`#F59E0B`).
  - Held: 5px red dot (`#EF4444`).
  - At platform: 5px emerald green dot (`#10B981`).
- **Conflict Highlighting**: Zero aggressive red glowing halos. Only trains involved in the currently selected conflict receive a crisp, subtle 1.5px outline contour (`filter: drop-shadow(0 0 1.5px #EF4444)`).
- **Contextual Monospace Labels**: Train ID pills are hidden by default to prevent visual clutter, appearing only on mouse hover, when a conflict involving the train is selected, or for the next arrival train.

## 3. License & Provenance

- **Source**: In-house precision vector designs created specifically for the RailSync Railway Traffic Management System.
- **License**: Creative Commons Zero 1.0 Universal (CC0 1.0) / MIT License.
- **Restrictions**: Free for use, modification, and commercial redistribution without attribution requirements.
