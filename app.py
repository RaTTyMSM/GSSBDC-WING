from flask import Flask, render_template, request, session, redirect, url_for, abort, jsonify, flash
from flask_socketio import SocketIO, emit, join_room, leave_room
from core.helpers import (
    load_data, save_data, calculate_distance, geocode_location,
    MEMBER_FILE, DONOR_FILE, REQUEST_FILE, DONATION_FILE, CONTACT_FILE, NOTICE_FILE, COMMITTEE_FILE,
    get_departments,
    compute_request_status, get_request_deadline, request_bags_remaining,
    request_collected_bags, sync_request_status
)
from modules.donation import get_eligibility, create_automatic_donation
from datetime import date, datetime, timedelta
from core.permissions import has_permission, GRANTABLE_PERMISSIONS, can_add_role, can_assign_role, ASSIGNABLE_ROLES, get_executive_titles
from core.security import hash_password, verify_password, is_hashed, generate_csrf_token, validate_csrf
import os
import secrets

import traceback
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("gssbdc")

app = Flask(__name__)
app.jinja_env.globals["has_permission"] = has_permission

def _load_or_create_secret_key():
    """Use GSSBDC_SECRET_KEY from the environment if set (recommended for
    production). Otherwise, auto-generate one on first run and persist it
    to a local file so the key stays stable across restarts -- without
    this, os.urandom() would give a new key every restart and log
    everyone out each time the server is restarted."""
    env_key = os.environ.get("GSSBDC_SECRET_KEY")
    if env_key:
        return env_key

    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".secret_key")
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            saved = f.read().strip()
            if saved:
                return saved

    new_key = secrets.token_hex(32)
    with open(key_path, "w") as f:
        f.write(new_key)
    return new_key


# Strong secret: set GSSBDC_SECRET_KEY in environment for production.
# If not set, a key is auto-generated once and saved to .secret_key
# (do not commit this file / do not share it).
app.secret_key = _load_or_create_secret_key()
# Cookie hardening
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    # SESSION_COOKIE_SECURE=True,  # enable when serving over HTTPS
)

# SocketIO must be created AFTER secret_key so session cookies work on WS
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    manage_session=True,
    logger=False,
    engineio_logger=False,
)


@app.context_processor
def inject_csrf():
    """Make csrf_token available in all templates."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = generate_csrf_token()
    return {"csrf_token": session["_csrf_token"]}

@app.context_processor
def inject_nav_member():
    """Make the logged-in member available to base.html on every page,
    even for routes that don't explicitly pass member/session_member."""
    return {"nav_member": get_current_member()}

@app.before_request
def check_csrf():
    """Reject POST requests without a valid CSRF token."""
    if request.method == "POST":
        token = request.form.get("csrf_token", "")
        if not validate_csrf(session.get("_csrf_token"), token):
            abort(400, description="Invalid or missing CSRF token. Please refresh the page and try again.")

# =====================================
# Global error handlers
# =====================================

@app.errorhandler(400)
def error_400(e):
    msg = getattr(e, "description", None) or "Bad request."
    return render_template("error.html", code=400, message="Bad Request", detail=msg), 400


@app.errorhandler(403)
def error_403(e):
    msg = getattr(e, "description", None) or "You do not have permission to access this page."
    return render_template("error.html", code=403, message="Access Denied", detail=msg), 403


@app.errorhandler(404)
def error_404(e):
    return render_template("error.html", code=404, message="Page Not Found", detail="The page you requested does not exist."), 404


@app.errorhandler(405)
def error_405(e):
    return render_template("error.html", code=405, message="Method Not Allowed", detail="This action is not allowed here."), 405


@app.errorhandler(500)
def error_500(e):
    log.exception("Internal server error: %s", e)
    return render_template(
        "error.html",
        code=500,
        message="Something went wrong",
        detail="An unexpected error occurred. Please try again or contact an admin.",
    ), 500


@app.errorhandler(Exception)
def error_unhandled(e):
    """Catch-all so the app doesn't dump a raw traceback to the browser."""
    log.exception("Unhandled exception: %s", e)
    # In debug mode, re-raise so Flask shows the debugger
    if app.debug:
        raise
    return render_template(
        "error.html",
        code=500,
        message="Something went wrong",
        detail="An unexpected error occurred. Please try again.",
    ), 500

def get_current_member():
    """Load fresh member from DB using session member_id."""
    try:
        member_id = session.get("member_id")
        if member_id is None:
            old = session.get("member")
            if isinstance(old, dict) and "id" in old:
                member_id = old["id"]
                session["member_id"] = member_id
            else:
                return None
        members = load_data(MEMBER_FILE)
        if not isinstance(members, list):
            log.error("members data is not a list")
            return None
        member = next(
            (m for m in members if m.get("id") == member_id and not m.get("deleted", False)),
            None,
        )
        if member is None or not member.get("active", True):
            return None
        safe = dict(member)
        safe.pop("password", None)
        return safe
    except Exception as e:
        log.exception("get_current_member failed: %s", e)
        return None


def require_member():
    """Return current member, or None if not logged in."""
    member = get_current_member()
    if member is None:
        session.pop("member_id", None)
        session.pop("member", None)
        return None
    return member

def _blood_group_donation_stats(club_donations):
    """Bags + donation-count broken down by blood group (club only)."""
    bg_order = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    bags = {}
    counts = {}
    for d in club_donations:
        bg = d.get("blood_group") or "Unknown"
        bags[bg] = bags.get(bg, 0) + int(d.get("bags", 0) or 0)
        counts[bg] = counts.get(bg, 0) + 1
    labels = [bg for bg in bg_order if bg in bags or bg in counts]
    labels += sorted(bg for bg in set(list(bags) + list(counts)) if bg not in bg_order)
    return {
        "labels": labels,
        "bags": [bags.get(bg, 0) for bg in labels],
        "counts": [counts.get(bg, 0) for bg in labels],
        "bags_dict": {bg: bags.get(bg, 0) for bg in labels},
        "counts_dict": {bg: counts.get(bg, 0) for bg in labels},
    }

def _build_dashboard_chart_data():
    """Shared builder for dashboard charts (page render + live API)."""
    donors = load_data(DONOR_FILE)
    donations = load_data(DONATION_FILE)
    requests_data = load_data(REQUEST_FILE)
    contacts = load_data(CONTACT_FILE)
    committees = load_data(COMMITTEE_FILE)

    club_donations = [d for d in donations if d.get("source", "club") != "external"]

    for r in requests_data:
        r.setdefault("fulfillments", [])
        r["collected_bags"] = request_collected_bags(r)
        r["_status"] = compute_request_status(r)
        r["_period"] = _request_period_key(r)

    blood_group_counts = {}
    for d in donors:
        bg = d.get("blood_group") or "Unknown"
        blood_group_counts[bg] = blood_group_counts.get(bg, 0) + 1
    bg_order = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    blood_group_labels = [bg for bg in bg_order if bg in blood_group_counts]
    blood_group_labels += [bg for bg in blood_group_counts if bg not in bg_order]
    bg_stats = _blood_group_donation_stats(club_donations)

    return {
        "blood_groups": {
            "labels": blood_group_labels,
            "values": [blood_group_counts[bg] for bg in blood_group_labels]
        },
        "bags_by_blood_group": {
            "labels": bg_stats["labels"],
            "values": bg_stats["bags"],
        },
        "donation_count_by_blood_group": {
            "labels": bg_stats["labels"],
            "values": bg_stats["counts"],
        },
        "six_month_stats": _last_n_months_full(requests_data, club_donations, contacts, 6),
    }



@app.route("/")
def home():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    chart_data = None
    if has_permission(member, "view_statistics"):
        chart_data = _build_dashboard_chart_data()

    return render_template(
        "dashboard.html",
        member=member,
        has_permission=has_permission,
        chart_data=chart_data
    )


@app.route("/api/dashboard-charts")
def api_dashboard_charts():
    """JSON endpoint for live dashboard chart refresh."""
    member = require_member()
    if member is None:
        return jsonify({"error": "unauthorized"}), 401
    if not has_permission(member, "view_statistics"):
        return jsonify({"error": "forbidden"}), 403
    return jsonify(_build_dashboard_chart_data())

def _socket_member():
    """Resolve logged-in member from the Flask session (shared with Socket.IO)."""
    member_id = session.get("member_id")
    if not member_id:
        return None
    members = load_data(MEMBER_FILE)
    return next((m for m in members if m.get("id") == member_id and not m.get("deleted")), None)


