from flask import Flask, request, jsonify, send_from_directory
from pathlib import Path
from PIL import Image, ImageStat
import sqlite3
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone


# =========================================================
# FLASK SETUP
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

app = Flask(__name__)

UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

DATABASE = BASE_DIR / "tests.db"

SECRET_KEY = os.environ.get(
    "RECORD_SECRET",
    "demo-secret-change-this"
)


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_database():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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


# =========================================================
# IMAGE HASH
# =========================================================

def sha256_file(file_path):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:

        while True:

            data = f.read(8192)

            if not data:
                break

            sha256.update(data)

    return sha256.hexdigest()


# =========================================================
# DEMO IMAGE CLASSIFICATION
# =========================================================

def classify_image(file_path):

    try:

        image = Image.open(file_path).convert("RGB")

        width, height = image.size

        # Take the central part of the image
        left = int(width * 0.25)
        top = int(height * 0.25)
        right = int(width * 0.75)
        bottom = int(height * 0.75)

        cropped = image.crop(
            (left, top, right, bottom)
        )

        stat = ImageStat.Stat(cropped)

        red = stat.mean[0]
        green = stat.mean[1]
        blue = stat.mean[2]

        # -------------------------------------------------
        # DEMONSTRATION CLASSIFIER
        # -------------------------------------------------

        if (
            red > green * 1.25
            and red > blue * 1.25
        ):

            return "POSITIVE", 0.85

        elif (
            blue > red * 1.20
            and blue > green * 1.10
        ):

            return "NEGATIVE", 0.85

        else:

            return "INCONCLUSIVE", 0.40

    except Exception:

        return "INCONCLUSIVE", 0.0


# =========================================================
# DIGITAL SIGNATURE
# =========================================================

def create_signature(record):

    canonical = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":")
    )

    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return signature


# =========================================================
# CREATE TEST RECORD
# =========================================================

