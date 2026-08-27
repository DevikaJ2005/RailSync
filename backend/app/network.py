"""
Static definition of the simulated Tamil Nadu rail network.
Station coordinates are REAL latitude/longitude values (used directly by
the Leaflet map on the frontend — no GPS tracking needed since the
network itself is simulated, but the geography is real).
"""

STATIONS = {
    "Chennai Central": {"lat": 13.0827, "lng": 80.2707, "platforms": 12},
    "Katpadi Junction": {"lat": 12.9698, "lng": 79.1417, "platforms": 6},
    "Jolarpettai Junction": {"lat": 12.5764, "lng": 78.5747, "platforms": 4},
    "Salem Junction": {"lat": 11.6643, "lng": 78.1460, "platforms": 1},
    "Tiruchirapalli Junction": {"lat": 10.8038, "lng": 78.6858, "platforms": 8},
    "Madurai Junction": {"lat": 9.9195, "lng": 78.1193, "platforms": 6},
    "Villupuram Junction": {"lat": 11.9401, "lng": 79.4861, "platforms": 5},
    "Coimbatore Junction": {"lat": 11.0018, "lng": 76.9629, "platforms": 2},
}

# Real approximate rail distances (km) between adjacent stations.
SECTIONS = [
    {"id": "SEC1", "from": "Chennai Central", "to": "Katpadi Junction", "distance_km": 129,
     "path": [[13.0827, 80.2707], [13.006, 80.173], [12.977, 79.923], [12.907, 79.909], [12.721, 79.573], [12.9698, 79.1417]]},
    {"id": "SEC2", "from": "Katpadi Junction", "to": "Jolarpettai Junction", "distance_km": 88,
     "path": [[12.9698, 79.1417], [12.906, 79.019], [12.792, 78.944], [12.678, 78.795], [12.5764, 78.5747]]},
    {"id": "SEC3", "from": "Jolarpettai Junction", "to": "Salem Junction", "distance_km": 98,
     "path": [[12.5764, 78.5747], [12.454, 78.438], [12.268, 78.158], [12.112, 77.994], [11.876, 78.061], [11.6643, 78.146]]},
    {"id": "SEC4", "from": "Salem Junction", "to": "Tiruchirapalli Junction", "distance_km": 148,
     "path": [[11.6643, 78.146], [11.548, 78.151], [11.219, 78.167], [10.960, 78.081], [10.785, 78.176], [10.8038, 78.6858]]},
    {"id": "SEC5", "from": "Tiruchirapalli Junction", "to": "Madurai Junction", "distance_km": 129,
     "path": [[10.8038, 78.6858], [10.679, 78.568], [10.454, 78.100], [10.235, 78.123], [9.9195, 78.1193]]},
    {"id": "SEC6", "from": "Chennai Central", "to": "Villupuram Junction", "distance_km": 160,
     "path": [[13.0827, 80.2707], [12.924, 80.118], [12.684, 79.983], [12.527, 79.884], [12.307, 79.638], [11.9401, 79.4861]]},
    {"id": "SEC7", "from": "Villupuram Junction", "to": "Tiruchirapalli Junction", "distance_km": 171,
     "path": [[11.9401, 79.4861], [11.791, 79.313], [11.542, 79.248], [11.271, 79.076], [11.110, 78.944], [10.8038, 78.6858]]},
    {"id": "SEC8", "from": "Salem Junction", "to": "Coimbatore Junction", "distance_km": 172,
     "path": [[11.6643, 78.146], [11.515, 77.973], [11.342, 77.728], [11.161, 77.603], [11.107, 77.341], [11.0018, 76.9629]]},
]

TRAINS = [
    {
        "train_no": "T101", "name": "Chennai-Coimbatore Express", "type": "Express",
        "speed_kmph": 78,
        "route": ["Chennai Central", "Katpadi Junction", "Jolarpettai Junction", "Salem Junction", "Coimbatore Junction"],
        "stops_at": ["Chennai Central", "Katpadi Junction", "Salem Junction", "Coimbatore Junction"],
    },
    {
        "train_no": "T102", "name": "Chennai-Madurai SF Express", "type": "Express",
        "speed_kmph": 80,
        "route": ["Chennai Central", "Villupuram Junction", "Tiruchirapalli Junction", "Madurai Junction"],
        "stops_at": ["Chennai Central", "Villupuram Junction", "Madurai Junction"],
    },
    {
        "train_no": "T103", "name": "Katpadi Passenger", "type": "Passenger",
        "speed_kmph": 45,
        "route": ["Chennai Central", "Katpadi Junction"],
        "stops_at": ["Chennai Central", "Katpadi Junction"],
    },
    {
        "train_no": "T104", "name": "Salem Freight Special", "type": "Freight",
        "speed_kmph": 35,
        "route": ["Salem Junction", "Coimbatore Junction"],
        "stops_at": ["Salem Junction", "Coimbatore Junction"],
    },
    {
        "train_no": "T105", "name": "Trichy-Chennai Express", "type": "Express",
        "speed_kmph": 76,
        "route": ["Tiruchirapalli Junction", "Villupuram Junction", "Chennai Central"],
        "stops_at": ["Tiruchirapalli Junction", "Chennai Central"],
    },
    {
        "train_no": "T106", "name": "Villupuram Passenger", "type": "Passenger",
        "speed_kmph": 42,
        "route": ["Chennai Central", "Villupuram Junction"],
        "stops_at": ["Chennai Central", "Villupuram Junction"],
    },
    {
        "train_no": "T107", "name": "Coimbatore Freight Corridor", "type": "Freight",
        "speed_kmph": 32,
        "route": ["Salem Junction", "Coimbatore Junction"],
        "stops_at": ["Salem Junction", "Coimbatore Junction"],
    },
    {
        "train_no": "T108", "name": "Madurai-Chennai SF Express", "type": "Express",
        "speed_kmph": 79,
        "route": ["Madurai Junction", "Tiruchirapalli Junction", "Salem Junction", "Jolarpettai Junction", "Katpadi Junction", "Chennai Central"],
        "stops_at": ["Madurai Junction", "Tiruchirapalli Junction", "Salem Junction", "Chennai Central"],
    },
    {
        "train_no": "T109", "name": "Jolarpettai Passenger", "type": "Passenger",
        "speed_kmph": 44,
        "route": ["Katpadi Junction", "Jolarpettai Junction"],
        "stops_at": ["Katpadi Junction", "Jolarpettai Junction"],
    },
    {
        "train_no": "T110", "name": "Salem-Trichy Freight", "type": "Freight",
        "speed_kmph": 33,
        "route": ["Salem Junction", "Tiruchirapalli Junction"],
        "stops_at": ["Salem Junction", "Tiruchirapalli Junction"],
    },
]


def get_section(station_a: str, station_b: str):
    for sec in SECTIONS:
        if {sec["from"], sec["to"]} == {station_a, station_b}:
            return sec
    return None


def get_distance(station_a: str, station_b: str) -> float:
    sec = get_section(station_a, station_b)
    return sec["distance_km"] if sec else 0


def network_payload() -> dict:
    """Serialized network for the GET /api/network endpoint."""
    return {
        "stations": [
            {"name": name, "lat": info["lat"], "lng": info["lng"], "platforms": info["platforms"]}
            for name, info in STATIONS.items()
        ],
        "sections": SECTIONS,
        "trains": [
            {"train_no": t["train_no"], "name": t["name"], "type": t["type"], "route": t["route"]}
            for t in TRAINS
        ],
    }