def broadcast_dashboard_charts():
    """Push latest chart payload to everyone watching the dashboard."""
    try:
        data = _build_dashboard_chart_data()
        socketio.emit("charts_update", data, room="dashboard")
    except Exception as e:
        log.exception("broadcast_dashboard_charts error: %s", e)


def push_notification(kind, title, message, link=None, audience="all", extra=None):
    """Broadcast a real-time notification over Socket.IO.

    audience:
      - "all"         -> every logged-in client in room notif_all
      - "executives"  -> Executive / Admin / Watcher only (room notif_exec)
    """
    payload = {
        "id": f"{kind}-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}",
        "kind": kind,          # member | notice | request
        "title": title,
        "message": message,
        "link": link or "/",
        "audience": audience,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    if extra:
        payload["extra"] = extra
    try:
        room = "notif_exec" if audience == "executives" else "notif_all"
        socketio.emit("notification", payload, room=room)
        # executives also sit in notif_all; avoid double-send for "all"
        print(f"[notif] {kind} -> {room}: {title}")
    except Exception as e:
        print("push_notification error:", e)


@socketio.on("connect")
def ws_connect():
    member = _socket_member()
    if member is None:
        print("[ws] connect rejected: no session")
        return False

    # Everyone logged in receives general notifications
    join_room("notif_all")

    # Executive-only notices / sensitive alerts
    if member.get("type") in ("Executive", "Admin", "Watcher"):
        join_room("notif_exec")

    # Dashboard chart stream (optional permission)
    if has_permission(member, "view_statistics"):
        join_room("dashboard")
        emit("charts_update", _build_dashboard_chart_data())

    print(
        "[ws] connected:", member.get("name"),
        "type=", member.get("type"),
        "rooms=notif_all"
        + ("+notif_exec" if member.get("type") in ("Executive", "Admin", "Watcher") else "")
        + ("+dashboard" if has_permission(member, "view_statistics") else "")
    )


@socketio.on("disconnect")
def ws_disconnect():
    leave_room("dashboard")


@socketio.on("request_charts")
def ws_request_charts():
    member = _socket_member()
    if member is None or not has_permission(member, "view_statistics"):
        return
    emit("charts_update", _build_dashboard_chart_data())


def _start_dashboard_push_loop():
    """Background push every few seconds while the server is running."""
    while True:
        socketio.sleep(5)
        try:
            broadcast_dashboard_charts()
        except Exception as e:
            print("dashboard push loop error:", e)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        members = load_data(MEMBER_FILE)

        for member in members:
            if member.get("username", "").lower() == username.lower():
                if not verify_password(password, member.get("password", "")):
                    break
                if not member.get("active", True):
                    return render_template("login.html", error="Your account is inactive.")
                # Migrate legacy plaintext password to hash on successful login
                if not is_hashed(member.get("password", "")):
                    member["password"] = hash_password(password)
                    save_data(MEMBER_FILE, members)
                session.clear()
                session["member_id"] = member["id"]
                session["_csrf_token"] = generate_csrf_token()

                # Remember me → cookie 30 days. 
                if request.form.get("remember") == "1":
                    session.permanent = True
                else:
                    session.permanent = False

                return redirect(url_for("home"))

        return render_template("login.html", error="Invalid username or password.")

    return render_template("login.html")

@app.route("/members")
def members_list():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "view_members"):
        abort(403, description="You do not have permission for this action.")

    members = load_data(MEMBER_FILE)

    executive_members = [m for m in members if m.get("type") == "Executive" and not m.get("deleted", False)]
    general_members = [m for m in members if m.get("type") == "General" and not m.get("deleted", False)]

    title_order = get_executive_titles()

    def title_rank(member):
        title = member.get("title", "")
        if title in title_order:
            return title_order.index(title)
        return len(title_order)

    executive_members.sort(key=title_rank)

    viewer_type = member.get("type")

    watcher_accounts = []
    admin_accounts = []

    if viewer_type == "Watcher":
        watcher_accounts = [m for m in members if m.get("type") == "Watcher" and not m.get("deleted", False)]
        admin_accounts = [m for m in members if m.get("type") == "Admin" and not m.get("deleted", False)]
    elif viewer_type == "Admin":
        admin_accounts = [m for m in members if m.get("type") == "Admin" and not m.get("deleted", False)]

    return render_template(
        "members_list.html",
        executive_members=executive_members,
        general_members=general_members,
        watcher_accounts=watcher_accounts,
        admin_accounts=admin_accounts,
        session_member=member,
        has_permission=has_permission
    )

@app.route("/members/add", methods=["GET", "POST"])
def add_member_page():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "manage_members"):
        abort(403, description="You do not have permission for this action.")

    current_role = member["type"]
    from core.permissions import ADDABLE_ROLES
    addable_roles = ADDABLE_ROLES.get(current_role, [])

    if not addable_roles:
        return "You are not allowed to add members.", 403

    if request.method == "POST":
        members = load_data(MEMBER_FILE)

        name = request.form.get("name", "").strip()
        role = request.form.get("role")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        title = request.form.get("title", "").strip() if role == "Executive" else ""
        portfolio = request.form.get("portfolio", "").strip() if role == "Executive" else ""

        if role not in addable_roles:
            return render_template("add_member.html", error="You are not allowed to add this role.", addable_roles=addable_roles, executive_titles=get_executive_titles(), departments=get_departments())

        if not name or not username or len(password) < 4:
            return render_template("add_member.html", error="Please fill all required fields correctly (password min 4 chars).", addable_roles=addable_roles, executive_titles=get_executive_titles(), departments=get_departments())

        if role != "Admin" and role != "Watcher" and not phone:
            return render_template("add_member.html", error="Phone is required for this role.", addable_roles=addable_roles, executive_titles=get_executive_titles(), departments=get_departments())

        for m in members:
            if m.get("username", "").lower() == username.lower():
                return render_template("add_member.html", error="Username already exists.", addable_roles=addable_roles, executive_titles=get_executive_titles(), departments=get_departments())

        new_id = max((m["id"] for m in members), default=0) + 1
        
        # Member ID is manually entered for Executive/General
        member_code = request.form.get("member_code", "").strip()
        department = request.form.get("department", "").strip() if role in ("Executive", "General") else ""

        if role in ("Executive", "General"):
            if not member_code:
                return render_template("add_member.html", error="Member ID is required.", addable_roles=addable_roles, executive_titles=get_executive_titles(), departments=get_departments())

            for m in members:
                if m.get("member_code") == member_code:
                    return render_template("add_member.html", error="This Member ID already exists.", addable_roles=addable_roles, executive_titles=get_executive_titles(), departments=get_departments())
        else:
            member_code = None

        new_member = {
            "id": new_id,
            "name": name,
            "phone": phone,
            "email": email,
            "username": username,
            "password": hash_password(password),
            "type": role,
            "title": title,
            "portfolio": portfolio,
            "member_code": member_code,
            "department": department,
            "active": True,
            "temp_permissions": [],
            "deleted": False
        }

        if role != "Admin" and role != "Watcher":
            new_member["requests_managed"] = 0
            new_member["donors_contacted"] = 0
            new_member["successful_cases"] = 0
            new_member["blood_managed"] = 0

        members.append(new_member)
        save_data(MEMBER_FILE, members)
        push_notification(
            kind="member",
            title="New member added",
            message=f"{name} joined as {role}"
                     + (f" ({title})" if title else ""),
            link=url_for("members_list"),
            audience="all",
            extra={"member_id": new_id, "role": role},
        )
        return redirect(url_for("members_list"))

    return render_template("add_member.html", addable_roles=addable_roles, executive_titles=get_executive_titles(), departments=get_departments())

@app.route("/access")
def manage_access():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "manage_access"):
        abort(403, description="You do not have permission for this action.")

    members = load_data(MEMBER_FILE)
    general_members = [m for m in members if m.get("type") == "General"]

    return render_template("manage_access.html", general_members=general_members)


@app.route("/access/<int:member_id>", methods=["GET", "POST"])
def manage_access_member(member_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "manage_access"):
        abort(403, description="You do not have permission for this action.")

    members = load_data(MEMBER_FILE)
    target = None
    for m in members:
        if m.get("id") == member_id and m.get("type") == "General":
            target = m
            break

    if target is None:
        abort(404, description="Member not found.")

    if request.method == "POST":
        selected = request.form.getlist("permissions")
        target["temp_permissions"] = selected
        save_data(MEMBER_FILE, members)
        return redirect(url_for("manage_access"))

    return render_template(
        "manage_access_edit.html",
        member=target,
        grantable_permissions=GRANTABLE_PERMISSIONS
    )