@app.route("/api/tests", methods=["POST"])
def create_test():

    # -----------------------------------------------------
    # Check image
    # -----------------------------------------------------

    if "image" not in request.files:

        return jsonify({
            "error": "Image is required."
        }), 400

    image = request.files["image"]

    if image.filename == "":

        return jsonify({
            "error": "No image selected."
        }), 400


    # -----------------------------------------------------
    # Operator ID
    # -----------------------------------------------------

    operator_id = request.form.get(
        "operator_id",
        ""
    ).strip()

    if not operator_id:

        return jsonify({
            "error": "Operator ID is required."
        }), 400


    # -----------------------------------------------------
    # GPS
    # -----------------------------------------------------

    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")
    gps_accuracy = request.form.get("gps_accuracy")


    try:

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

    except ValueError:

        return jsonify({
            "error": "Invalid GPS information."
        }), 400


    # -----------------------------------------------------
    # Save image
    # -----------------------------------------------------

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    filename = (
        timestamp.replace(":", "-")
        .replace("+00:00", "")
        + ".jpg"
    )

    image_path = UPLOAD_FOLDER / filename

    try:

        # Open and save as JPEG
        img = Image.open(image)
        img = img.convert("RGB")

        img.save(
            image_path,
            "JPEG"
        )

    except Exception:

        return jsonify({
            "error": "Invalid image file."
        }), 400


    # -----------------------------------------------------
    # Image hash
    # -----------------------------------------------------

    image_hash = sha256_file(
        image_path
    )


    # -----------------------------------------------------
    # Classification
    # -----------------------------------------------------

    result, confidence = classify_image(
        image_path
    )


    # -----------------------------------------------------
    # Create record
    # -----------------------------------------------------

    record = {
        "timestamp": timestamp,
        "operator_id": operator_id,
        "latitude": latitude,
        "longitude": longitude,
        "gps_accuracy": gps_accuracy,
        "result": result,
        "image_hash": image_hash
    }


    # -----------------------------------------------------
    # Record hash
    # -----------------------------------------------------

    canonical_record = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":")
    )

    record_hash = hashlib.sha256(
        canonical_record.encode("utf-8")
    ).hexdigest()


    # -----------------------------------------------------
    # Digital signature
    # -----------------------------------------------------

    signature = create_signature({
        **record,
        "record_hash": record_hash
    })


    # -----------------------------------------------------
    # Save to database
    # -----------------------------------------------------

    conn = get_db()

    cursor = conn.execute(
        """
        INSERT INTO tests (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
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
        )
    )

    test_id = cursor.lastrowid

    conn.commit()
    conn.close()


    # -----------------------------------------------------
    # Return result
    # -----------------------------------------------------

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


# =========================================================
# VERIFY TEST RECORD
# =========================================================

@app.route(
    "/api/tests/<int:test_id>/verify",
    methods=["GET"]
)
def verify_test(test_id):

    conn = get_db()

    test = conn.execute(
        """
        SELECT *
        FROM tests
        WHERE id = ?
        """,
        (test_id,)
    ).fetchone()

    conn.close()


    if test is None:

        return jsonify({
            "error": "Test record not found."
        }), 404


    # -----------------------------------------------------
    # Check image hash
    # -----------------------------------------------------

    image_path = (
        UPLOAD_FOLDER /
        test["image_file"]
    )

    image_hash_valid = False

    if image_path.exists():

        current_image_hash = sha256_file(
            image_path
        )

        image_hash_valid = (
            current_image_hash
            == test["image_hash"]
        )


    # -----------------------------------------------------
    # Recreate record
    # -----------------------------------------------------

    record = {

        "timestamp": test["timestamp"],

        "operator_id": test["operator_id"],

        "latitude": test["latitude"],

        "longitude": test["longitude"],

        "gps_accuracy": test["gps_accuracy"],

        "result": test["result"],

        "image_hash": test["image_hash"]

    }


    canonical_record = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":")
    )

    current_record_hash = hashlib.sha256(
        canonical_record.encode("utf-8")
    ).hexdigest()


    record_hash_valid = (
        current_record_hash
        == test["record_hash"]
    )


    # -----------------------------------------------------
    # Verify signature
    # -----------------------------------------------------

    expected_signature = create_signature({

        **record,

        "record_hash":
            test["record_hash"]

    })


    signature_valid = hmac.compare_digest(
        expected_signature,
        test["signature"]
    )


    verified = (
        image_hash_valid
        and record_hash_valid
        and signature_valid
    )


    return jsonify({

        "verified": verified,

        "image_hash_valid":
            image_hash_valid,

        "record_hash_valid":
            record_hash_valid,

        "signature_valid":
            signature_valid

    })


# =========================================================
# GET TEST LOG
# =========================================================

@app.route(
    "/api/tests",
    methods=["GET"]
)
def get_tests():

    search = request.args.get(
        "search",
        ""
    ).strip()


    conn = get_db()


    if search:

        like = f"%{search}%"

        rows = conn.execute(
            """
            SELECT *
            FROM tests
            WHERE
                operator_id LIKE ?
                OR result LIKE ?
                OR CAST(id AS TEXT) LIKE ?
            ORDER BY id DESC
            """,
            (
                like,
                like,
                like
            )
        ).fetchall()

    else:

        rows = conn.execute(
            """
            SELECT *
            FROM tests
            ORDER BY id DESC
            """
        ).fetchall()


    conn.close()


    tests = []

    for row in rows:

        tests.append({

            "id": row["id"],

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


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return send_from_directory(
        str(BASE_DIR / "frontend"),
        "home.html"
    )


# =========================================================
# TESTING PAGE
# =========================================================

@app.route("/test")
def test_page():

    return send_from_directory(
        str(BASE_DIR / "frontend"),
        "index.html"
    )


# =========================================================
# FRONTEND FILES
# =========================================================

@app.route(
    "/frontend/<path:filename>"
)
def frontend_files(filename):

    return send_from_directory(
        str(BASE_DIR / "frontend"),
        filename
    )

# =========================================================
# START SERVER
# =========================================================

# Create database when the app starts
create_database()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )