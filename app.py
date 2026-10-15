"""Intelligent Student Accommodation Matching System - starter backend.

Run:  pip install flask pandas
      python app.py
"""
import sqlite3
from datetime import datetime

import pandas as pd
from flask import Flask, g, jsonify, render_template, request

DB_PATH = "accommodation.db"
REPORT_THRESHOLD = 3  # reports before a listing is hidden as outdated

app = Flask(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    address TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),          -- per month
    distance_km REAL NOT NULL CHECK (distance_km >= 0),
    facilities TEXT DEFAULT '',                       -- comma-separated, lowercase
    contact TEXT,
    status TEXT DEFAULT 'active',                     -- active | outdated
    created_at TEXT NOT NULL,
    last_verified TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id INTEGER NOT NULL REFERENCES listings(id),
    reason TEXT,
    created_at TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.executescript(SCHEMA)
        seed_default_listings()


def seed_default_listings():
    now = datetime.utcnow().isoformat(timespec="seconds")
    base_listings = [
        ("Skyview Residence", "Gwarinpa, Abuja", 220000, 2.1, ["wifi", "water", "security", "generator"], "0801-100-2001"),
        ("Palm Grove Studio", "Jabi, Abuja", 260000, 3.4, ["wifi", "water", "parking", "laundry"], "0802-200-3002"),
        ("Cedar Court Flats", "Karu, Abuja", 180000, 4.2, ["wifi", "water", "security", "study-room"], "0803-300-4003"),
        ("Nile Corner Lodge", "Asokoro, Abuja", 310000, 2.7, ["wifi", "water", "security", "gym"], "0804-400-5004"),
        ("Campus Nest Rooms", "Utako, Abuja", 170000, 1.9, ["wifi", "water", "security", "shared-kitchen"], "0805-500-6005"),
        ("Sunrise Terrace", "Maitama, Abuja", 340000, 5.1, ["wifi", "water", "security", "pool"], "0806-600-7006"),
        ("Oakland Shared Stay", "Lokogoma, Abuja", 210000, 3.2, ["wifi", "water", "security", "balcony"], "0807-700-8007"),
        ("Garden Path Hostel", "Wuye, Abuja", 160000, 2.8, ["wifi", "water", "study-room", "laundry"], "0808-800-9008"),
        ("Pearl Heights", "Garki, Abuja", 290000, 4.5, ["wifi", "water", "security", "backup-power"], "0809-900-1009"),
        ("Bluebell Apartments", "Bwari, Abuja", 230000, 6.0, ["wifi", "water", "security", "parking"], "0810-100-20010"),
        ("Greenfield Suites", "Kado, Abuja", 250000, 2.5, ["wifi", "water", "security", "gym"], "0811-110-22011"),
        ("Maple Court Lodge", "Nyanya, Abuja", 195000, 5.8, ["wifi", "water", "library", "security"], "0812-120-33012"),
        ("Horizon Residence", "Durumi, Abuja", 270000, 3.8, ["wifi", "water", "security", "laundry"], "0813-130-44013"),
        ("Crestview Home", "Gudu, Abuja", 205000, 2.0, ["wifi", "water", "security", "generator"], "0814-140-55014"),
        ("Serene Living Hub", "Jikwoyi, Abuja", 185000, 6.4, ["wifi", "water", "security", "parking"], "0815-150-66015"),
        ("Valley View Stay", "Mpape, Abuja", 175000, 7.3, ["wifi", "water", "study-room", "security"], "0816-160-77016"),
        ("Lakeside Student Flat", "Keffi, Abuja", 240000, 8.2, ["wifi", "water", "security", "backup-power"], "0817-170-88017"),
        ("Aster Lodge", "Life Camp, Abuja", 300000, 4.0, ["wifi", "water", "gym", "parking"], "0818-180-99018"),
        ("Summit Campus Homes", "Katampe, Abuja", 280000, 2.4, ["wifi", "water", "laundry", "security"], "0819-190-101019"),
        ("Metro Square Rooms", "Central Business District, Abuja", 260000, 1.6, ["wifi", "water", "security", "study-room"], "0820-200-111020"),
    ]

    with sqlite3.connect(DB_PATH) as con:
        existing_count = con.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        if existing_count >= 20:
            return

        rows = []
        for title, address, price, distance, facilities, contact in base_listings:
            rows.append((
                title,
                address,
                float(price),
                float(distance),
                ",".join(clean_facilities(facilities)),
                contact,
                "active",
                now,
                now,
            ))

        con.executemany(
            "INSERT INTO listings (title,address,price,distance_km,facilities,contact,status,created_at,last_verified) VALUES (?,?,?,?,?,?,?,?,?)",
            rows,
        )


def clean_facilities(value):
    if isinstance(value, list):
        items = value
    else:
        items = str(value or "").split(",")
    return sorted({f.strip().lower() for f in items if f.strip()})


def active_listings_df(where="status = 'active'", params=()):
    rows = get_db().execute(f"SELECT * FROM listings WHERE {where}", params).fetchall()
    df = pd.DataFrame([dict(r) for r in rows])
    if not df.empty:
        df["facility_list"] = df["facilities"].apply(clean_facilities)
    return df


