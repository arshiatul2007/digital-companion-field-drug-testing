from flask import Flask, request, jsonify, send_from_directory
from PIL import Image, ImageStat
from pathlib import Path
from datetime import datetime, timezone
import sqlite3
import hashlib
import hmac
import json
import uuid
import os


# --------------------------------------------------
# FLASK SETUP
# --------------------------------------------------

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"
DATABASE = BASE_DIR / "tests.db"

UPLOAD_FOLDER.mkdir(exist_ok=True)

SECRET_KEY = os.environ.get(
    "RECORD_SECRET",
    "demo-secret-change-this"
)


# --------------------------------------------------
# DATABASE
# --------------------------------------------------

def create_database():

    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            operator_id TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            gps_accuracy REAL,
            result TEXT NOT NULL,
            image_hash TEXT NOT NULL,
            record_hash TEXT NOT NULL,
            signature TEXT NOT NULL,
            image_file TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


# --------------------------------------------------
# IMAGE HASH
# --------------------------------------------------

def sha256_file(path):

    h = hashlib.sha256()

    with open(path, "rb") as f:

        while True:

            chunk = f.read(8192)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


# --------------------------------------------------
# DEMO COLOUR CLASSIFICATION
# --------------------------------------------------

def classify_image(path):

    image = Image.open(path).convert("RGB")

    width, height = image.size

    left = int(width * 0.25)
    top = int(height * 0.25)
    right = int(width * 0.75)
    bottom = int(height * 0.75)

    center = image.crop(
        (left, top, right, bottom)
    )

    mean_r, mean_g, mean_b = ImageStat.Stat(center).mean

    if mean_r > mean_g * 1.25 and mean_r > mean_b * 1.25:

        return "POSITIVE", 0.85

    elif mean_b > mean_r * 1.20 and mean_b > mean_g * 1.10:

        return "NEGATIVE", 0.85

    else:

        return "INCONCLUSIVE", 0.40


# --------------------------------------------------
# DIGITAL SIGNATURE
# --------------------------------------------------

def create_signature(record):

    data = json.dumps(
        record,
        sort_keys=True
    ).encode("utf-8")

    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        data,
        hashlib.sha256
    ).hexdigest()


# --------------------------------------------------
# CREATE TEST RECORD
# --------------------------------------------------

