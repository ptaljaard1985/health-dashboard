#!/usr/bin/env python3
"""
Health Coach Telegram Bot
=========================
Daily 6am summary with progress and actionable guidance for TODAY.

Shows last 7 days (yesterday + 6 days before) and recommends
what to do today based on what's "falling off" the rolling window.

See TELEGRAM_BOT_SPEC.md for full specification.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from db import init_db, get_connection

load_dotenv()

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '8334374048:AAHE-v6kjGGeHr41k8WWPYQH2LEFaZMdRSo')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '8569149206')

# Weekly targets (rolling 7 days)
WEEKLY_CARDIO_GOAL = 4
WEEKLY_STRENGTH_GOAL = 3

# Monthly targets (calendar month)
MONTHLY_CARDIO_GOAL = 16
MONTHLY_STRENGTH_GOAL = 10

# Alert thresholds
REST_DAY_WARNING = 2
REST_DAY_URGENT = 3
WEIGHIN_REMINDER_DAYS = 3

CARDIO_TYPES = {'Run', 'Walk', 'Indoor Cycle', 'Hike', 'Trail Run', 'Rucking', 'Padel', 'Tennis', 'Golf'}


def send_telegram(message):
    """Send a Telegram message."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Telegram sent successfully")
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def fetch_exercises():
    """Fetch exercises from the database."""
    conn = get_connection()
    rows = conn.execute("SELECT date, type FROM activities ORDER BY date DESC").fetchall()
    conn.close()

    return [{'date': row['date'], 'types': [row['type']]} for row in rows]


def fetch_weight_entries():
    """Fetch weight entries from the database."""
    conn = get_connection()
    rows = conn.execute("SELECT date, weight_kg FROM weigh_ins ORDER BY date DESC").fetchall()
    conn.close()

    return [{'date': row['date'], 'weight': row['weight_kg']} for row in rows]


def get_days_in_month(year, month):
    """Get number of days in a month."""
    if month == 12:
        return 31
    next_month = datetime(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)
    return last_day.day


def has_activity_in_last_n_days(exercises, activity_check_fn, n_days, today):
    """Check if there's been an activity matching the check function in last N days."""
    cutoff = today - timedelta(days=n_days)
    recent = [e for e in exercises if datetime.strptime(e['date'][:10], '%Y-%m-%d').date() > cutoff]
    return any(activity_check_fn(e) for e in recent)


