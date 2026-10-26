#!/bin/bash
# One-time setup. Run from the project root: ./setup.sh
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo ""
echo "Setting up the first admin account for the dashboard."
read -p "Admin username: " ADMIN_USER
read -s -p "Admin password: " ADMIN_PASS
echo ""

python3 seed_admin.py --username "$ADMIN_USER" --password "$ADMIN_PASS"

echo ""
echo "Setup complete."
echo "Next steps:"
echo "  1. Enroll yourself and others:  python3 enroll.py --name \"Full Name\""
echo "  2. Start the server:            python3 run.py"
echo "  3. Open:                        http://127.0.0.1:5000"