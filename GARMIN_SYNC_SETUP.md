# Garmin to Notion Sync - Setup Guide

This script automatically syncs your Garmin Connect activities and weight data to your Notion Exercise Log database.

---

## Quick Start (5 minutes)

### Step 1: Install Python Dependencies

Open Terminal and run:

```bash
pip install garminconnect notion-client python-dotenv
```

### Step 2: Create Your Notion Integration

1. Go to [notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Name it **"Garmin Sync"**
4. Select your workspace
5. Click **Submit**
6. Copy the **"Internal Integration Token"** (starts with `secret_`)

### Step 3: Connect Integration to Your Database

**Important!** The integration needs permission to access your database:

1. Open your [Exercise Log database](https://www.notion.so/9279f78c5284458fbe891096853bd840) in Notion
2. Click the **"..."** menu (top right)
3. Click **"Connections"** → **"Connect to"**
4. Find and select **"Garmin Sync"**

### Step 4: Create Your .env File

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your credentials:
   ```bash
   nano .env
   ```

   Fill in:
   - `GARMIN_EMAIL` - Your Garmin Connect email
   - `GARMIN_PASSWORD` - Your Garmin Connect password
   - `NOTION_API_KEY` - The token from Step 2

### Step 5: Run the Sync

```bash
python garmin_notion_sync.py
```

You should see output like:
```
2026-02-01 10:00:00 - INFO - Starting Garmin to Notion sync
2026-02-01 10:00:01 - INFO - Successfully connected to Garmin Connect
2026-02-01 10:00:02 - INFO - Found 12 activities in last 7 days
2026-02-01 10:00:03 - INFO - Created activity: Morning Run (2026-01-28)
...
2026-02-01 10:00:10 - INFO - Sync complete!
```

---

## Daily Automatic Sync (macOS)

To run the sync automatically every day at 6 AM:

### Create a Launch Agent

1. Create the plist file:

```bash
mkdir -p ~/Library/LaunchAgents
nano ~/Library/LaunchAgents/com.garmin.notion.sync.plist
```

2. Paste this content (update the paths to match your setup):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.garmin.notion.sync</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/YOUR_USERNAME/path/to/garmin_notion_sync.py</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/path/to/</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>/tmp/garmin_sync.log</string>

    <key>StandardErrorPath</key>
    <string>/tmp/garmin_sync.error.log</string>
</dict>
</plist>
```

3. Load the agent:

```bash
launchctl load ~/Library/LaunchAgents/com.garmin.notion.sync.plist
```

### Useful Commands

```bash
# Check if it's loaded
launchctl list | grep garmin

# Run it manually (test)
launchctl start com.garmin.notion.sync

# Stop the scheduler
launchctl unload ~/Library/LaunchAgents/com.garmin.notion.sync.plist

# View logs
tail -f /tmp/garmin_sync.log
```

---

## Activity Type Mapping

The script maps Garmin activity types to your Notion database:

| Garmin Activity | → Notion Type |
|-----------------|---------------|
| running | Run |
| trail_running | Trail Run |
| walking | Walk |
| hiking | Hike |
| indoor_cycling | Indoor Cycle |
| strength_training | Kettlebells |
| tennis | Tennis |
| padel | Padel |
| golf | Golf |

To add new mappings, edit `GARMIN_TO_NOTION_TYPE` in the script.

---

## Troubleshooting

### "Missing required environment variables"
- Make sure `.env` file exists (not just `.env.example`)
- Check all required variables are filled in

### "Failed to connect to Garmin"
- Check your Garmin email/password
- If you have 2FA enabled, you may need an app-specific password

### "notion_client.errors.APIResponseError: Could not find database"
- Make sure you connected the integration to your database (Step 3)
- Check the database ID is correct in `.env`

### Activities not appearing
- Check `garmin_sync.log` for errors
- Unknown activity types get logged - you may need to add mappings

---

## Data Synced

### Activities
- Exercise name
- Date
- Type (mapped to your categories)
- Duration (minutes)
- Distance (km)
- Calories
- Average Heart Rate
- Max Heart Rate
- Notes

### Weight
- Date
- Weight (kg)
- Type = "Weigh-in"

---

## Security Notes

- Never share your `.env` file
- The Notion integration only has access to databases you explicitly connect it to
- Consider using a Garmin app-specific password if available
- Credentials are stored locally only
