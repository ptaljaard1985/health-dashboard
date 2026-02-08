#!/bin/bash
# Daily Health Sync - Runs Garmin sync then generates dashboard
# Scheduled to run at 10am daily

cd "/Users/pierretaljaard/Dropbox/1_TALJAARD/Pierre Snr/1 Projects/202602 Health App/garmin sync"

echo "$(date): Starting daily health sync..."

# Step 1: Sync Garmin data to Notion
echo "Syncing Garmin data..."
python3 garmin_notion_sync.py

# Step 2: Generate updated dashboard
echo "Generating dashboard..."
python3 generate_dashboard.py

echo "$(date): Daily health sync complete!"
