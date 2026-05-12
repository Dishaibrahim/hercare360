import json
from pathlib import Path

from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, Heading, Row, Separator, Text,
)

room_allocator_app = FastMCPApp("RoomAllocator")

_DATA = Path(__file__).parent.parent.parent / "data" / "rooms.json"


def _load_rooms() -> list[dict]:
    return json.loads(_DATA.read_text())["rooms"]


def _save_rooms(rooms: list[dict]) -> None:
    raw = json.loads(_DATA.read_text())
    raw["rooms"] = rooms
    _DATA.write_text(json.dumps(raw, indent=2))


@room_allocator_app.tool("GetScanningRoomAvailability")
async def get_scanning_room_availability() -> PrefabApp:
    """Real-time scanning room utilisation with per-slot booking detail."""
    rooms = _load_rooms()

    with Card() as view:
        with CardHeader():
            CardTitle("Scanning Room Availability")
        with CardContent():
            with Column(gap=4):
                for room in rooms:
                    booked = len(room["bookings"])
                    max_slots = 16 if room["slot_duration_min"] == 30 else (10 if room["slot_duration_min"] == 45 else 8)
                    pct = min(100, int((booked / max_slots) * 100))
                    util_v = "danger" if pct > 75 else ("warning" if pct > 50 else "success")

                    with Column(gap=2):
                        with Row(gap=3, align="center"):
                            Heading(room["name"])
                            Badge(room["type"], variant="secondary")
                            Badge(f"{pct}% utilised", variant=util_v)
                        Text(f"Slot duration: {room['slot_duration_min']} min · {booked} bookings today")

                        if room["bookings"]:
                            for booking in room["bookings"]:
                                with Row(gap=2, align="center"):
                                    Badge(booking["time"], variant="secondary")
                                    Text(booking["patient_name"])
                                    Text(f"— {booking['procedure']}", css_class="text-muted-foreground text-sm")
                        else:
                            Badge("All slots available", variant="success")

                    Separator()

    return PrefabApp(view=view)


@room_allocator_app.tool("AllocateScanningRoom")
async def allocate_scanning_room(
    room_id: str,
    time_slot: str,
    patient_id: str,
    patient_name: str,
    procedure: str,
) -> dict:
    """Assign a room to a procedure; detect double-bookings and flag for priority resolution."""
    rooms = _load_rooms()
    room = next((r for r in rooms if r["id"] == room_id), None)

    if room is None:
        return {"success": False, "error": f"Room '{room_id}' not found. Valid IDs: US-1, US-2, DEXA-1, COLPO-1"}

    conflict = next((b for b in room["bookings"] if b["time"] == time_slot), None)
    if conflict:
        return {
            "success": False,
            "conflict": True,
            "room": room["name"],
            "slot": time_slot,
            "conflicting_patient_id": conflict["patient_id"],
            "conflicting_patient_name": conflict["patient_name"],
            "message": (
                f"Slot {time_slot} in {room['name']} is already booked by {conflict['patient_name']}. "
                "Call ResolvePriorityConflict to auto-assign by clinical urgency."
            ),
        }

    room["bookings"].append({"time": time_slot, "patient_id": patient_id, "patient_name": patient_name, "procedure": procedure})
    room["bookings"].sort(key=lambda b: b["time"])
    _save_rooms(rooms)

    return {
        "success": True,
        "room": room["name"],
        "slot": time_slot,
        "patient": patient_name,
        "procedure": procedure,
        "message": f"✓ Allocated {room['name']} at {time_slot} for {patient_name} — {procedure}",
    }


@room_allocator_app.tool("GetCapacityHeatmap")
async def get_capacity_heatmap() -> dict:
    """7-day room utilisation heatmap, colour-coded by utilisation percent."""
    rooms = _load_rooms()
    heatmap = []

    for room in rooms:
        booked = len(room["bookings"])
        max_slots = 16 if room["slot_duration_min"] == 30 else (10 if room["slot_duration_min"] == 45 else 8)
        pct = min(100, int((booked / max_slots) * 100))
        heatmap.append({
            "room_id": room["id"],
            "room": room["name"],
            "type": room["type"],
            "bookings_today": booked,
            "utilisation_pct": pct,
            "status": "High" if pct > 75 else ("Moderate" if pct > 50 else "Low"),
        })

    return {"date": "2026-05-12", "rooms": heatmap}