# 1. Register listings -------------------------------------------------------
@app.post("/api/listings")
def register_listing():
    data = request.get_json(force=True)
    missing = [k for k in ("title", "address", "price", "distance_km") if k not in data]
    if missing:
        return jsonify(error=f"Missing fields: {missing}"), 400
    try:
        price, dist = float(data["price"]), float(data["distance_km"])
    except (TypeError, ValueError):
        return jsonify(error="price and distance_km must be numbers"), 400
    if price < 0 or dist < 0:
        return jsonify(error="price and distance_km must be >= 0"), 400

    now = datetime.utcnow().isoformat(timespec="seconds")
    db = get_db()
    cur = db.execute(
        "INSERT INTO listings (title,address,price,distance_km,facilities,contact,created_at,last_verified)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (data["title"], data["address"], price, dist,
         ",".join(clean_facilities(data.get("facilities"))), data.get("contact"), now, now),
    )
    db.commit()
    return jsonify(id=cur.lastrowid), 201


# 2 & 3. Search by price range + filter by distance ---------------------------
@app.get("/api/listings")
def search_listings():
    q = "status = 'active'"
    params = []
    if (v := request.args.get("min_price", type=float)) is not None:
        q += " AND price >= ?"; params.append(v)
    if (v := request.args.get("max_price", type=float)) is not None:
        q += " AND price <= ?"; params.append(v)
    if (v := request.args.get("max_distance", type=float)) is not None:
        q += " AND distance_km <= ?"; params.append(v)
    q += " ORDER BY price ASC"
    rows = get_db().execute(f"SELECT * FROM listings WHERE {q}", params).fetchall()
    return jsonify([dict(r) for r in rows])


# 4. Compare facilities -------------------------------------------------------
@app.get("/api/compare")
def compare():
    ids = [int(i) for i in request.args.get("ids", "").split(",") if i.strip().isdigit()]
    if len(ids) < 2:
        return jsonify(error="Provide at least two ids, e.g. ?ids=1,2,3"), 400
    marks = ",".join("?" * len(ids))
    df = active_listings_df(f"id IN ({marks})", ids)
    if df.empty:
        return jsonify(error="No matching listings"), 404
    all_fac = sorted({f for fl in df["facility_list"] for f in fl})
    table = {
        "listings": df[["id", "title", "price", "distance_km"]].to_dict("records"),
        "facility_matrix": {
            f: {int(r.id): (f in r.facility_list) for r in df.itertuples()} for f in all_fac
        },
        "shared_by_all": sorted(set.intersection(*[set(x) for x in df["facility_list"]])),
    }
    return jsonify(table)


# 5. Rank by preferences (weighted multi-criteria scoring) --------------------
def minmax_inverse(s):
    """Lower raw value -> higher score in [0,1]."""
    rng = s.max() - s.min()
    return pd.Series(1.0, index=s.index) if rng == 0 else 1 - (s - s.min()) / rng


@app.post("/api/recommend")
def recommend():
    """Body example:
    {"budget": 150000, "max_distance": 3,
     "required": ["wifi"], "preferred": ["water", "security"],
     "weights": {"price": 0.4, "distance": 0.3, "facilities": 0.3}}
    """
    p = request.get_json(force=True)
    df = active_listings_df()
    if df.empty:
        return jsonify([])

    if p.get("budget") is not None:
        df = df[df["price"] <= float(p["budget"])]
    if p.get("max_distance") is not None:
        df = df[df["distance_km"] <= float(p["max_distance"])]
    required = set(clean_facilities(p.get("required")))
    if required:  # hard constraint
        df = df[df["facility_list"].apply(lambda fl: required <= set(fl))]
    if df.empty:
        return jsonify([])

    preferred = set(clean_facilities(p.get("preferred")))
    w = {"price": 0.4, "distance": 0.3, "facilities": 0.3}
    w.update(p.get("weights", {}))
    total = sum(w.values()) or 1
    w = {k: v / total for k, v in w.items()}

    df = df.copy()
    df["price_score"] = minmax_inverse(df["price"])
    df["distance_score"] = minmax_inverse(df["distance_km"])
    df["facility_score"] = df["facility_list"].apply(
        lambda fl: len(preferred & set(fl)) / len(preferred) if preferred else 1.0
    )
    df["score"] = (w["price"] * df["price_score"]
                   + w["distance"] * df["distance_score"]
                   + w["facilities"] * df["facility_score"])
    df = df.sort_values("score", ascending=False)
    cols = ["id", "title", "price", "distance_km", "facilities", "score"]
    return jsonify(df[cols].round({"score": 3}).to_dict("records"))


# 6. Report outdated listings -------------------------------------------------
@app.post("/api/listings/<int:listing_id>/report")
def report_listing(listing_id):
    db = get_db()
    if db.execute("SELECT 1 FROM listings WHERE id=?", (listing_id,)).fetchone() is None:
        return jsonify(error="Listing not found"), 404
    reason = (request.get_json(silent=True) or {}).get("reason", "")
    db.execute("INSERT INTO reports (listing_id, reason, created_at) VALUES (?,?,?)",
               (listing_id, reason, datetime.utcnow().isoformat(timespec="seconds")))
    count = db.execute("SELECT COUNT(*) FROM reports WHERE listing_id=?", (listing_id,)).fetchone()[0]
    if count >= REPORT_THRESHOLD:
        db.execute("UPDATE listings SET status='outdated' WHERE id=?", (listing_id,))
    db.commit()
    return jsonify(reports=count, hidden=count >= REPORT_THRESHOLD)


# Simple web page ------------------------------------------------------------
@app.get("/")
def home():
    return render_template("index.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