VALID_BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

@app.route("/donors")
def donors_list():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "view_donors"):
        abort(403, description="You do not have permission for this action.")

    donors = load_data(DONOR_FILE)

    selected_group = request.args.get("blood_group", "")
    if selected_group:
        donors = [d for d in donors if d.get("blood_group") == selected_group]

    selected_department = request.args.get("department", "")
    if selected_department:
        donors = [d for d in donors if d.get("department") == selected_department]

    search = request.args.get("search", "").strip()
    if search:
        needle = search.lower()
        donors = [
            d for d in donors
            if needle in d.get("name", "").lower()
            or needle in d.get("phone", "").lower()
            or needle in d.get("area", "").lower()
            or needle in (d.get("donor_code") or "").lower()
        ]

    return render_template(
        "donors_list.html",
        donors=donors,
        selected_group=selected_group,
        selected_department=selected_department,
        search=search,
        departments=get_departments(),
        session_member=member,
        has_permission=has_permission
    )

@app.route("/donors/add", methods=["GET", "POST"])
def add_donor_page():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "add_donor"):
        abort(403, description="You do not have permission for this action.")

    if request.method == "POST":
        donors = load_data(DONOR_FILE)

        name = request.form.get("name", "").strip()
        blood_group = request.form.get("blood_group", "").strip().upper()
        phone = request.form.get("phone", "").strip()
        area = request.form.get("area", "").strip()
        donor_code = request.form.get("donor_code", "").strip()
        department = request.form.get("department", "").strip()

        if not name or blood_group not in VALID_BLOOD_GROUPS or not area:
            return render_template(
                "add_donor.html",
                departments=get_departments(),
                error="Please fill all fields correctly."
            )

        clean_phone = phone.replace(" ", "").replace("-", "").replace("+", "")
        if not clean_phone.isdigit() or len(clean_phone) < 10:
            return render_template(
                "add_donor.html",
                departments=get_departments(),
                error="Invalid phone number."
            )

        for d in donors:
            existing = d.get("phone", "").replace(" ", "").replace("-", "").replace("+", "")
            if existing == clean_phone:
                return render_template(
                    "add_donor.html",
                    departments=get_departments(),
                    error=f"A donor with this phone already exists (ID: {d['id']}, {d['name']})."
                )

        # Area → Latitude / Longitude (OpenStreetMap Nominatim)
        latitude, longitude = geocode_location(area)
        if latitude is None or longitude is None:
            return render_template(
                "add_donor.html",
                departments=get_departments(),
                error="Could not find location for this area. Please try a more specific name (e.g. Mirpur, Dhaka)."
            )

        new_id = max((d["id"] for d in donors), default=0) + 1

        donors.append({
            "id": new_id,
            "donor_code": donor_code,
            "department": department,
            "name": name,
            "blood_group": blood_group,
            "phone": phone,
            "area": area,
            "latitude": latitude,
            "longitude": longitude,
            "active": True
        })

        save_data(DONOR_FILE, donors)
        return redirect(url_for("donors_list"))

    return render_template("add_donor.html", departments=get_departments())

@app.route("/donors/<int:donor_id>/edit", methods=["GET", "POST"])
def edit_donor_page(donor_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "edit_donor"):
        abort(403, description="You do not have permission for this action.")

    donors = load_data(DONOR_FILE)
    donor = next((d for d in donors if d["id"] == donor_id), None)
    if donor is None:
        return "Donor not found.", 404

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        blood_group = request.form.get("blood_group", "").strip().upper()
        phone = request.form.get("phone", "").strip()
        area = request.form.get("area", "").strip()
        donor_code = request.form.get("donor_code", "").strip()
        department = request.form.get("department", "").strip()
        active = "active" in request.form

        if not name or blood_group not in VALID_BLOOD_GROUPS or not area:
            return render_template(
                "edit_donor.html",
                donor=donor,
                departments=get_departments(),
                error="Please fill all required fields correctly."
            )

        clean_phone = phone.replace(" ", "").replace("-", "").replace("+", "")
        if not clean_phone.isdigit() or len(clean_phone) < 10:
            return render_template(
                "edit_donor.html",
                donor=donor,
                departments=get_departments(),
                error="Invalid phone number."
            )

        # phone unique check (exclude current donor)
        for d in donors:
            if d["id"] == donor_id:
                continue
            existing = d.get("phone", "").replace(" ", "").replace("-", "").replace("+", "")
            if existing == clean_phone:
                return render_template(
                    "edit_donor.html",
                    donor=donor,
                    departments=get_departments(),
                    error=f"A donor with this phone already exists (ID: {d['id']}, {d['name']})."
                )

        # area পরিবর্তন হলে নতুন করে geocode করো
        if area != donor.get("area"):
            lat, lon = geocode_location(area)
            if lat is not None and lon is not None:
                donor["latitude"] = lat
                donor["longitude"] = lon

        donor["name"] = name
        donor["blood_group"] = blood_group
        donor["phone"] = phone
        donor["area"] = area
        donor["donor_code"] = donor_code
        donor["department"] = department
        donor["active"] = active

        save_data(DONOR_FILE, donors)
        return redirect(url_for("donors_list"))

    return render_template(
        "edit_donor.html",
        donor=donor,
        departments=get_departments()
    )


@app.route("/donors/<int:donor_id>/delete", methods=["POST"])
def delete_donor(donor_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "delete_donor"):
        abort(403, description="You do not have permission for this action.")

    donors = load_data(DONOR_FILE)
    donor = next((d for d in donors if d["id"] == donor_id), None)
    if donor is None:
        return "Donor not found.", 404

    # Soft delete: mark inactive instead of erasing the record. A hard
    # delete here would orphan the donor_id still referenced by past
    # donations/contacts/fulfillments and permanently lose their info.
    donor["active"] = False
    save_data(DONOR_FILE, donors)
    return redirect(url_for("donors_list"))

@app.route("/requests")
def requests_list():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "view_requests"):
        abort(403, description="You do not have permission for this action.")

    requests_data = load_data(REQUEST_FILE)

    for r in requests_data:
        r.setdefault("fulfillments", [])
        r["collected_bags"] = request_collected_bags(r)
        r["remaining_bags"] = request_bags_remaining(r)
        r["effective_status"] = compute_request_status(r)

    open_requests = [r for r in requests_data if r["effective_status"] == "Open"]
    partial_requests = [r for r in requests_data if r["effective_status"] == "Partial"]
    incomplete_requests = [r for r in requests_data if r["effective_status"] == "Incomplete"]
    fulfilled_requests = [r for r in requests_data if r["effective_status"] == "Fulfilled"]

    return render_template(
        "requests_list.html",
        open_requests=open_requests,
        partial_requests=partial_requests,
        incomplete_requests=incomplete_requests,
        fulfilled_requests=fulfilled_requests,
        session_member=member,
        has_permission=has_permission
    )


