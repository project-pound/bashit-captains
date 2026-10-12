import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "captains.db"
DB_PATH.parent.mkdir(exist_ok=True, parents=True)
OPERATIONS_DB = Path("C:/Users/anujq/OneDrive/Documents/project_pound/bashit_operations/data/operations.db")

app = Flask(__name__)
app.secret_key = "bashit-captains-secret"

CAPTAIN_USERS = {
    "captain1": {"password": "bashit123", "name": "Sanjay Nair", "otp": "246810"},
    "captain2": {"password": "bashit123", "name": "Meera Singh", "otp": "135791"},
    "captain3": {"password": "bashit123", "name": "Rohit Das", "otp": "864209"},
}


def get_db_connection(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS captain_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                name TEXT,
                otp TEXT
            )
            """
        )
        for username, data in CAPTAIN_USERS.items():
            conn.execute(
                "INSERT OR IGNORE INTO captain_users (username, password, name, otp) VALUES (?, ?, ?, ?)",
                (username, data["password"], data["name"], data["otp"]),
            )


def fetch_assignments(captain_name=None):
    if not OPERATIONS_DB.exists():
        return [], []
    conn = sqlite3.connect(OPERATIONS_DB)
    conn.row_factory = sqlite3.Row
    assignments = conn.execute(
        "SELECT * FROM captain_assignments ORDER BY assigned_at DESC"
    ).fetchall()
    leads = conn.execute(
        "SELECT * FROM lead_records ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    lead_map = {row["id"]: row for row in leads}
    if captain_name:
        assignments = [a for a in assignments if a["captain_name"] == captain_name]
    current = []
    past = []
    for a in assignments:
        lead = lead_map.get(a["lead_id"])
        if not lead:
            continue
        detail = {
            "id": a["id"],
            "lead_id": a["lead_id"],
            "captain_name": a["captain_name"],
            "region": a["region"],
            "status": a["status"],
            "assigned_at": a["assigned_at"],
            "event_type": lead["event_type"],
            "customer_name": lead["customer_name"],
            "phone": lead["phone"],
            "city": lead["city"],
            "event_date": lead["event_date"],
            "guest_count": lead["guest_count"],
            "budget": lead["budget"],
            "quote_json": lead["quote_json"],
            "customer_status": lead["status"],
            "current": a["status"] == "assigned",
        }
        if detail["current"]:
            current.append(detail)
        else:
            past.append(detail)
    return current, past


def mask_value(value):
    if value is None:
        return "-"
    text = str(value)
    if len(text) <= 4:
        return "****"
    return text[:2] + "******" + text[-2:]


def mask_past_assignment(detail):
    masked = dict(detail)
    masked["phone"] = mask_value(detail.get("phone"))
    masked["customer_name"] = masked["customer_name"][:2] + "******"
    masked["city"] = "******"
    masked["event_date"] = "**/**/****"
    masked["guest_count"] = "****"
    masked["budget"] = "******"
    return masked


def logged_in():
    return "captain" in session


def render_login(message=""):
    return render_template_string(
        '''
        <html><head><title>BashIt Captain Login</title>
        <style>body{font-family:Arial,sans-serif;background:#f4f6fb;display:flex;justify-content:center;align-items:center;height:100vh;} .card{background:white;padding:30px;border-radius:14px;box-shadow:0 10px 30px rgba(0,0,0,0.08);width:360px;} input{width:100%;padding:12px;margin:8px 0;border:1px solid #dbe2ef;border-radius:10px;} button{width:100%;padding:12px;border:none;background:#0f766e;color:white;border-radius:10px;font-weight:bold;} .msg{color:#b91c1c;margin-bottom:14px;}</style></head><body>
        <div class="card">
            <h2>BashIt Captain Login</h2>
            {% if message %}<div class="msg">{{ message }}</div>{% endif %}
            <form method="post">
                <input name="username" placeholder="Username" required>
                <input name="password" type="password" placeholder="Password" required>
                <input name="otp" placeholder="2FA Code" required>
                <button type="submit">Login</button>
            </form>
        </div>
        </body></html>
        ''',
        message=message,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        otp = request.form.get("otp")
        user = CAPTAIN_USERS.get(username)
        if user and user["password"] == password and user["otp"] == otp:
            session["captain"] = username
            session["captain_name"] = user["name"]
            return redirect(url_for("dashboard"))
        return render_login("Invalid username, password, or 2FA code.")
    return render_login()


@app.route("/logout")
def logout():
    session.pop("captain", None)
    session.pop("captain_name", None)
    return redirect(url_for("login"))


@app.route("/")
def dashboard():
    if not logged_in():
        return redirect(url_for("login"))
    captain_name = session["captain_name"]
    current, past = fetch_assignments(captain_name)
    return render_template_string(
        '''
        <html><head><title>BashIt Captain Dashboard</title>
        <style>body{font-family:Arial,sans-serif;background:#f5f7fb;margin:0;padding:24px;} .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;} .box{background:white;padding:18px;border-radius:12px;box-shadow:0 8px 28px rgba(0,0,0,0.04);margin-bottom:18px;} table{border-collapse:collapse;width:100%;} th,td{border-bottom:1px solid #e7ebf3;padding:10px;text-align:left;} .link{text-decoration:none;color:#0f766e;font-weight:bold;} a.button{display:inline-block;padding:10px 16px;background:#0f766e;color:white;border-radius:10px;text-decoration:none;} </style></head><body>
        <div class="top">
            <h1>{{ captain_name }} Dashboard</h1>
            <a class="button" href="/logout">Logout</a>
        </div>
        <div class="box">
            <h2>Current Assignments</h2>
            <table>
                <tr><th>Lead ID</th><th>Event</th><th>Customer</th><th>City</th><th>Date</th><th>Action</th></tr>
                {% for item in current %}
                <tr><td>{{ item['lead_id'] }}</td><td>{{ item['event_type'] }}</td><td>{{ item['customer_name'] }}</td><td>{{ item['city'] }}</td><td>{{ item['event_date'] }}</td><td><a class="link" href="/assignment/{{ item['lead_id'] }}">View</a></td></tr>
                {% endfor %}
            </table>
        </div>
        <div class="box">
            <h2>Past Assignments</h2>
            <table>
                <tr><th>Lead ID</th><th>Event</th><th>Customer</th><th>City</th><th>Masked Info</th></tr>
                {% for item in past %}
                <tr><td>{{ item['lead_id'] }}</td><td>{{ item['event_type'] }}</td><td>{{ item['customer_name'] }}</td><td>{{ item['city'] }}</td><td><a class="link" href="/assignment/{{ item['lead_id'] }}">View</a></td></tr>
                {% endfor %}
            </table>
        </div>
        </body></html>
        ''',
        captain_name=captain_name,
        current=current,
        past=past,
    )


@app.route("/assignment/<int:lead_id>")
def assignment(lead_id):
    if not logged_in():
        return redirect(url_for("login"))
    captain_name = session["captain_name"]
    current, past = fetch_assignments(captain_name)
    all_assignments = current + past
    detail = next((a for a in all_assignments if a["lead_id"] == lead_id), None)
    if not detail:
        return "Assignment not found", 404
    is_current = detail in current
    if not is_current:
        detail = mask_past_assignment(detail)
    return render_template_string(
        '''
        <html><head><title>Assignment {{ lead_id }}</title>
        <style>body{font-family:Arial,sans-serif;background:#f5f7fb;padding:24px;} .card{background:white;padding:20px;border-radius:16px;box-shadow:0 8px 28px rgba(0,0,0,0.04);} .row{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #edf2f7;} .label{font-weight:bold;} a{color:#0f766e;text-decoration:none;} </style></head><body>
        <div class="card">
            <h2>Assignment #{{ lead_id }}</h2>
            <div class="row"><div class="label">Captain</div><div>{{ detail['captain_name'] }}</div></div>
            <div class="row"><div class="label">Event Type</div><div>{{ detail['event_type'] }}</div></div>
            <div class="row"><div class="label">Customer</div><div>{{ detail['customer_name'] }}</div></div>
            <div class="row"><div class="label">Phone</div><div>{{ detail['phone'] }}</div></div>
            <div class="row"><div class="label">City</div><div>{{ detail['city'] }}</div></div>
            <div class="row"><div class="label">Event Date</div><div>{{ detail['event_date'] }}</div></div>
            <div class="row"><div class="label">Guest Count</div><div>{{ detail['guest_count'] }}</div></div>
            <div class="row"><div class="label">Budget</div><div>{{ detail['budget'] }}</div></div>
            <div class="row"><div class="label">Status</div><div>{{ detail['status'] }}</div></div>
            <div style="margin-top:16px;"><a href="/">Back to dashboard</a></div>
        </div>
        </body></html>
        ''',
        lead_id=lead_id,
        detail=detail,
    )


ensure_tables()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002, debug=True)
