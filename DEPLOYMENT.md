# Deployment guide

## Choose the right deployment model

This application performs recognition on the machine running Python and opens
camera index `0` with OpenCV. Use one of these models:

1. **Local workstation:** the recommended first deployment. The workstation
   has the webcam, database, and dashboard.
2. **Private LAN server:** a server with a USB/IP camera attached to that
   server. Staff access the dashboard from other machines on the LAN.
3. **Cloud/serverless hosting:** not supported by the current camera design.
   A redesign would be required to capture video in the browser or from a
   camera gateway and send frames to the recognition service.

Do not expose the Flask development server directly to the public internet.

## Production-style Linux setup

These steps assume Debian/Ubuntu and a machine with a working webcam.

### 1. Install system packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev build-essential cmake
```

If OpenCV cannot access the camera, also check the operating system's camera
permissions and that another process is not using the device.

### 2. Copy the application and create an environment

```bash
cd /path/to/face-recognition
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install gunicorn
```

Run the application as a dedicated, unprivileged user. Keep the following
paths writable by that user because the app creates the database, secret key,
and enrollment folders:

- `database/`
- `data/faces/`
- the project root for `.flask_secret_key` when no environment key is set

### 3. Create an admin and set the session secret

Generate a secret outside the repository and export it in the service
environment:

```bash
export FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python seed_admin.py --username admin --password 'replace-with-a-strong-password'
```

For a persistent service, configure `FLASK_SECRET_KEY` and the admin password
through the service manager or secret store, not in source control. The
literal password shown above is only a placeholder; replace it before running
the command.
Do not copy `.flask_secret_key` into Git.

### 4. Enroll people on the camera host

Enrollment needs a local graphical session and webcam:

```bash
python enroll.py --name "Full Name"
```

For a profile created in the dashboard, use its generated `--user-id`
command. After enrollment, select **Refresh Known Faces**.

### 5. Run Gunicorn with one worker

The camera stream and recognition state are held in a process-local singleton.
Run one worker so all dashboard requests share the same camera and recognition
state. Threads allow the MJPEG stream and normal dashboard requests to coexist:

```bash
gunicorn \
  --workers 1 \
  --threads 8 \
  --timeout 120 \
  --bind 127.0.0.1:8000 \
  run:app
```

Binding to `127.0.0.1` is safest when a reverse proxy is on the same machine.
For a trusted LAN-only deployment without a reverse proxy, bind to the
server's LAN address instead and restrict access with a firewall:

```bash
gunicorn --workers 1 --threads 8 --timeout 120 \
  --bind 192.168.1.20:8000 run:app
```

Do not use multiple workers with the current camera implementation: each
worker would create its own camera and recognition state.

## Reverse proxy and HTTPS

For a shared deployment, put Nginx, Caddy, or another TLS-terminating reverse
proxy in front of Gunicorn. Proxy the MJPEG endpoint without buffering and
allow its long-lived response to remain open. The important requirements are:

- terminate HTTPS at the proxy;
- forward requests to `127.0.0.1:8000`;
- disable proxy buffering for `/api/stream`;
- allow a read timeout longer than a normal request;
- restrict the dashboard to trusted users or a private network.

The app does not currently configure CSRF tokens, rate limiting, account
lockout, or a full production user-management workflow. Treat the reverse
proxy, network boundary, and admin credentials as part of the security
boundary before exposing the service to untrusted networks.

## Backups and upgrades

Stop or quiesce the service before copying live data. Back up:

```text
database/attendance.db
data/faces/
```

Keep the secret key in a separate protected secret backup. Do not upload
attendance exports, face photos, the SQLite database, or secret keys to a
public GitHub repository.

After updating code:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m tests.test_concurrent_writes
```

`init_db()` creates missing tables and applies the small schema additions used
by the current application. Take a database backup before upgrades.

## GitHub publishing checklist

Before creating a public repository:

1. Review `git status` and confirm no `.flask_secret_key`, database, face
   images, CSV exports, passwords, or other personal data are staged.
2. Keep the repository's `.gitignore` enabled.
3. Remove any accidentally tracked sensitive files from Git's index without
   deleting local copies:

   ```bash
   git rm --cached .flask_secret_key database/attendance.db
   ```

4. Replace example credentials and personal names in documentation.
5. Add a license and decide whether the project should be public.
6. Rotate any secret that was ever committed, even if it was later deleted.

A clean first push from the project root is:

```bash
git init
git add README.md docs/ .gitignore app database engine templates *.py requirements.txt setup.sh
git status
git commit -m "Document Smart Attendance setup and deployment"
git branch -M main
git remote add origin https://github.com/<account>/<repository>.git
git push -u origin main
```

Inspect the staged file list before committing. Do not use `git add .` until
you have verified that local biometric and attendance data are ignored.