@app.route("/requests/create", methods=["GET", "POST"])
def create_request_page():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "create_request"):
        abort(403, description="You do not have permission for this action.")

    if request.method == "POST":
        requests_data = load_data(REQUEST_FILE)

        blood_group = request.form.get("blood_group", "").upper()
        urgency = request.form.get("urgency")

        patient_problem = request.form.get("patient_problem", "").strip()
        hemoglobin = request.form.get("hemoglobin", "").strip()
        donation_date = request.form.get("donation_date", "").strip()
        donation_time = request.form.get("donation_time", "").strip()
        donation_place = request.form.get("donation_place", "").strip()
        contact = request.form.get("contact", "").strip()

        if blood_group not in VALID_BLOOD_GROUPS or urgency not in ("Normal", "Emergency"):
            return render_template("create_request.html", error="Please fill all fields correctly.")

        if not donation_date or not donation_place or not contact:
            return render_template("create_request.html", error="Donation date, place, and contact are required.")

        try:
            datetime.strptime(donation_date, "%Y-%m-%d")
        except ValueError:
            return render_template("create_request.html", error="Invalid donation date.")

        try:
            bags = int(request.form.get("bags"))
        except (ValueError, TypeError):
            return render_template("create_request.html", error="Invalid number of bags.")

        if bags <= 0:
            return render_template("create_request.html", error="Number of bags must be greater than 0.")

        latitude, longitude = geocode_location(donation_place)

        if latitude is None or longitude is None:
            return render_template(
                "create_request.html",
                error=f"Could not locate '{donation_place}' on the map. Please enter a more specific place name (e.g. include area/city, like 'Dhaka Medical College Hospital, Dhaka')."
            )

        new_id = max((r["id"] for r in requests_data), default=0) + 1

        requests_data.append({
            "id": new_id,
            "blood_group": blood_group,
            "area": donation_place,
            "latitude": latitude,
            "longitude": longitude,
            "bags": bags,
            "urgency": urgency,
            "patient_problem": patient_problem,
            "hemoglobin": hemoglobin,
            "donation_date": donation_date,
            "donation_time": donation_time,
            "donation_place": donation_place,
            "contact": contact,
            "status": "Open",
            "created_by": member["id"],
            "fulfillments": [],
            "collected_bags": 0,
            "created_date": date.today().isoformat(),
            "completed_date": None
        })

        save_data(REQUEST_FILE, requests_data)
        push_notification(
            kind="request",
            title="New blood request",
            message=f"{blood_group} · {bags} bag(s) · {urgency} — {donation_place}",
            link=url_for("requests_list"),
            audience="all",
            extra={
                "request_id": new_id,
                "blood_group": blood_group,
                "bags": bags,
                "urgency": urgency,
            },
        )
        return redirect(url_for("requests_list"))

    return render_template("create_request.html")

def _find_matches(req, donors, donations):
    matches = []
    for donor in donors:
        if donor.get("blood_group") != req["blood_group"]:
            continue
        if not donor.get("active", True):
            continue
        eligibility = get_eligibility(donor["id"], donations)
        if not eligibility["eligible"]:
            continue
        if "latitude" not in donor or "longitude" not in donor:
            continue

        distance = calculate_distance(req["latitude"], req["longitude"], donor["latitude"], donor["longitude"])

        donation_count = sum(1 for d in donations if d["donor_id"] == donor["id"])
        total_bags = sum(d.get("bags", 0) for d in donations if d["donor_id"] == donor["id"])

        matches.append({
            "donor": donor,
            "distance": distance,
            "donation_count": donation_count,
            "total_bags": total_bags
        })

    matches.sort(key=lambda x: x["distance"])
    return matches


@app.route("/requests/<int:request_id>/matches")
def match_donors_page(request_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "complete_request"):
        abort(403, description="You do not have permission for this action.")

    requests_data = load_data(REQUEST_FILE)
    req = next((r for r in requests_data if r["id"] == request_id), None)
    if req is None:
        return "Request not found.", 404

    donors = load_data(DONOR_FILE)
    donations = load_data(DONATION_FILE)
    matches = _find_matches(req, donors, donations)

    return render_template("match_donors.html", req=req, matches=matches)


def _clean_phone(p):
    return (p or "").replace(" ", "").replace("-", "").replace("+", "")


def _grant_member_credit(members, req, member_id, bags_just_added):
    """Point 4/11: whichever club member manages a donor gets credit.
    'Requests Managed' is credited once per distinct request per
    member (not once per bag); 'Blood Managed' accumulates per bag.
    fulfillments already includes the just-added entry."""
    member = next((m for m in members if m.get("id") == member_id), None)
    if member is None:
        return

    prior = [
        f for f in req["fulfillments"][:-1]
        if f.get("source") == "club" and f.get("managed_by") == member_id
    ]

    if not prior:
        member["requests_managed"] = member.get("requests_managed", 0) + 1
        member["successful_cases"] = member.get("successful_cases", 0) + 1

    member["blood_managed"] = member.get("blood_managed", 0) + bags_just_added


@app.route("/requests/<int:request_id>/complete", methods=["GET", "POST"])
def complete_request_page(request_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "complete_request"):
        abort(403, description="You do not have permission for this action.")

    requests_data = load_data(REQUEST_FILE)
    req = next((r for r in requests_data if r["id"] == request_id), None)
    if req is None:
        return "Request not found.", 404

    req.setdefault("fulfillments", [])
    sync_request_status(req)

    if req["status"] in ("Partial", "Incomplete"):
        return "This request has passed its 3-day window and is locked. It can no longer be edited.", 403
    if req["status"] == "Fulfilled":
        return "This request is already fully completed.", 400

    error = None

    if request.method == "POST":
        action = request.form.get("action", "add")
        donors = load_data(DONOR_FILE)
        members = load_data(MEMBER_FILE)
        donations = load_data(DONATION_FILE)

        if action == "remove":
            if not has_permission(member, "complete_request"):
                abort(403, description="You do not have permission for this action.")
            try:
                fulfillment_id = int(request.form.get("fulfillment_id"))
            except (ValueError, TypeError):
                fulfillment_id = None

            removed = next((f for f in req["fulfillments"] if f.get("id") == fulfillment_id), None)
            req["fulfillments"] = [f for f in req["fulfillments"] if f.get("id") != fulfillment_id]

            # Undo the linked donation record (eligibility) and the
            # managing member's credit so a correction doesn't inflate stats.
            if removed is not None:
                if removed.get("donation_id") is not None:
                    donations = [d for d in donations if d.get("id") != removed["donation_id"]]
                    save_data(DONATION_FILE, donations)

                if removed.get("source") == "club" and removed.get("managed_by"):
                    member = next((m for m in members if m.get("id") == removed["managed_by"]), None)
                    if member is not None:
                        member["blood_managed"] = max(0, member.get("blood_managed", 0) - removed.get("bags", 0))
                        still_has = any(
                            f.get("source") == "club" and f.get("managed_by") == removed["managed_by"]
                            for f in req["fulfillments"]
                        )
                        if not still_has:
                            member["requests_managed"] = max(0, member.get("requests_managed", 0) - 1)
                            member["successful_cases"] = max(0, member.get("successful_cases", 0) - 1)
                        save_data(MEMBER_FILE, members)

            sync_request_status(req)
            save_data(REQUEST_FILE, requests_data)
            return redirect(url_for("complete_request_page", request_id=request_id))

        elif action == "add":
            remaining = request_bags_remaining(req)
            if remaining <= 0:
                error = "Requested bags are already fully managed for this request."
            else:
                source = request.form.get("source", "club")
                today_str = date.today().isoformat()
                next_fid = max((f.get("id", 0) for f in req["fulfillments"]), default=0) + 1

                if source == "club":
                    # ---- Point 3/9/10: one club donor = exactly 1 bag, no manual quantity ----
                    try:
                        donor_id = int(request.form.get("donor_id"))
                    except (ValueError, TypeError):
                        donor_id = None
                        error = "Please select a donor."

                    if donor_id is not None:
                        donor = next((d for d in donors if d["id"] == donor_id), None)
                        already_used = any(
                            f.get("source") == "club" and f.get("donor_id") == donor_id
                            for f in req["fulfillments"]
                        )
                        if donor is None:
                            error = "Donor not found."
                        elif already_used:
                            error = "This donor has already been recorded for this request."
                        elif donor.get("blood_group") != req["blood_group"]:
                            error = "Donor blood group does not match the requested blood group."
                        elif not donor.get("active", True):
                            error = "This donor is inactive."
                        else:
                            eligibility = get_eligibility(donor_id, donations)
                            if not eligibility["eligible"]:
                                error = f"Donor not eligible until {eligibility['next_date']}."
                            else:
                                manager = member
                                donation_rec = create_automatic_donation(
                                    donor, donations, today_str, 1,
                                    source="club", request_id=req["id"],
                                    managed_by=manager["id"], managed_by_name=manager["name"]
                                )
                                save_data(DONATION_FILE, donations)

                                entry = {
                                    "id": next_fid,
                                    "source": "club",
                                    "donor_id": donor["id"],
                                    "donor_name": donor["name"],
                                    "blood_group": donor["blood_group"],
                                    "bags": 1,
                                    "managed_by": manager["id"],
                                    "managed_by_name": manager["name"],
                                    "date": today_str,
                                    "donation_id": donation_rec["id"]
                                }
                                req["fulfillments"].append(entry)

                                _grant_member_credit(members, req, manager["id"], 1)
                                save_data(MEMBER_FILE, members)

                                sync_request_status(req)
                                save_data(REQUEST_FILE, requests_data)
                                return redirect(url_for("complete_request_page", request_id=request_id))

                elif source == "external":
                    # ---- Point 1/2/5: managed outside the club (donor donated
                    # elsewhere, or patient's family/others arranged it).
                    # Never counted in club statistics. Blood-group match is
                    # optional here (we may not be able to verify it). ----
                    donor_name = request.form.get("ext_donor_name", "").strip()
                    donor_phone = request.form.get("ext_donor_phone", "").strip()
                    donor_bg = request.form.get("ext_blood_group", "").strip().upper()
                    add_to_system = request.form.get("add_to_donor_list") == "on"

                    if not donor_name:
                        donor_name = "Unknown / Family arranged"

                    donor_obj = None
                    if donor_phone:
                        clean = _clean_phone(donor_phone)
                        donor_obj = next((d for d in donors if _clean_phone(d.get("phone", "")) == clean), None)

                    if donor_obj is None and add_to_system and donor_name != "Unknown / Family arranged":
                        new_id = max((d["id"] for d in donors), default=0) + 1
                        donor_obj = {
                            "id": new_id,
                            "name": donor_name,
                            "blood_group": donor_bg if donor_bg in VALID_BLOOD_GROUPS else req["blood_group"],
                            "phone": donor_phone,
                            "area": req.get("area", ""),
                            "latitude": req.get("latitude", 0),
                            "longitude": req.get("longitude", 0),
                            "active": True
                        }
                        donors.append(donor_obj)
                        save_data(DONOR_FILE, donors)

                    manager = member
                    donation_id = None

                    # Only create a donation record (for eligibility tracking)
                    # when we actually have a system donor tied to it.
                    if donor_obj is not None:
                        donation_rec = create_automatic_donation(
                            donor_obj, donations, today_str, 1,
                            source="external", request_id=req["id"],
                            managed_by=None, managed_by_name=None
                        )
                        save_data(DONATION_FILE, donations)
                        donation_id = donation_rec["id"]

                    entry = {
                        "id": next_fid,
                        "source": "external",
                        "donor_id": donor_obj["id"] if donor_obj else None,
                        "donor_name": donor_obj["name"] if donor_obj else donor_name,
                        "blood_group": donor_bg or (donor_obj["blood_group"] if donor_obj else req["blood_group"]),
                        "bags": 1,
                        "managed_by": None,
                        "managed_by_name": None,
                        "recorded_by": manager["id"],
                        "recorded_by_name": manager["name"],
                        "date": today_str,
                        "donation_id": donation_id
                    }
                    req["fulfillments"].append(entry)

                    sync_request_status(req)
                    save_data(REQUEST_FILE, requests_data)
                    return redirect(url_for("complete_request_page", request_id=request_id))
                else:
                    error = "Invalid source."

    donors = load_data(DONOR_FILE)
    donations = load_data(DONATION_FILE)
    candidates = _find_matches(req, donors, donations)
    used_donor_ids = {f.get("donor_id") for f in req["fulfillments"] if f.get("source") == "club"}
    candidates = [c for c in candidates if c["donor"]["id"] not in used_donor_ids]

    donor_id = request.args.get("donor_id", "")
    return render_template(
        "complete_request.html",
        req=req,
        status=compute_request_status(req),
        remaining=request_bags_remaining(req),
        deadline=get_request_deadline(req),
        donor_id=donor_id,
        candidates=candidates,
        error=error
    )

