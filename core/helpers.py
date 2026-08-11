import json
import math
import os
import requests
from datetime import date, datetime, timedelta

DONOR_FILE = "data/donors.json"
DONATION_FILE = "data/donations.json"
REQUEST_FILE = "data/requests.json"
MEMBER_FILE = "data/members.json"
CONTACT_FILE = "data/contacts.json"
NOTICE_FILE = "data/notices.json"
TITLE_FILE = "data/titles.json"
DEPARTMENT_FILE = "data/departments.json"
COMMITTEE_FILE = "data/committees.json"


# =====================================
# Clear Screen
# =====================================

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

# =====================================
# Distance Calculate
# =====================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    R = 6371

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        +
        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    distance = R * c

    return distance

# =====================================
# Load Data
# =====================================

def load_data(filename):

    try:
        with open(filename, "r") as file:
            return json.load(file)

    except (FileNotFoundError, json.JSONDecodeError):
        return []

# =====================================
# Save Data
# =====================================

def save_data(filename, data):
    """Write JSON safely: temp file first, then replace (avoids corruption)."""
    import tempfile
    directory = os.path.dirname(filename) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp_path, filename)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

# =====================================
# Blood Request Status Helpers
# (Multi-source / multi-donor completion,
#  auto partial/incomplete after deadline)
# =====================================

REQUEST_DEADLINE_DAYS = 3


def get_request_target_date(req):
    """The date the blood was actually needed by (donation_date),
    falling back to created_date for very old records."""
    raw = req.get("donation_date") or req.get("created_date")
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def get_request_deadline(req):
    """Date after which an unfulfilled request auto-drops to
    Partial/Incomplete (donation_date + REQUEST_DEADLINE_DAYS)."""
    base = get_request_target_date(req)
    if base is None:
        return None
    return base + timedelta(days=REQUEST_DEADLINE_DAYS)


def request_collected_bags(req):
    fulfillments = req.get("fulfillments") or []
    return sum(f.get("bags", 0) for f in fulfillments)


def request_bags_remaining(req):
    return max(0, req.get("bags", 0) - request_collected_bags(req))


def compute_request_status(req):
    """Status is always derived, never permanently locked, so a
    Partial/Incomplete request can still become Fulfilled later
    if more bags get managed."""
    bags = req.get("bags", 0)
    collected = request_collected_bags(req)

    if bags > 0 and collected >= bags:
        return "Fulfilled"

    deadline = get_request_deadline(req)
    if deadline is not None and date.today() > deadline:
        if collected > 0:
            return "Partial"
        return "Incomplete"

    return "Open"


def sync_request_status(req):
    """Recompute status + collected_bags after any fulfillment
    add/remove and keep completed_date consistent."""
    req["collected_bags"] = request_collected_bags(req)
    new_status = compute_request_status(req)
    req["status"] = new_status
    if new_status == "Fulfilled":
        if not req.get("completed_date"):
            req["completed_date"] = date.today().isoformat()
    else:
        req["completed_date"] = None
    return req


def get_departments():
    return load_data(DEPARTMENT_FILE)

def add_department(department):
    departments = load_data(DEPARTMENT_FILE)
    if department not in departments:
        departments.append(department)
        save_data(DEPARTMENT_FILE, departments)
        return True
    return False

# =====================================
# Geocode Location (Text -> Lat/Long)
# =====================================

def geocode_location(place_name):
    """
    Converts a place name / address text into (latitude, longitude)
    using OpenStreetMap's free Nominatim geocoding service.
    Returns (lat, lon) as floats, or (None, None) if not found.
    """
    try:
        query = place_name.strip()
        if "bangladesh" not in query.lower():
            query = f"{query}, Bangladesh"

        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "GSSBDC-Connect/1.0"},
            timeout=6
        )
        response.raise_for_status()
        results = response.json()

        if not results:
            return None, None

        return float(results[0]["lat"]), float(results[0]["lon"])

    except Exception:
        return None, None