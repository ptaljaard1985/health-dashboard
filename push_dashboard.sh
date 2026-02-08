#!/bin/bash
# Push dashboard updates to GitHub Pages
# Runs after generate_dashboard.py

cd "/Users/pierretaljaard/Dropbox/1_TALJAARD/Pierre Snr/1 Projects/202602 Health App/garmin sync"

# Copy latest dashboard to index.html
cp dashboard.html index.html

# Git add, commit and push
git add index.html dashboard.html
git commit -m "Dashboard update $(date '+%Y-%m-%d %H:%M')"
git push origin main

echo "Dashboard pushed to GitHub Pages at $(date)"
