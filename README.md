# Smart Attendance

Smart Attendance is a Flask-based face-recognition attendance system for a
computer with a webcam. It provides an admin dashboard, guided face
enrollment, live recognition with blink-based liveness checking, a SQLite
attendance database, a monthly register, and CSV export.

> **Important:** The webcam is opened by the Python process with
> `cv2.VideoCapture(0)`. The camera must therefore be physically connected to
> the machine running the application. Hosting the app on a cloud server does
> not automatically give it access to a camera in a user's browser.

## Features

- Admin login with hashed passwords and signed Flask sessions
- Roster management for students, employees, or other attendees
- Multi-photo face enrollment stored as encodings in SQLite
- Live MJPEG recognition feed from the server webcam
- Identity confirmation across multiple frames
- Optional blink-based liveness gate to reject static photographs
- One attendance record per person per day, enforced by a database constraint
- Daily attendance table and CSV export
- Monthly attendance register with manual corrections
- Configurable recognition tolerance, frame rate, detector, and liveness settings

The liveness check is deliberately lightweight. It helps block a static photo,
but it is not a complete defence against replayed video or sophisticated
spoofing.

## Requirements

- Python 3.10 or newer
- A webcam connected to the machine running the app
- Linux, macOS, or Windows
- Build tools required by `dlib`/`face_recognition` when a compatible wheel is
  not available

On Debian/Ubuntu, install the native prerequisites first:

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential cmake
```

## Quick start

Run all commands from the project root.

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

On Windows PowerShell, activate with:

```powershell
.venv\Scripts\Activate.ps1
```

### 2. Install dependencies and create the first admin

The setup script installs Python dependencies and securely prompts for the
first admin credentials:

```bash
./setup.sh
```

The equivalent manual commands are:

```bash
python -m pip install -r requirements.txt
python seed_admin.py --username admin --password 'change-this-password'
```

Use a strong password and do not put it in shell history on a shared machine.

### 3. Start the dashboard

```bash
python run.py
```

Open <http://127.0.0.1:5000> and log in.

`run.py` uses Flask's development server. It is suitable for local testing,
but use the deployment instructions in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
for a shared or production installation.

## Enroll people

There are two supported enrollment flows.

### Dashboard roster flow

1. Open **Roster** in the dashboard.
2. Create a profile and note the generated command.
3. Run the command from the project root, for example:

   ```bash
   python enroll.py --user-id 5 --name "Full Name"
   ```

4. In the enrollment window, press **Space** to capture images and **Q** to
   finish. Capture approximately 15–20 images with different angles and
   lighting.
5. Return to the dashboard and select **Refresh Known Faces**.

### Remove someone who has left

1. Open **Roster** in the dashboard.
2. Find the person under **Registered people**.
3. Click **Remove** and confirm the prompt.

This deletes the person’s profile and face encodings from SQLite, removes their
enrollment photos from `data/faces/`, removes their linked attendance history,
and refreshes the live recognizer immediately. The action is permanent, so
export any attendance records that must be retained before removing the
profile.

Optional profile fields can be supplied during enrollment:

```bash
python enroll.py \
  --user-id 5 \
  --name "Full Name" \
  --roll-number "EMP-005" \
  --email "person@example.com" \
  --section "Engineering"
```

### Direct enrollment

To create a new profile without using the dashboard:

```bash
python enroll.py --name "Full Name"
```

Enrollment requires a local display and webcam because OpenCV opens a camera
window.

## Use the application

- `/` — admin dashboard and live recognition feed
- `/students` — create profiles and view enrollment status
- `/attendance` — view attendance for a selected date
- `/attendance/export.csv` — download one day's attendance as CSV, including
  each person's roll/employee number, email, and section/team
- `/register` — view and manually update the monthly register, including each
  person's roster details
- `/auth/login` and `/auth/logout` — authentication

Attendance is marked only after the configured identity confirmation and
liveness checks succeed. A person can be marked at most once per calendar day.

## Configuration

Recognition and liveness settings are in [config.py](config.py):

- `TOLERANCE` — lower values are stricter
- `CONFIRM_FRAMES` — consecutive matches required
- `DETECTION_MODEL` — `hog` is the practical CPU default; `cnn` generally
  requires a suitable GPU
- `PROCESS_EVERY_N_FRAMES` and `FRAME_RESIZE_SCALE` — performance controls
- `ENABLE_LIVENESS` and the blink thresholds — anti-spoofing controls

The database is stored at `database/attendance.db`. Face photos are stored
under `data/faces/`, while their numeric encodings are stored in the database.
Back up both locations if the original enrollment photos are needed.

The app creates `.flask_secret_key` automatically on first startup. In a
server deployment, prefer setting a long random `FLASK_SECRET_KEY` environment
variable and keep it private.

## Project layout

```text
app/                 Flask app factory, routes, and camera stream
database/            SQLAlchemy models, SQLite setup, and attendance helpers
engine/              Face matching and liveness detection
templates/           Dashboard, roster, login, and attendance pages
data/faces/          Local enrollment photos (not committed)
tests/               Database concurrency test
config.py            Recognition and liveness tuning
enroll.py            Webcam enrollment utility
run.py               Flask entry point
run_recognition.py   Standalone desktop recognition loop
seed_admin.py        Admin account creation utility
setup.sh             First-time setup helper
```

## Testing

The concurrency test uses a temporary database and does not need a webcam:

```bash
python -m tests.test_concurrent_writes
```

## Privacy and security

Face images and face encodings are biometric data. Obtain consent, restrict
access to the dashboard, protect backups, and define an appropriate retention
period. Do not commit `database/attendance.db`, `.flask_secret_key`, face
photos, passwords, or exported attendance files to a public repository.

This project is intended for controlled deployments. Before exposing it beyond
a trusted LAN, add HTTPS, firewall rules, backups, monitoring, and a stronger
production authentication and privacy review.

## License

No license has been declared yet. Add a license before publishing the project
for reuse.
