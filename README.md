# Digital Companion for Field Drug Testing

A web-based prototype for digitally documenting and verifying field test records.

## ⚠️ Important Disclaimer

This project is a demonstration prototype.

The colour classification feature is NOT a validated drug-identification method and must not be used for real-world forensic, legal, enforcement, medical, or safety decisions.

## Overview

This project demonstrates how a digital system can record:

- Operator ID
- Test image
- Date and time
- GPS location
- Test result
- Image SHA-256 hash
- Record hash
- Digital HMAC signature

The system also provides record verification and a searchable test log.

## Features

- 📷 Capture test images using a camera
- 🖼️ Upload an image
- 📍 Capture GPS location
- 🧪 Demo colour classification
- 📝 Create digital test records
- 🔐 Generate SHA-256 image hashes
- 🔏 Generate digital record signatures
- ✅ Verify test records
- 🔎 Search test records

## Technology Stack

- Python
- Flask
- Pillow
- SQLite
- HTML
- CSS
- JavaScript

## Project Structure

```text
digitalcompanion/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
│
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js