@app.route("/titles", methods=["GET", "POST"])
def manage_titles():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if member["type"] not in ("Admin", "Watcher"):
        abort(403, description="You do not have permission for this action.")

    from core.permissions import add_executive_title

    if request.method == "POST":
        new_title = request.form.get("new_title", "").strip()
        if not new_title:
            return render_template("manage_titles.html", titles=get_executive_titles(), error="Title cannot be empty.")
        if not add_executive_title(new_title):
            return render_template("manage_titles.html", titles=get_executive_titles(), error="This title already exists.")
        return render_template("manage_titles.html", titles=get_executive_titles(), message="Title added successfully!")

    return render_template("manage_titles.html", titles=get_executive_titles())

@app.route("/members/<int:member_id>/edit", methods=["GET", "POST"])
def edit_member_page(member_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "edit_data"):
        abort(403, description="You do not have permission for this action.")

    members = load_data(MEMBER_FILE)
    target = next((m for m in members if m["id"] == member_id and m.get("type") in ("Executive", "General") and not m.get("deleted", False)), None)
    if target is None:
        abort(404, description="Member not found.")

    current_role = member["type"]
    assignable_roles = ASSIGNABLE_ROLES.get(current_role, [])
    can_change_role = bool(assignable_roles)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        member_code = request.form.get("member_code", "").strip()
        department = request.form.get("department", "").strip()
        new_role = request.form.get("role")
        title = request.form.get("title", "").strip()
        portfolio = request.form.get("portfolio", "").strip()

        if not name:
            return render_template("edit_member.html", member=target, departments=get_departments(), titles=get_executive_titles(), assignable_roles=assignable_roles, can_change_role=can_change_role, error="Name is required.")

        if can_change_role and new_role != target["type"]:
            if not can_assign_role(current_role, new_role):
                return render_template("edit_member.html", member=target, departments=get_departments(), titles=get_executive_titles(), assignable_roles=assignable_roles, can_change_role=can_change_role, error="You are not allowed to assign this role.")
            target["type"] = new_role

        target["name"] = name
        target["phone"] = phone
        target["email"] = email
        target["member_code"] = member_code
        target["department"] = department
        target["title"] = title if target["type"] == "Executive" else ""
        target["portfolio"] = portfolio if target["type"] == "Executive" else ""

        save_data(MEMBER_FILE, members)
        return redirect(url_for("members_list"))

    return render_template(
        "edit_member.html",
        member=target,
        departments=get_departments(),
        titles=get_executive_titles(),
        assignable_roles=assignable_roles,
        can_change_role=can_change_role
    )


def _can_reset_credentials(current_role, target_role):
    if current_role == "Watcher":
        return True
    if current_role == "Admin":
        return target_role in ("Executive", "General")
    if current_role == "Executive":
        return target_role == "General"
    return False


@app.route("/members/<int:member_id>/credentials", methods=["GET", "POST"])
def reset_credentials_page(member_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    members = load_data(MEMBER_FILE)
    target = next((m for m in members if m["id"] == member_id and not m.get("deleted", False)), None)
    if target is None:
        abort(404, description="Member not found.")

    current_role = member["type"]
    if not _can_reset_credentials(current_role, target["type"]):
        abort(403, description="You do not have permission for this action.")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or len(password) < 4:
            return render_template("reset_credentials.html", member=target, error="Username required, password min 4 chars.")

        for m in members:
            if m["id"] != member_id and m.get("username", "").lower() == username.lower():
                return render_template("reset_credentials.html", member=target, error="Username already taken.")

        target["username"] = username
        target["password"] = hash_password(password)
        save_data(MEMBER_FILE, members)
        return redirect(url_for("members_list"))

    return render_template("reset_credentials.html", member=target)


@app.route("/profile/password", methods=["GET", "POST"])
def change_own_password():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    # Admins can't change their own password -- only the Watcher can reset it for them
    if member["type"] == "Admin":
        return "Admins cannot change their own password. Contact the Watcher.", 403

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "").strip()

        members = load_data(MEMBER_FILE)
        me = next((m for m in members if m["id"] == member["id"]), None)
        if me is None:
            return "Account not found.", 404

        if not verify_password(current_password, me.get("password", "")):
            return render_template("change_password.html", error="Current password is incorrect.")

        if len(new_password) < 4:
            return render_template("change_password.html", error="New password must be at least 4 characters.")

        me["password"] = hash_password(new_password)
        save_data(MEMBER_FILE, members)
        # session keeps member_id only; password already saved to JSON
        session["_csrf_token"] = generate_csrf_token()
        return render_template("change_password.html", message="Password changed successfully!")

    return render_template("change_password.html")


@app.route("/members/<int:member_id>/delete", methods=["POST"])
def delete_member(member_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "delete_data"):
        abort(403, description="You do not have permission for this action.")

    members = load_data(MEMBER_FILE)
    target = next((m for m in members if m["id"] == member_id), None)
    if target is None:
        abort(404, description="Member not found.")

    target["deleted"] = True
    target["active"] = False
    save_data(MEMBER_FILE, members)
    return redirect(url_for("members_list"))