@app.route("/api/tests", methods=["POST"])
def create_test():

    image = request.files.get("image")

    operator_id = request.form.get(
        "operator_id",
        ""
    ).strip()

    if not image:

        return jsonify({
            "error": "Please provide an image"
        }), 400

    if not operator_id:

        return jsonify({
            "error": "Operator ID is required"
        }), 400

    # Create unique test ID

    test_id = str(uuid.uuid4())

    # Save image

    filename = test_id + ".jpg"

    image_path = UPLOAD_FOLDER / filename

    image.save(image_path)

    # Create image hash

    image_hash = sha256_file(image_path)

    # Demo classification

    result, confidence = classify_image(
        image_path
    )

    # Get GPS information

    latitude = request.form.get("latitude")

    longitude = request.form.get("longitude")

    gps_accuracy = request.form.get(
        "gps_accuracy"
    )

    latitude = (
        float(latitude)
        if latitude
        else None
    )

    longitude = (
        float(longitude)
        if longitude
        else None
    )

    gps_accuracy = (
        float(gps_accuracy)
        if gps_accuracy
        else None
    )

    # Current UTC time

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    # Record information

    record = {

        "id": test_id,

        "timestamp": timestamp,

        "operator_id": operator_id,

        "latitude": latitude,

        "longitude": longitude,

        "gps_accuracy": gps_accuracy,

        "result": result,

        "image_hash": image_hash
    }

    # Record hash

    record_hash = hashlib.sha256(

        json.dumps(
            record,
            sort_keys=True
        ).encode("utf-8")

    ).hexdigest()

    # Digital signature

    signature = create_signature(
        record
    )

    # Save to database

    conn = sqlite3.connect(DATABASE)

    conn.execute("""
        INSERT INTO tests
        (
            id,
            timestamp,
            operator_id,
            latitude,
            longitude,
            gps_accuracy,
            result,
            image_hash,
            record_hash,
            signature,
            image_file
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (

        test_id,

        timestamp,

        operator_id,

        latitude,

        longitude,

        gps_accuracy,

        result,

        image_hash,

        record_hash,

        signature,

        filename
    ))

    conn.commit()

    conn.close()

    # Send result to browser

    return jsonify({

        "id": test_id,

        "timestamp": timestamp,

        "operator_id": operator_id,

        "latitude": latitude,

        "longitude": longitude,

        "gps_accuracy": gps_accuracy,

        "result": result,

        "confidence": confidence,

        "image_hash": image_hash,

        "record_hash": record_hash,

        "signature": signature
    })


# --------------------------------------------------
# VERIFY TEST RECORD
# --------------------------------------------------

@app.route(
    "/api/tests/<test_id>/verify",
    methods=["GET"]
)
def verify_test(test_id):

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    row = conn.execute(

        "SELECT * FROM tests WHERE id = ?",

        (test_id,)

    ).fetchone()

    conn.close()

    if not row:

        return jsonify({
            "error": "Test record not found"
        }), 404

    image_path = (
        UPLOAD_FOLDER /
        row["image_file"]
    )

    if not image_path.exists():

        return jsonify({
            "error": "Test image is missing"
        }), 404

    # Check image hash

    current_image_hash = sha256_file(
        image_path
    )

    image_hash_valid = (
        current_image_hash ==
        row["image_hash"]
    )

    # Recreate original record

    record = {

        "id": row["id"],

        "timestamp": row["timestamp"],

        "operator_id": row["operator_id"],

        "latitude": row["latitude"],

        "longitude": row["longitude"],

        "gps_accuracy": row["gps_accuracy"],

        "result": row["result"],

        "image_hash": row["image_hash"]
    }

    # Check record hash

    current_record_hash = hashlib.sha256(

        json.dumps(
            record,
            sort_keys=True
        ).encode("utf-8")

    ).hexdigest()

    record_hash_valid = (
        current_record_hash ==
        row["record_hash"]
    )

    # Check digital signature

    current_signature = create_signature(
        record
    )

    signature_valid = hmac.compare_digest(

        current_signature,

        row["signature"]
    )

    verified = (

        image_hash_valid
        and record_hash_valid
        and signature_valid
    )

    return jsonify({

        "id": test_id,

        "image_hash_valid":
            image_hash_valid,

        "record_hash_valid":
            record_hash_valid,

        "signature_valid":
            signature_valid,

        "verified":
            verified
    })


# --------------------------------------------------
# GET TEST LOG
# --------------------------------------------------

@app.route(
    "/api/tests",
    methods=["GET"]
)
def get_tests():

    search = request.args.get(
        "search",
        ""
    ).strip()

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    if search:

        rows = conn.execute("""

            SELECT *
            FROM tests

            WHERE operator_id LIKE ?
               OR result LIKE ?
               OR id LIKE ?

            ORDER BY timestamp DESC

        """, (

            f"%{search}%",

            f"%{search}%",

            f"%{search}%"

        )).fetchall()

    else:

        rows = conn.execute("""

            SELECT *
            FROM tests

            ORDER BY timestamp DESC

        """).fetchall()

    conn.close()

    tests = []

    for row in rows:

        tests.append({

            "id":
                row["id"],

            "timestamp":
                row["timestamp"],

            "operator_id":
                row["operator_id"],

            "latitude":
                row["latitude"],

            "longitude":
                row["longitude"],

            "gps_accuracy":
                row["gps_accuracy"],

            "result":
                row["result"],

            "image_hash":
                row["image_hash"],

            "record_hash":
                row["record_hash"],

            "signature":
                row["signature"],

            "image_file":
                row["image_file"]
        })

    return jsonify(tests)


# --------------------------------------------------
# FRONTEND
# --------------------------------------------------

@app.route("/")
def home():

    return send_from_directory(

        BASE_DIR / "frontend",

        "index.html"
    )


@app.route(
    "/frontend/<path:filename>"
)
def frontend_files(filename):

    return send_from_directory(

        BASE_DIR / "frontend",

        filename
    )


# --------------------------------------------------
# START SERVER
# --------------------------------------------------

if __name__ == "__main__":

    create_database()

    app.run(

        host="127.0.0.1",

        port=5000,

        debug=True
    )