def build_daily_message():
    """Build the daily summary message."""
    print(f"Building daily health summary at {datetime.now()}")

    init_db()
    exercises = fetch_exercises()
    weights = fetch_weight_entries()
    today = datetime.now().date()

    # ===== WEEKLY STATS (Last 7 Days = yesterday + 6 days before, excluding today) =====
    yesterday = today - timedelta(days=1)
    seven_days_ago = today - timedelta(days=7)
    week_exercises = [
        e for e in exercises
        if seven_days_ago <= datetime.strptime(e['date'][:10], '%Y-%m-%d').date() <= yesterday
    ]

    weekly_cardio = len([e for e in week_exercises if any(t in CARDIO_TYPES for t in e['types'])])
    weekly_strength = len([e for e in week_exercises if 'Kettlebells' in e['types']])

    # ===== FALLING OFF (8 days ago - what leaves the window tomorrow) =====
    eight_days_ago = today - timedelta(days=8)
    falling_off_exercises = [
        e for e in exercises
        if datetime.strptime(e['date'][:10], '%Y-%m-%d').date() == eight_days_ago
    ]
    falling_off_cardio = any(any(t in CARDIO_TYPES for t in e['types']) for e in falling_off_exercises)
    falling_off_strength = any('Kettlebells' in e['types'] for e in falling_off_exercises)

    # ===== MONTHLY STATS (Calendar Month) =====
    month_start = today.replace(day=1)
    month_name = today.strftime('%B')
    month_short = today.strftime('%b')
    day_of_month = today.day
    days_in_month = get_days_in_month(today.year, today.month)

    month_exercises = [
        e for e in exercises
        if datetime.strptime(e['date'][:10], '%Y-%m-%d').date() >= month_start
    ]

    monthly_cardio = len([e for e in month_exercises if any(t in CARDIO_TYPES for t in e['types'])])
    monthly_strength = len([e for e in month_exercises if 'Kettlebells' in e['types']])

    # Expected pace (pro-rata)
    progress_ratio = day_of_month / days_in_month
    cardio_expected = round(MONTHLY_CARDIO_GOAL * progress_ratio)
    strength_expected = round(MONTHLY_STRENGTH_GOAL * progress_ratio)

    # ===== REST DAYS =====
    workout_dates = sorted(set(e['date'][:10] for e in exercises), reverse=True)
    rest_days = 0
    if workout_dates:
        last_workout = datetime.strptime(workout_dates[0], '%Y-%m-%d').date()
        rest_days = (today - last_workout).days

    # ===== WEIGHT =====
    days_since_weighin = None
    latest_weight = None
    weight_7d_change = None
    weight_30d_change = None

    if weights:
        latest_weight = weights[0]['weight']
        last_weighin = datetime.strptime(weights[0]['date'], '%Y-%m-%d').date()
        days_since_weighin = (today - last_weighin).days

        # Find weight from ~7 days ago
        older_weights_7d = [w for w in weights if datetime.strptime(w['date'], '%Y-%m-%d').date() <= seven_days_ago]
        if older_weights_7d:
            weight_7d_change = round(latest_weight - older_weights_7d[0]['weight'], 1)

        # Find weight from ~30 days ago
        thirty_days_ago = today - timedelta(days=30)
        older_weights_30d = [w for w in weights if datetime.strptime(w['date'], '%Y-%m-%d').date() <= thirty_days_ago]
        if older_weights_30d:
            weight_30d_change = round(latest_weight - older_weights_30d[0]['weight'], 1)

    # ===== BUILD MESSAGE =====
    lines = []

    # Header
    lines.append(f"<b>📊 {month_short} Day {day_of_month}</b>")
    lines.append("")

    # Weekly progress
    lines.append("<b>This week:</b>")
    weekly_cardio_status = "✓" if weekly_cardio >= WEEKLY_CARDIO_GOAL - 1 else "⚠️"
    weekly_strength_status = "✓" if weekly_strength >= WEEKLY_STRENGTH_GOAL - 1 else "⚠️"
    lines.append(f"🏃 Cardio: {weekly_cardio}/{WEEKLY_CARDIO_GOAL} {weekly_cardio_status}")
    lines.append(f"🏋️ Strength: {weekly_strength}/{WEEKLY_STRENGTH_GOAL} {weekly_strength_status}")
    lines.append("")

    # Monthly progress
    lines.append(f"<b>{month_name}:</b>")
    monthly_cardio_status = "✓" if monthly_cardio >= cardio_expected - 1 else "⚠️"
    monthly_strength_status = "✓" if monthly_strength >= strength_expected - 1 else "⚠️"
    lines.append(f"🏃 Cardio: {monthly_cardio}/{MONTHLY_CARDIO_GOAL} {monthly_cardio_status}")
    lines.append(f"🏋️ Strength: {monthly_strength}/{MONTHLY_STRENGTH_GOAL} {monthly_strength_status}")

    # Pace alerts (only if behind on monthly)
    pace_issues = []
    remaining_days = days_in_month - day_of_month
    if remaining_days > 0:
        if monthly_cardio < cardio_expected - 1:
            needed = MONTHLY_CARDIO_GOAL - monthly_cardio
            per_week = round(needed / (remaining_days / 7), 1)
            pace_issues.append(f"Need {per_week} cardio/week to hit monthly goal")

        if monthly_strength < strength_expected - 1:
            needed = MONTHLY_STRENGTH_GOAL - monthly_strength
            per_week = round(needed / (remaining_days / 7), 1)
            pace_issues.append(f"Need {per_week} strength/week to hit monthly goal")

    if pace_issues:
        lines.append("")
        for issue in pace_issues:
            lines.append(f"<i>{issue}</i>")

    # Rest days alert
    if rest_days >= REST_DAY_WARNING:
        lines.append("")
        if rest_days >= REST_DAY_URGENT:
            lines.append(f"😴 <b>{rest_days} rest days in a row</b>")
        else:
            lines.append(f"😴 {rest_days} rest days in a row")

    # Weight section
    lines.append("")
    if days_since_weighin is not None and days_since_weighin >= WEIGHIN_REMINDER_DAYS:
        lines.append(f"⚖️ <b>No weigh-in for {days_since_weighin} days</b>")
    elif latest_weight:
        lines.append(f"⚖️ {latest_weight} kg")
        weight_changes = []
        if weight_7d_change is not None:
            dir_7d = "↓" if weight_7d_change < 0 else "↑" if weight_7d_change > 0 else "→"
            weight_changes.append(f"{dir_7d} {abs(weight_7d_change)} kg (7d)")
        if weight_30d_change is not None:
            dir_30d = "↓" if weight_30d_change < 0 else "↑" if weight_30d_change > 0 else "→"
            weight_changes.append(f"{dir_30d} {abs(weight_30d_change)} kg (30d)")
        if weight_changes:
            lines.append("   " + "  •  ".join(weight_changes))

    # Falling off warning
    if falling_off_cardio or falling_off_strength:
        lines.append("")
        falling_items = []
        if falling_off_cardio:
            falling_items.append("cardio")
        if falling_off_strength:
            falling_items.append("strength")
        lines.append(f"⏳ Falling off tomorrow: {', '.join(falling_items)} from 8 days ago")

    # Today's recommendation
    lines.append("")
    lines.append("<b>Today:</b>")

    suggestion = get_today_suggestion(
        rest_days=rest_days,
        weekly_cardio=weekly_cardio,
        weekly_strength=weekly_strength,
        monthly_cardio=monthly_cardio,
        monthly_strength=monthly_strength,
        cardio_expected=cardio_expected,
        strength_expected=strength_expected,
        exercises=exercises,
        today=today,
        falling_off_cardio=falling_off_cardio,
        falling_off_strength=falling_off_strength
    )
    lines.append(f"→ {suggestion}")

    return "\n".join(lines)