# =====================================
# Donations
# =====================================

@app.route("/donations")
def donations_list():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "view_donors"):
        abort(403, description="You do not have permission for this action.")

    donations = load_data(DONATION_FILE)
    donations.sort(key=lambda d: d.get("date", ""), reverse=True)
    for d in donations:
        d.setdefault("source", "club")

    return render_template(
        "donations_list.html",
        donations=donations,
        session_member=member,
        has_permission=has_permission
    )

@app.route("/donations/add", methods=["GET", "POST"])
def add_donation_page():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "add_donation"):
        abort(403, description="You do not have permission for this action.")

    donors = load_data(DONOR_FILE)
    active_donors = [d for d in donors if d.get("active", True)]

    if request.method == "POST":
        try:
            donor_id = int(request.form.get("donor_id"))
            bags = int(request.form.get("bags"))
        except (ValueError, TypeError):
            return render_template("add_donation.html", donors=active_donors, error="Please select a donor and enter a valid number of bags.")

        donation_date = request.form.get("date", "").strip()
        source = request.form.get("source", "club")
        if source not in ("club", "external"):
            source = "club"

        try:
            datetime.strptime(donation_date, "%Y-%m-%d")
        except ValueError:
            return render_template("add_donation.html", donors=active_donors, error="Invalid date format. Please use YYYY-MM-DD.")

        if bags <= 0:
            return render_template("add_donation.html", donors=active_donors, error="Number of bags must be greater than 0.")

        donor = next((d for d in donors if d["id"] == donor_id), None)
        if donor is None:
            return render_template("add_donation.html", donors=active_donors, error="Donor not found.")

        donations = load_data(DONATION_FILE)

        manager = member if source == "club" else None
        create_automatic_donation(
            donor, donations, donation_date, bags,
            source=source,
            managed_by=manager["id"] if manager else None,
            managed_by_name=manager["name"] if manager else None
        )

        return redirect(url_for("donations_list"))

    return render_template("add_donation.html", donors=active_donors)

# =====================================
# Notice Board
# =====================================

@app.route("/notices")
def notices_list():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "view_notices"):
        abort(403, description="You do not have permission for this action.")

    notices = load_data(NOTICE_FILE)
    can_manage = has_permission(member, "manage_notices")

    if not can_manage:
        notices = [n for n in notices if n.get("active", True)]

    # Executive-only notices: visible to Executive / Admin / Watcher (and managers)
    is_exec_viewer = member.get("type") in ("Executive", "Admin", "Watcher") or can_manage
    if not is_exec_viewer:
        notices = [n for n in notices if n.get("audience", "all") != "executives"]

    notices.sort(key=lambda n: n.get("date", ""), reverse=True)

    return render_template(
        "notices_list.html",
        notices=notices,
        session_member=member,
        has_permission=has_permission
    )

@app.route("/notices/add", methods=["GET", "POST"])
def add_notice_page():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "manage_notices"):
        abort(403, description="You do not have permission for this action.")

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        priority = request.form.get("priority", "Normal")
        audience = request.form.get("audience", "all").strip()

        if not title or not message:
            return render_template("add_notice.html", error="Title and message are required.")

        if priority not in ("Normal", "Important", "Emergency"):
            priority = "Normal"
        if audience not in ("all", "executives"):
            audience = "all"

        notices = load_data(NOTICE_FILE)
        new_id = max((n["id"] for n in notices), default=0) + 1

        notice = {
            "id": new_id,
            "title": title,
            "message": message,
            "priority": priority,
            "audience": audience,  # "all" | "executives"
            "date": date.today().isoformat(),
            "posted_by": member["id"],
            "posted_by_name": member["name"],
            "active": True
        }

        notices.append(notice)
        save_data(NOTICE_FILE, notices)

        push_notification(
            kind="notice",
            title=f"Notice: {title}",
            message=message[:120] + ("…" if len(message) > 120 else ""),
            link=url_for("notices_list"),
            audience=audience,
            extra={"notice_id": new_id, "priority": priority},
        )
        return redirect(url_for("notices_list"))

    return render_template("add_notice.html")

@app.route("/notices/<int:notice_id>/edit", methods=["GET", "POST"])
def edit_notice_page(notice_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "manage_notices"):
        abort(403, description="You do not have permission for this action.")

    notices = load_data(NOTICE_FILE)
    notice = next((n for n in notices if n["id"] == notice_id), None)
    if notice is None:
        return "Notice not found.", 404

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        message = request.form.get("message", "").strip()
        priority = request.form.get("priority", "Normal")
        audience = request.form.get("audience", notice.get("audience", "all")).strip()

        if not title or not message:
            return render_template("edit_notice.html", notice=notice, error="Title and message are required.")

        if priority not in ("Normal", "Important", "Emergency"):
            priority = "Normal"
        if audience not in ("all", "executives"):
            audience = "all"

        notice["title"] = title
        notice["message"] = message
        notice["priority"] = priority
        notice["audience"] = audience
        notice["edited_by"] = member["id"]
        notice["edited_by_name"] = member["name"]
        notice["edited_date"] = date.today().isoformat()

        save_data(NOTICE_FILE, notices)
        return redirect(url_for("notices_list"))

    return render_template("edit_notice.html", notice=notice)

@app.route("/notices/<int:notice_id>/toggle", methods=["POST"])
def toggle_notice(notice_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "manage_notices"):
        abort(403, description="You do not have permission for this action.")

    notices = load_data(NOTICE_FILE)
    notice = next((n for n in notices if n["id"] == notice_id), None)
    if notice is None:
        return "Notice not found.", 404

    notice["active"] = not notice.get("active", True)
    save_data(NOTICE_FILE, notices)
    return redirect(url_for("notices_list"))

@app.route("/notices/<int:notice_id>/delete", methods=["POST"])
def delete_notice(notice_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "manage_notices"):
        abort(403, description="You do not have permission for this action.")

    notices = load_data(NOTICE_FILE)
    notice = next((n for n in notices if n["id"] == notice_id), None)
    if notice is None:
        return "Notice not found.", 404

    notices.remove(notice)
    save_data(NOTICE_FILE, notices)
    return redirect(url_for("notices_list"))

# =====================================
# Donor Contact History
# =====================================

@app.route("/donors/<int:donor_id>/contact", methods=["GET", "POST"])
def contact_donor_page(donor_id):
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "contact_donor"):
        abort(403, description="You do not have permission for this action.")

    donors = load_data(DONOR_FILE)
    donor = next((d for d in donors if d["id"] == donor_id), None)
    if donor is None:
        return "Donor not found.", 404

    if request.method == "POST":
        status = request.form.get("status", "").strip()

        if status not in ("Contacted", "Agreed", "Donated", "Failed"):
            return render_template("record_contact.html", donor=donor, error="Please select a valid status.")

        contacts = load_data(CONTACT_FILE)
        members = load_data(MEMBER_FILE)
        db_member = next((m for m in members if m["id"] == member["id"]), None)

        new_id = max((c["id"] for c in contacts), default=0) + 1

        contact = {
            "id": new_id,
            "member_id": member["id"],
            "member_name": member["name"],
            "donor_id": donor["id"],
            "donor_name": donor["name"],
            "blood_group": donor["blood_group"],
            "date": date.today().isoformat(),
            "status": status
        }

        contacts.append(contact)
        save_data(CONTACT_FILE, contacts)

        if db_member is not None:
            db_member["donors_contacted"] = db_member.get("donors_contacted", 0) + 1
            save_data(MEMBER_FILE, members)

        return redirect(url_for("donor_contacts_list", donor_id=donor_id))

    return render_template("record_contact.html", donor=donor)

@app.route("/contacts")
def contacts_list():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "view_contacts"):
        abort(403, description="You do not have permission for this action.")

    contacts = load_data(CONTACT_FILE)

    donor_id = request.args.get("donor_id", type=int)
    if donor_id:
        contacts = [c for c in contacts if c.get("donor_id") == donor_id]

    contacts.sort(key=lambda c: c.get("date", ""), reverse=True)

    donors = load_data(DONOR_FILE)
    donor = next((d for d in donors if d["id"] == donor_id), None) if donor_id else None

    return render_template(
        "contacts_list.html",
        contacts=contacts,
        donor=donor
    )

@app.route("/donors/<int:donor_id>/contacts")
def donor_contacts_list(donor_id):
    return redirect(url_for("contacts_list", donor_id=donor_id))

