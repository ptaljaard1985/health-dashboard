# Fix Garmin Sync — Do This on 26 March 2026

## What happened?

Garmin blocked our login because we were logging in too often (every 3 hours).
The workflow is disabled until the block clears.

## What changed?

The sync script now saves a login token after the first login.
Future runs reuse that token instead of logging in fresh every time.

## Step-by-step instructions

### Step 1: Open terminal and go to the project folder

```bash
cd ~/health-dashboard
```

### Step 2: Pull the latest code

```bash
git pull
```

### Step 3: Run the sync locally to generate a token

```bash
python3 garmin_notion_sync.py
```

This will log in to Garmin and save a token in `.garmin_tokens/`.

If you get a rate limit error, wait another day and try again.

### Step 4: Generate the token string for GitHub

```bash
python3 -c "
import json, base64, os
tokens = {}
for f in ['oauth1_token.json', 'oauth2_token.json']:
    with open(os.path.join('.garmin_tokens', f)) as fh:
        tokens[f] = json.load(fh)
print(base64.b64encode(json.dumps(tokens).encode()).decode())
"
```

This prints a long string of letters and numbers. Copy it.

### Step 5: Save that string as a GitHub Secret

```bash
gh secret set GARMIN_TOKENS
```

It will ask you to paste. Paste the string from Step 4, then press Enter and Ctrl+D.

### Step 6: Re-enable the workflow

```bash
gh workflow enable "Sync Garmin & Update Dashboard"
```

### Step 7: Test it

```bash
gh workflow run "Sync Garmin & Update Dashboard"
```

Then check if it passed:

```bash
gh run list --workflow=sync.yml --limit=1
```

You should see `completed success`. Done!