def get_today_suggestion(rest_days, weekly_cardio, weekly_strength,
                         monthly_cardio, monthly_strength,
                         cardio_expected, strength_expected,
                         exercises, today,
                         falling_off_cardio=False, falling_off_strength=False):
    """Get actionable suggestion for TODAY based on priority logic and what's falling off."""

    def is_cardio(e):
        return any(t in CARDIO_TYPES for t in e['types'])

    def is_strength(e):
        return 'Kettlebells' in e['types']

    # Priority 1: 3+ rest days - urgent
    if rest_days >= REST_DAY_URGENT:
        return "Get moving! Even a 20min walk counts."

    # Priority 2: 2 rest days - warning
    if rest_days >= REST_DAY_WARNING:
        return "Time to move. Light cardio or kettlebells."

    # Priority 3: Falling off - need to replace what's leaving the 7-day window
    if falling_off_strength and weekly_strength <= WEEKLY_STRENGTH_GOAL:
        return "Kettlebells - replace what's falling off tomorrow"

    if falling_off_cardio and weekly_cardio <= WEEKLY_CARDIO_GOAL:
        return "Cardio - replace what's falling off tomorrow"

    # Priority 4: Weekly strength behind AND no recent strength
    if weekly_strength < WEEKLY_STRENGTH_GOAL - 1:
        if not has_activity_in_last_n_days(exercises, is_strength, 2, today):
            return "Kettlebells - you're behind this week"

    # Priority 5: Weekly cardio behind AND no recent cardio
    if weekly_cardio < WEEKLY_CARDIO_GOAL - 1:
        if not has_activity_in_last_n_days(exercises, is_cardio, 2, today):
            return "Cardio session - you're behind this week"

    # Priority 6: Monthly strength behind pace
    if monthly_strength < strength_expected - 1:
        return "Kettlebells session"

    # Priority 7: Monthly cardio behind pace
    if monthly_cardio < cardio_expected - 1:
        return "MAF cardio (walk, run, or cycle)"

    # Priority 8: No strength in last 3 days
    if not has_activity_in_last_n_days(exercises, is_strength, 3, today):
        return "Kettlebells (none in last 3 days)"

    # Priority 9: No cardio in last 3 days
    if not has_activity_in_last_n_days(exercises, is_cardio, 3, today):
        return "Easy cardio for recovery"

    # Priority 10: All good
    return "On track. Rest or light movement."


def check_and_notify():
    """Build and send daily summary."""
    message = build_daily_message()
    send_telegram(message)


def test_notification():
    """Send a test message."""
    send_telegram("🤖 Health Coach connected. Daily summaries at 6am.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_notification()
    else:
        check_and_notify()