# =====================================
# Statistics
# =====================================

def _request_period_key(req):
    """Which month/year a request 'belongs to' for statistics:
    completed date if it's Fulfilled, otherwise the point it was
    judged Partial/Incomplete (the 3-day deadline), otherwise the
    date it was needed / created."""
    return (
        req.get("completed_date")
        or str(get_request_deadline(req) or "")
        or req.get("donation_date")
        or req.get("created_date")
        or ""
    )


def _member_period_credit(member_id, reqs):
    """Point 4/6/11: distinct-request credit + bag credit for a
    member, restricted to requests already filtered to a period."""
    requests_managed = 0
    blood_managed = 0
    for r in reqs:
        mine = [f for f in r.get("fulfillments", []) if f.get("source") == "club" and f.get("managed_by") == member_id]
        if not mine:
            continue
        requests_managed += 1
        blood_managed += sum(f.get("bags", 0) for f in mine)
    return requests_managed, blood_managed


def _last_n_months_bags(club_donations, n=6):
    """Total club-donated bags for each of the last n months (oldest first),
    used to drive the dashboard trend chart."""
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(n):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()

    result = []
    for (y, m) in months:
        key = f"{y:04d}-{m:02d}"
        bags = sum(
            d.get("bags", 0) for d in club_donations
            if str(d.get("date", "")).startswith(key)
        )
        label = date(y, m, 1).strftime("%b %Y")
        result.append({"label": label, "bags": bags})
    return result


def _last_n_months_full(requests_data, club_donations, contacts, n=6):
    """Richer month-by-month stats for the last n months (oldest first).
    Used on the Monthly statistics page to show trend / good-vs-bad."""
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(n):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()

    result = []
    for (y, m) in months:
        key = f"{y:04d}-{m:02d}"
        date_from = f"{key}-01"
        if m == 12:
            date_to = f"{y + 1}-01-01"
        else:
            date_to = f"{y:04d}-{m + 1:02d}-01"

        bags = sum(
            d.get("bags", 0) for d in club_donations
            if str(d.get("date", "")).startswith(key)
        )
        donations = len([
            d for d in club_donations
            if str(d.get("date", "")).startswith(key)
        ])
        period_reqs = [r for r in requests_data if _in_range(r.get("_period", ""), date_from, date_to)]
        breakdown = _status_breakdown(period_reqs)
        period_contacts = [c for c in contacts if _in_range(c.get("date", ""), date_from, date_to)]
        donated = len([c for c in period_contacts if c.get("status") == "Donated"])
        failed = len([c for c in period_contacts if c.get("status") == "Failed"])

        result.append({
            "label": date(y, m, 1).strftime("%b %Y"),
            "key": key,
            "bags": bags,
            "donations": donations,
            "fulfilled": breakdown["fulfilled"],
            "partial": breakdown["partial"],
            "incomplete": breakdown["incomplete"],
            "contacts": len(period_contacts),
            "donated": donated,
            "failed": failed,
        })
    return result


def _yearly_comparison(requests_data, club_donations, contacts, n=5):
    """Stats for the last n calendar years (oldest first) for comparison chart."""
    current_year = date.today().year
    years = list(range(current_year - n + 1, current_year + 1))
    result = []
    for y in years:
        date_from = f"{y}-01-01"
        date_to = f"{y + 1}-01-01"
        bags = sum(
            d.get("bags", 0) for d in club_donations
            if _in_range(d.get("date", ""), date_from, date_to)
        )
        donations = len([
            d for d in club_donations
            if _in_range(d.get("date", ""), date_from, date_to)
        ])
        period_reqs = [r for r in requests_data if _in_range(r.get("_period", ""), date_from, date_to)]
        breakdown = _status_breakdown(period_reqs)
        period_contacts = [c for c in contacts if _in_range(c.get("date", ""), date_from, date_to)]
        result.append({
            "label": str(y),
            "year": y,
            "bags": bags,
            "donations": donations,
            "fulfilled": breakdown["fulfilled"],
            "partial": breakdown["partial"],
            "incomplete": breakdown["incomplete"],
            "contacts": len(period_contacts),
            "donated": len([c for c in period_contacts if c.get("status") == "Donated"]),
            "failed": len([c for c in period_contacts if c.get("status") == "Failed"]),
        })
    return result


def _committee_comparison(requests_data, club_donations, contacts, committees):
    """Stats for every committee term (oldest first) for comparison chart."""
    ordered = sorted(committees, key=lambda c: c.get("start_date") or "")
    result = []
    for c in ordered:
        date_from = c.get("start_date")
        date_to = c.get("end_date")  # None = open-ended
        bags = sum(
            d.get("bags", 0) for d in club_donations
            if _in_range(d.get("date", ""), date_from, date_to)
        )
        donations = len([
            d for d in club_donations
            if _in_range(d.get("date", ""), date_from, date_to)
        ])
        period_reqs = [r for r in requests_data if _in_range(r.get("_period", ""), date_from, date_to)]
        breakdown = _status_breakdown(period_reqs)
        period_contacts = [c_ for c_ in contacts if _in_range(c_.get("date", ""), date_from, date_to)]
        result.append({
            "label": _committee_label(c),
            "id": c.get("id"),
            "bags": bags,
            "donations": donations,
            "fulfilled": breakdown["fulfilled"],
            "partial": breakdown["partial"],
            "incomplete": breakdown["incomplete"],
            "contacts": len(period_contacts),
            "donated": len([x for x in period_contacts if x.get("status") == "Donated"]),
            "failed": len([x for x in period_contacts if x.get("status") == "Failed"]),
        })
    return result


def _status_breakdown(reqs):
    return {
        "fulfilled": len([r for r in reqs if r["_status"] == "Fulfilled"]),
        "partial": len([r for r in reqs if r["_status"] == "Partial"]),
        "incomplete": len([r for r in reqs if r["_status"] == "Incomplete"]),
        "open": len([r for r in reqs if r["_status"] == "Open"]),
    }


def _member_role_rank(m, title_order):
    if m.get("type") == "Executive":
        title = m.get("title", "")
        sub = title_order.index(title) if title in title_order else len(title_order)
        return (0, sub)
    return (1, 0)


def _member_designation(m):
    if m.get("type") == "Executive":
        base = m.get("title") or "Executive"
        if m.get("portfolio"):
            base += f" ({m['portfolio']})"
        return base
    return "General Member"


def _in_range(value, date_from, date_to):
    """date_from/date_to are 'YYYY-MM-DD' strings (ISO strings compare
    correctly lexicographically). date_to=None means open-ended (ongoing)."""
    if not value:
        return False
    if date_from and value < date_from:
        return False
    if date_to and value >= date_to:
        return False
    return True


def _period_stats(requests_data, club_donations, contacts, members, title_order, date_from, date_to):
    """Generic period-bounded statistics, used by Monthly, Yearly, and
    Committee-based statistics pages alike."""
    period_donations = [d for d in club_donations if _in_range(d.get("date", ""), date_from, date_to)]
    period_bags = sum(d.get("bags", 0) for d in period_donations)

    period_requests = [r for r in requests_data if _in_range(r["_period"], date_from, date_to)]
    breakdown = _status_breakdown(period_requests)

    period_contacts = [c for c in contacts if _in_range(c.get("date", ""), date_from, date_to)]

    summary = {
        "total_donations": len(period_donations),
        "total_bags": period_bags,
        "fulfilled_requests": breakdown["fulfilled"],
        "partial_requests": breakdown["partial"],
        "incomplete_requests": breakdown["incomplete"],
        "total_contacts": len(period_contacts),
        "total_agreed": len([c for c in period_contacts if c.get("status") == "Agreed"]),
        "total_donated": len([c for c in period_contacts if c.get("status") == "Donated"]),
        "total_failed": len([c for c in period_contacts if c.get("status") == "Failed"])
    }

    eligible_members = [
        m for m in members
        if not m.get("deleted", False) and m.get("type") in ("Executive", "General")
    ]
    eligible_members.sort(key=lambda m: _member_role_rank(m, title_order))

    member_rows = []
    for m in eligible_members:
        m_contacts = [c for c in period_contacts if c.get("member_id") == m["id"]]
        requests_managed, blood_managed = _member_period_credit(m["id"], period_requests)

        member_rows.append({
            "name": m["name"],
            "designation": _member_designation(m),
            "contacted": len(m_contacts),
            "agreed": len([c for c in m_contacts if c.get("status") == "Agreed"]),
            "donated": len([c for c in m_contacts if c.get("status") == "Donated"]),
            "failed": len([c for c in m_contacts if c.get("status") == "Failed"]),
            "requests_managed": requests_managed,
            "blood_managed": blood_managed
        })

    return summary, member_rows


def _committee_label(committee):
    def fmt(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d").strftime("%B %Y")
        except (ValueError, TypeError):
            return d or "?"
    start = fmt(committee.get("start_date"))
    end = fmt(committee.get("end_date")) if committee.get("end_date") else "Present"
    return f"{start} - {end}"


@app.route("/statistics")
def statistics_page():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "view_statistics"):
        abort(403, description="You do not have permission for this action.")

    donors = load_data(DONOR_FILE)
    donations = load_data(DONATION_FILE)
    requests_data = load_data(REQUEST_FILE)
    contacts = load_data(CONTACT_FILE)
    members = load_data(MEMBER_FILE)

    for r in requests_data:
        r.setdefault("fulfillments", [])
        r["collected_bags"] = request_collected_bags(r)
        r["_status"] = compute_request_status(r)
        r["_period"] = _request_period_key(r)

    club_donations = [d for d in donations if d.get("source", "club") != "external"]
    overall_bags = sum(d.get("bags", 0) for d in club_donations)
    overall_breakdown = _status_breakdown(requests_data)
    title_order = get_executive_titles()

    blood_group_counts = {}
    for d in donors:
        bg = d.get("blood_group") or "Unknown"
        blood_group_counts[bg] = blood_group_counts.get(bg, 0) + 1
    bg_order = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
    blood_group_counts = {
        bg: blood_group_counts[bg]
        for bg in bg_order + [b for b in blood_group_counts if b not in bg_order]
        if bg in blood_group_counts
    }

    trend_rows = _last_n_months_bags(club_donations, 6)
    monthly_trend = {
        "labels": [row["label"] for row in trend_rows],
        "bags": [row["bags"] for row in trend_rows]
    }

    month = request.args.get("month", "").strip() or date.today().strftime("%Y-%m")

    date_from = f"{month}-01"
    if month[5:7] == "12":
        date_to = f"{int(month[:4]) + 1}-01-01"
    else:
        date_to = f"{month[:4]}-{int(month[5:7]) + 1:02d}-01"

    summary, member_rows = _period_stats(requests_data, club_donations, contacts, members, title_order, date_from, date_to)
    monthly = {"month": month, **summary}

    # Last 6 months rich stats for the comparison / good-vs-bad chart
    six_month_stats = _last_n_months_full(requests_data, club_donations, contacts, 6)
    bg_stats = _blood_group_donation_stats(club_donations)

    return render_template(
        "statistics.html",
        total_donors=len(donors),
        total_donations=len(club_donations),
        overall_bags=overall_bags,
        overall_breakdown=overall_breakdown,
        blood_group_counts=blood_group_counts,
        monthly_trend=monthly_trend,
        month=month,
        monthly=monthly,
        member_rows=member_rows,
        six_month_stats=six_month_stats,
        bags_by_blood_group=bg_stats["bags_dict"],
        donation_count_by_blood_group=bg_stats["counts_dict"],
    )


@app.route("/statistics/yearly")
def statistics_yearly_page():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "view_statistics"):
        abort(403, description="You do not have permission for this action.")

    donations = load_data(DONATION_FILE)
    requests_data = load_data(REQUEST_FILE)
    contacts = load_data(CONTACT_FILE)
    members = load_data(MEMBER_FILE)

    for r in requests_data:
        r.setdefault("fulfillments", [])
        r["collected_bags"] = request_collected_bags(r)
        r["_status"] = compute_request_status(r)
        r["_period"] = _request_period_key(r)

    club_donations = [d for d in donations if d.get("source", "club") != "external"]
    title_order = get_executive_titles()

    year = request.args.get("year", "").strip() or date.today().strftime("%Y")
    date_from = f"{year}-01-01"
    date_to = f"{int(year) + 1}-01-01"

    summary, member_rows = _period_stats(requests_data, club_donations, contacts, members, title_order, date_from, date_to)
    yearly = {"year": year, **summary}
    period_donations = [
        d for d in club_donations
        if (d.get("date") or "") >= date_from and (d.get("date") or "") < date_to
    ]
    bg_stats = _blood_group_donation_stats(period_donations)

    # Multi-year comparison so user can see which year performed best
    yearly_comparison = _yearly_comparison(requests_data, club_donations, contacts, n=5)

    return render_template(
        "statistics_yearly.html",
        year=year,
        yearly=yearly,
        member_rows=member_rows,
        yearly_comparison=yearly_comparison,
        bags_by_blood_group=bg_stats["bags_dict"],
        donation_count_by_blood_group=bg_stats["counts_dict"],
    )


@app.route("/statistics/committee")
def statistics_committee_page():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))

    if not has_permission(member, "view_statistics"):
        abort(403, description="You do not have permission for this action.")

    donations = load_data(DONATION_FILE)
    requests_data = load_data(REQUEST_FILE)
    contacts = load_data(CONTACT_FILE)
    members = load_data(MEMBER_FILE)
    committees = load_data(COMMITTEE_FILE)

    for r in requests_data:
        r.setdefault("fulfillments", [])
        r["collected_bags"] = request_collected_bags(r)
        r["_status"] = compute_request_status(r)
        r["_period"] = _request_period_key(r)

    club_donations = [d for d in donations if d.get("source", "club") != "external"]
    title_order = get_executive_titles()

    committees_display = [{"id": c["id"], "label": _committee_label(c)} for c in committees]
    committees_display.reverse()

    committee = None
    summary = None
    member_rows = []

    committee_id = request.args.get("committee_id", "").strip()
    if committee_id:
        try:
            committee = next((c for c in committees if c["id"] == int(committee_id)), None)
        except ValueError:
            committee = None

        if committee is not None:
            summary, member_rows = _period_stats(
                requests_data, club_donations, contacts, members, title_order,
                committee.get("start_date"), committee.get("end_date")
            )
            start = committee.get("start_date") or ""
            end = committee.get("end_date") or "9999-12-31"
            period_donations = [
                d for d in club_donations
                if start <= (d.get("date") or "") <= end
            ]
            bg_stats = _blood_group_donation_stats(period_donations)

    # All committees comparison — which term performed best overall
    committee_comparison = _committee_comparison(
        requests_data, club_donations, contacts, committees
    )
    
    if committee is None:
            bg_stats = {"bags_dict": {}, "counts_dict": {}}

    return render_template(
        "statistics_committee.html",
        committees=committees_display,
        committee=committee,
        committee_label=_committee_label(committee) if committee else None,
        summary=summary,
        member_rows=member_rows,
        committee_comparison=committee_comparison,
        bags_by_blood_group=bg_stats["bags_dict"],
        donation_count_by_blood_group=bg_stats["counts_dict"],
    )


@app.route("/committees", methods=["GET", "POST"])
def manage_committees():
    member = require_member()
    if member is None:
        return redirect(url_for("login"))
    if member["type"] not in ("Admin", "Watcher"):
        abort(403, description="You do not have permission for this action.")

    committees = load_data(COMMITTEE_FILE)
    error = None

    if request.method == "POST":
        start_date = request.form.get("start_date", "").strip()

        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            error = "Please choose a valid start date."

        if error is None:
            current = next((c for c in committees if c.get("end_date") is None), None)
            if current is not None:
                if start_date <= current.get("start_date", ""):
                    error = "Start date must be after the current committee's start date."
                else:
                    current["end_date"] = start_date

        if error is None:
            new_id = max((c["id"] for c in committees), default=0) + 1
            committees.append({
                "id": new_id,
                "start_date": start_date,
                "end_date": None
            })
            save_data(COMMITTEE_FILE, committees)
            return redirect(url_for("manage_committees"))

    committees_display = [
        {"id": c["id"], "label": _committee_label(c), "start_date": c["start_date"], "end_date": c.get("end_date") or "Present"}
        for c in committees
    ]
    committees_display.reverse()

    return render_template("manage_committees.html", committees=committees_display, today=date.today().isoformat(), error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    # Never use debug=True on a public server
    socketio.start_background_task(_start_dashboard_push_loop)
    socketio.run(
        app,
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
        host="127.0.0.1",
        port=5000,
        allow_unsafe_werkzeug=True,
    )
