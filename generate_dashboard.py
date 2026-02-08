#!/usr/bin/env python3
"""
Health Dashboard Generator
==========================
Fetches exercise data from the local SQLite database and generates an interactive HTML dashboard.

Run this after syncing Garmin data to update the dashboard.
"""

import os
import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv
from db import init_db, get_connection

load_dotenv()

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')


def fetch_all_exercises():
    """Fetch all exercises from the database."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM activities ORDER BY date DESC").fetchall()
    conn.close()

    return [
        {
            'date': row['date'],
            'name': row['exercise'],
            'types': [row['type']],
            'duration': row['duration'] or 0,
            'avg_hr': row['avg_heart_rate'] or 0
        }
        for row in rows
    ]


def fetch_weight_entries():
    """Fetch weight entries from the database."""
    conn = get_connection()
    rows = conn.execute("SELECT date, weight_kg FROM weigh_ins ORDER BY date DESC").fetchall()
    conn.close()

    return [{'date': row['date'], 'weight': row['weight_kg']} for row in rows]


def calculate_streak(exercises):
    """Calculate current and longest exercise streak."""
    if not exercises:
        return 0, 0

    # Get unique dates sorted from oldest to newest
    dates = sorted(set(e['date'][:10] for e in exercises))

    if not dates:
        return 0, 0

    # Convert to date objects
    date_objects = [datetime.strptime(d, '%Y-%m-%d').date() for d in dates]
    today = datetime.now().date()

    # Calculate all streaks
    streaks = []
    current_run = 1

    for i in range(1, len(date_objects)):
        if (date_objects[i] - date_objects[i-1]).days == 1:
            current_run += 1
        else:
            streaks.append((current_run, date_objects[i-1]))  # (length, end_date)
            current_run = 1

    # Don't forget the last streak
    streaks.append((current_run, date_objects[-1]))

    # Longest streak
    longest_streak = max(s[0] for s in streaks) if streaks else 0

    # Current streak - check if the most recent workout is today or yesterday
    last_workout_date = date_objects[-1]
    days_since_last = (today - last_workout_date).days

    if days_since_last > 1:
        # Streak is broken
        current_streak = 0
    else:
        # Find the streak that ends with the most recent date
        current_streak = streaks[-1][0] if streaks else 0

    return current_streak, longest_streak


def calculate_weekly_stats(exercises):
    """Calculate workouts per week for the last 8 weeks."""
    weeks = defaultdict(int)

    for ex in exercises:
        date = datetime.strptime(ex['date'][:10], '%Y-%m-%d')
        week_start = date - timedelta(days=date.weekday())
        week_key = week_start.strftime('%Y-%m-%d')
        weeks[week_key] += 1

    # Get last 8 weeks
    today = datetime.now()
    result = []
    for i in range(7, -1, -1):
        week_start = today - timedelta(days=today.weekday() + (i * 7))
        week_key = week_start.strftime('%Y-%m-%d')
        week_label = week_start.strftime('%d %b')
        result.append({
            'week': week_label,
            'count': weeks.get(week_key, 0)
        })

    return result


def calculate_activity_breakdown(exercises):
    """Calculate activity type distribution."""
    type_counts = defaultdict(int)
    type_duration = defaultdict(int)

    for ex in exercises:
        for t in ex['types']:
            type_counts[t] += 1
            type_duration[t] += ex['duration']

    return [
        {'type': t, 'count': c, 'duration': type_duration[t]}
        for t, c in sorted(type_counts.items(), key=lambda x: -x[1])
    ]


def calculate_this_week_days(exercises):
    """Get which days this week have workouts."""
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())

    workout_days = set()
    for ex in exercises:
        ex_date = datetime.strptime(ex['date'][:10], '%Y-%m-%d').date()
        if ex_date >= week_start:
            workout_days.add(ex_date.weekday())

    return list(workout_days)


def prepare_weight_chart_data(weights):
    """Prepare weight data for chart, starting from Jan 1, 2026."""
    start_date = datetime(2026, 1, 1).date()

    # Filter weights from Jan 1, 2026 onwards and sort by date
    filtered = [w for w in weights if datetime.strptime(w['date'], '%Y-%m-%d').date() >= start_date]
    sorted_weights = sorted(filtered, key=lambda x: x['date'])

    return [{'date': w['date'], 'weight': w['weight']} for w in sorted_weights]


def generate_ai_summary(exercises, weights, stats):
    """Generate an AI-powered progress summary using Claude."""
    if not ANTHROPIC_API_KEY:
        return "AI summary unavailable - no API key configured."

    try:
        # Calculate activity mix for last 7 days
        activity_counts_7d = {}
        for ex in stats.get('last_7_days_exercises', []):
            for t in ex['types']:
                activity_counts_7d[t] = activity_counts_7d.get(t, 0) + 1
        activity_mix_7d = ', '.join([f"{k}: {v}" for k, v in sorted(activity_counts_7d.items(), key=lambda x: -x[1])])

        total_7d = len(stats.get('last_7_days_exercises', []))
        cardio_7d = stats.get('cardio_7d', 0)
        strength_7d = stats.get('strength_7d', 0)
        weight_change_7d = stats.get('weight_change_7d', 0)

        # Calculate activity mix for last 30 days
        activity_counts_30d = {}
        for ex in stats.get('last_30_days_exercises', []):
            for t in ex['types']:
                activity_counts_30d[t] = activity_counts_30d.get(t, 0) + 1
        activity_mix_30d = ', '.join([f"{k}: {v}" for k, v in sorted(activity_counts_30d.items(), key=lambda x: -x[1])])

        total_30d = len(stats.get('last_30_days_exercises', []))
        weight_change_30d = stats.get('weight_change_30d', 0)

        # Weight data for context
        weight_summary = []
        for w in weights[:10]:
            weight_summary.append(f"- {w['date']}: {w['weight']} kg")

        latest_weight = weights[0]['weight'] if weights else None
        start_weight = 97.5  # Jan 2026 starting weight
        total_lost = round(start_weight - latest_weight, 1) if latest_weight else None

        # Calculate time elapsed
        from datetime import date
        today = date.today()
        days_since_jan1 = (today - date(2026, 1, 1)).days
        weeks_elapsed = round(days_since_jan1 / 7, 1)
        months_elapsed = round(days_since_jan1 / 30, 1)

        prompt = f"""You are a professional health consultant. Write THREE short paragraphs with blank lines between them. Use "you/your" naturally - no greeting, no sign-off, just the assessment.

CURRENT DATE: {today.strftime('%d %B %Y')}
TIME ELAPSED SINCE JAN 1 2026: {days_since_jan1} days ({weeks_elapsed} weeks, {months_elapsed} months)

COACHING PHILOSOPHY:
- Intermittent fasting: 16-hour fasts, eating window ~11am-7pm
- Low-carb eating to reduce insulin resistance and improve fat burning
- NOT a calorie counting approach - focus is on insulin/metabolic health
- Phil Maffetone / MAF Method for exercise: low-intensity aerobic training at MAF heart rate (180 minus age)
- Build aerobic base before adding intensity; avoid chronic cardio or HIIT
- Never recommend HIIT or high-intensity intervals
- Never mention "caloric deficit" or calorie counting - that's not the framework
- Goal: improve insulin sensitivity and fat metabolism through fasting, low-carb, and consistent sub-MAF exercise

CLIENT'S TARGETS:
- Weight: 82 kg by end of 2026 (from 97.5 kg in Jan 2026)
- Exercise: Daily movement, kettlebells 3-4x/week, MAF cardio
- Weekly goals: 4 cardio, 3 strength (per 7 days)
- Monthly goals: 16 cardio activities, 10 strength activities
- Goal pace: 1.5-2 kg weight loss per month

LAST 7 DAYS DATA:
- Total workouts: {total_7d}
- Cardio: {cardio_7d}/4, Strength: {strength_7d}/3
- Activity mix: {activity_mix_7d if activity_mix_7d else 'No activities'}
- Weight change: {weight_change_7d if weight_change_7d is not None else 'No data'} kg
- Weigh-ins count: {len(stats.get('last_7_days_weights', []))}

LAST 30 DAYS DATA:
- Total workouts: {total_30d}
- Activity mix: {activity_mix_30d if activity_mix_30d else 'No activities'}
- Weight change: {weight_change_30d if weight_change_30d is not None else 'No data'} kg

WEIGHT JOURNEY:
- Starting weight (1 Jan 2026): {start_weight} kg
- Current weight: {latest_weight if latest_weight else 'No data'} kg
- Total lost so far: {total_lost if total_lost else 'No data'} kg in {days_since_jan1} days
- Loss rate: {round(total_lost / weeks_elapsed, 2) if total_lost and weeks_elapsed else 'N/A'} kg/week = {round(total_lost / months_elapsed, 1) if total_lost and months_elapsed else 'N/A'} kg/month
- Target: 82 kg by end of 2026 (need to lose {round(latest_weight - 82, 1) if latest_weight else 'N/A'} kg more)

RECENT WEIGHT ENTRIES:
{chr(10).join(weight_summary[:5])}

Write exactly THREE paragraphs:

PARAGRAPH 1 (2-3 sentences): Comment on last 7 days only. How was the week? Activity balance? Any concerns?

PARAGRAPH 2 (2-3 sentences): Comment on last 30 days. Activity mix and frequency - on track for monthly goals?

PARAGRAPH 3 (2-3 sentences): Summarise weight progress from Jan 2026 to now. Is the pace on track for 82 kg by end of year?

Be direct and analytical. No exclamation marks. Maximum 180 words total."""

        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-3-haiku-20240307",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        response.raise_for_status()
        data = response.json()
        return data['content'][0]['text']

    except Exception as e:
        print(f"AI summary error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return f"AI summary temporarily unavailable. Error: {str(e)[:100]}"


def generate_dashboard(exercises, weights):
    """Generate the HTML dashboard."""

    current_streak, longest_streak = calculate_streak(exercises)
    weekly_stats = calculate_weekly_stats(exercises)
    activity_breakdown = calculate_activity_breakdown(exercises)
    this_week_days = calculate_this_week_days(exercises)

    # Total stats
    total_workouts = len(exercises)
    exercises_with_duration = [e for e in exercises if e['duration'] and e['duration'] > 0]
    total_duration = sum(e['duration'] for e in exercises_with_duration)
    avg_duration = round(total_duration / len(exercises_with_duration), 1) if exercises_with_duration else 0

    # This week stats
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    this_week_workouts = len([e for e in exercises if datetime.strptime(e['date'][:10], '%Y-%m-%d').date() >= week_start])


    # Weight trend
    latest_weight = weights[0]['weight'] if weights else None
    weight_change = None
    if len(weights) >= 2:
        weight_change = round(weights[0]['weight'] - weights[-1]['weight'], 1)

    # Weight chart data (from Jan 1, 2026)
    weight_chart_data = prepare_weight_chart_data(weights)

    # Cardio types definition
    cardio_types = {'Run', 'Walk', 'Indoor Cycle', 'Hike', 'Trail Run', 'Rucking', 'Padel', 'Tennis', 'Golf'}

    # Last 7 days data (yesterday + 6 days before = 7 days, excluding today)
    yesterday = today - timedelta(days=1)
    six_days_ago = yesterday - timedelta(days=6)
    last_7d_label = f"{six_days_ago.strftime('%a %-d %b')} – {yesterday.strftime('%a %-d %b')}"
    last_7_days_exercises = [e for e in exercises if six_days_ago <= datetime.strptime(e['date'][:10], '%Y-%m-%d').date() <= yesterday]
    last_7_days_weights = [w for w in weights if six_days_ago <= datetime.strptime(w['date'], '%Y-%m-%d').date() <= yesterday]

    # Weight change over 7 days (latest weight vs weight from ~7 days ago)
    weight_change_7d = None
    if weights:
        latest_weight_7d = weights[0]['weight']
        older_weights_7d = [w for w in weights if datetime.strptime(w['date'], '%Y-%m-%d').date() <= six_days_ago]
        if older_weights_7d:
            weight_change_7d = round(latest_weight_7d - older_weights_7d[0]['weight'], 1)

    # Total hours last 7 days
    total_minutes_7d = sum(e['duration'] for e in last_7_days_exercises if e['duration'] and e['duration'] > 0)
    total_hours_7d = round(total_minutes_7d / 60, 1)

    # 7-day summary stats
    cardio_7d = len([e for e in last_7_days_exercises if any(t in cardio_types for t in e['types'])])
    strength_7d = len([e for e in last_7_days_exercises if 'Kettlebells' in e['types']])

    # Rest days in last 7 days
    workout_dates_7d = set(e['date'][:10] for e in last_7_days_exercises)
    rest_days_7d = 7 - len(workout_dates_7d)

    # Calculate stats for each calendar month dynamically
    def get_month_stats(year, month, exercises_list, weights_list, is_current_month=False):
        month_start = datetime(year, month, 1).date()
        if month == 12:
            month_end = datetime(year + 1, 1, 1).date()
        else:
            month_end = datetime(year, month + 1, 1).date()

        days_in_month = (month_end - month_start).days

        month_exercises = [e for e in exercises_list
                          if month_start <= datetime.strptime(e['date'][:10], '%Y-%m-%d').date() < month_end]
        month_weights = [w for w in weights_list
                        if month_start <= datetime.strptime(w['date'], '%Y-%m-%d').date() < month_end]

        cardio = len([e for e in month_exercises if any(t in cardio_types for t in e['types'])])
        strength = len([e for e in month_exercises if 'Kettlebells' in e['types']])
        total_minutes = sum(e['duration'] for e in month_exercises if e['duration'] and e['duration'] > 0)
        total_hours = round(total_minutes / 60)
        workout_dates = set(e['date'][:10] for e in month_exercises)

        if is_current_month:
            rest_days = today.day - len(workout_dates)
        else:
            rest_days = days_in_month - len(workout_dates)

        weight_change = None
        if month_weights:
            sorted_month_weights = sorted(month_weights, key=lambda x: x['date'])
            last_weight_this_month = sorted_month_weights[-1]['weight']
            first_weight_this_month = sorted_month_weights[0]['weight']

            # Find last weight from previous month
            prev_month_weights = [w for w in weights_list
                                  if datetime.strptime(w['date'], '%Y-%m-%d').date() < month_start]
            if prev_month_weights:
                sorted_prev = sorted(prev_month_weights, key=lambda x: x['date'])
                last_weight_prev_month = sorted_prev[-1]['weight']
                weight_change = round(last_weight_this_month - last_weight_prev_month, 1)
            elif year == 2026 and month == 1:
                # For Jan 2026, assume Dec 31 weight = first Jan weight
                weight_change = round(last_weight_this_month - first_weight_this_month, 1)

        return {
            'name': datetime(year, month, 1).strftime('%B %Y'),
            'cardio': cardio,
            'strength': strength,
            'hours': total_hours,
            'weight_change': weight_change,
            'rest_days': rest_days,
            'year': year,
            'month': month
        }

    # Find all unique months in the exercise data (2026 onwards only)
    all_months = set()
    for e in exercises:
        ex_date = datetime.strptime(e['date'][:10], '%Y-%m-%d').date()
        if ex_date.year >= 2026:
            all_months.add((ex_date.year, ex_date.month))

    # Sort months in reverse chronological order (most recent first)
    sorted_months = sorted(all_months, reverse=True)

    # Calculate stats for each month
    monthly_stats = []
    for year, month in sorted_months:
        is_current = (year == today.year and month == today.month)
        stats = get_month_stats(year, month, exercises, weights, is_current)
        monthly_stats.append(stats)

    # For AI summary - use last 30 days data
    thirty_days_ago = today - timedelta(days=30)
    last_30_days_exercises = [e for e in exercises if datetime.strptime(e['date'][:10], '%Y-%m-%d').date() >= thirty_days_ago]
    last_30_days_weights = [w for w in weights if datetime.strptime(w['date'], '%Y-%m-%d').date() >= thirty_days_ago]
    weight_change_30d = None
    if last_30_days_weights and len(last_30_days_weights) >= 2:
        sorted_weights_30d = sorted(last_30_days_weights, key=lambda x: x['date'])
        weight_change_30d = round(sorted_weights_30d[-1]['weight'] - sorted_weights_30d[0]['weight'], 1)

    # Average weight loss per week since Jan 1, 2026
    start_weight_jan1 = 97.5
    days_since_jan1 = (today - datetime(2026, 1, 1).date()).days
    weeks_since_jan1 = days_since_jan1 / 7
    total_lost_ytd = round(start_weight_jan1 - latest_weight, 1) if latest_weight else None
    avg_loss_per_week = round(total_lost_ytd / weeks_since_jan1, 2) if total_lost_ytd and weeks_since_jan1 > 0 else None

    # 2026 Year to Date stats
    ytd_start = datetime(2026, 1, 1).date()
    ytd_exercises = [e for e in exercises if datetime.strptime(e['date'][:10], '%Y-%m-%d').date() >= ytd_start]

    running_ytd = len([e for e in ytd_exercises if any(t in {'Run', 'Trail Run'} for t in e['types'])])
    cycling_ytd = len([e for e in ytd_exercises if 'Indoor Cycle' in e['types']])
    walk_hike_ytd = len([e for e in ytd_exercises if any(t in {'Walk', 'Hike', 'Rucking'} for t in e['types'])])
    racquet_ytd = len([e for e in ytd_exercises if any(t in {'Tennis', 'Padel'} for t in e['types'])])
    strength_ytd = len([e for e in ytd_exercises if 'Kettlebells' in e['types']])

    # Target weight countdown
    target_weight = 82.0
    kg_to_go = round(latest_weight - target_weight, 1) if latest_weight else None

    # Projected date to reach target (based on 30-day rate)
    projected_date = None
    if weight_change_30d and weight_change_30d < 0 and kg_to_go and kg_to_go > 0:
        monthly_loss_rate = abs(weight_change_30d)
        months_to_go = kg_to_go / monthly_loss_rate if monthly_loss_rate > 0 else 0
        projected_date = (today + timedelta(days=months_to_go * 30)).strftime('%b %Y')

    # 10-day rolling average for weight chart (calendar-based)
    weight_chart_with_avg = []
    sorted_weights_all = sorted(weight_chart_data, key=lambda x: x['date'])
    for w in sorted_weights_all:
        current_date = datetime.strptime(w['date'], '%Y-%m-%d').date()
        ten_days_ago = current_date - timedelta(days=10)
        # Get all weights within the last 10 calendar days
        window = [x for x in sorted_weights_all
                  if ten_days_ago < datetime.strptime(x['date'], '%Y-%m-%d').date() <= current_date]
        rolling_avg = round(sum(x['weight'] for x in window) / len(window), 1) if window else w['weight']
        weight_chart_with_avg.append({
            'date': w['date'],
            'weight': w['weight'],
            'rolling_avg': rolling_avg
        })

    # Top activity
    top_activity = activity_breakdown[0]['type'] if activity_breakdown else 'None'

    # Generate AI summary
    ai_stats = {
        'current_streak': current_streak,
        'longest_streak': longest_streak,
        'this_week_workouts': this_week_workouts,
        'avg_duration': avg_duration,
        'top_activity': top_activity,
        'last_7_days_exercises': last_7_days_exercises,
        'last_7_days_weights': last_7_days_weights,
        'cardio_7d': cardio_7d,
        'strength_7d': strength_7d,
        'weight_change_7d': weight_change_7d,
        'last_30_days_exercises': last_30_days_exercises,
        'last_30_days_weights': last_30_days_weights,
        'weight_change_30d': weight_change_30d,
        'activity_breakdown': activity_breakdown
    }
    ai_summary = generate_ai_summary(exercises, weights, ai_stats)

    dashboard_data = {
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'currentStreak': current_streak,
        'longestStreak': longest_streak,
        'totalWorkouts': total_workouts,
        'totalDuration': total_duration,
        'avgDuration': avg_duration,
        'thisWeekWorkouts': this_week_workouts,
        'thisWeekDays': this_week_days,
        'weeklyStats': weekly_stats,
        'activityBreakdown': activity_breakdown[:6],
        'latestWeight': latest_weight,
        'weightChange': weight_change,
        'recentWorkouts': exercises[:10]
    }

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pierre's Health Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; }}
        .glass {{ background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }}
        .streak-fire {{ animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.7; }} }}
    </style>
</head>
<body class="text-white p-6">
    <div class="max-w-6xl mx-auto">
        <!-- Header -->
        <div class="mb-8">
            <h1 class="text-3xl font-bold mb-2">Health Dashboard</h1>
            <p class="text-gray-400">Last updated: {dashboard_data['generated']}</p>
        </div>

        <!-- AI Summary -->
        <div class="glass rounded-2xl p-6 mb-6 border-l-4 border-emerald-400">
            <div class="flex justify-between items-center cursor-pointer" onclick="toggleSection('summary')">
                <div class="flex items-center gap-3">
                    <div class="text-2xl">🤖</div>
                    <h2 class="text-xl font-semibold">Progress Summary</h2>
                </div>
                <span id="summary-toggle" class="text-gray-400">▶</span>
            </div>
            <div id="summary-content" class="mt-4 text-gray-300 leading-relaxed space-y-3" style="display: none;">
                {format_ai_paragraphs(ai_summary)}
            </div>
        </div>

        <!-- This Week Progress -->
        <div class="glass rounded-2xl p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">This Week</h2>
            <div class="flex justify-between gap-2">
                {generate_week_days(this_week_days)}
            </div>
        </div>

        <!-- Calendar View -->
        <div class="glass rounded-2xl p-6 mb-6">
            <div class="flex justify-between items-center cursor-pointer" onclick="toggleSection('calendar')">
                <h2 class="text-xl font-semibold">Calendar</h2>
                <span id="calendar-toggle" class="text-gray-400">▶</span>
            </div>
            <div id="calendar-content" style="display: none;" class="mt-4">
                <div class="flex justify-between items-center mb-4">
                    <button onclick="prevMonth()" class="px-3 py-1 rounded-lg bg-white/10 hover:bg-white/20 transition">← Prev</button>
                    <h3 id="calendar-month-label" class="text-lg font-semibold"></h3>
                    <button onclick="nextMonth()" class="px-3 py-1 rounded-lg bg-white/10 hover:bg-white/20 transition">Next →</button>
                </div>
                <div class="grid grid-cols-7 gap-1 mb-2">
                    <div class="text-center text-xs text-gray-500 py-1">Mon</div>
                    <div class="text-center text-xs text-gray-500 py-1">Tue</div>
                    <div class="text-center text-xs text-gray-500 py-1">Wed</div>
                    <div class="text-center text-xs text-gray-500 py-1">Thu</div>
                    <div class="text-center text-xs text-gray-500 py-1">Fri</div>
                    <div class="text-center text-xs text-gray-500 py-1">Sat</div>
                    <div class="text-center text-xs text-gray-500 py-1">Sun</div>
                </div>
                <div id="calendar-grid" class="grid grid-cols-7 gap-1"></div>
            </div>
        </div>

        <!-- Last 7 Days Summary -->
        <div class="glass rounded-2xl p-6 mb-6">
            <h2 class="text-xl font-semibold mb-4">Last 7 Days <span class="text-sm font-normal text-gray-400">({last_7d_label})</span></h2>
            <div class="grid grid-cols-5 gap-4 mb-4">
                <div class="text-center">
                    <div class="text-3xl mb-1">🏃</div>
                    <div class="text-3xl font-bold {'text-green-400' if cardio_7d >= 4 else 'text-yellow-400' if cardio_7d >= 3 else 'text-red-400'}">{cardio_7d}<span class="text-lg text-gray-400">/4</span></div>
                    <div class="text-gray-400 text-xs">Cardio</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">🏋️</div>
                    <div class="text-3xl font-bold {'text-green-400' if strength_7d >= 3 else 'text-yellow-400' if strength_7d >= 2 else 'text-red-400'}">{strength_7d}<span class="text-lg text-gray-400">/3</span></div>
                    <div class="text-gray-400 text-xs">Strength</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">⏱️</div>
                    <div class="text-3xl font-bold text-green-400">{total_hours_7d}</div>
                    <div class="text-gray-400 text-xs">Hours</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">⚖️</div>
                    <div class="text-3xl font-bold {'text-green-400' if weight_change_7d and weight_change_7d < 0 else 'text-red-400' if weight_change_7d and weight_change_7d > 0 else 'text-gray-400'}">{('+' if weight_change_7d and weight_change_7d > 0 else '') + str(weight_change_7d) if weight_change_7d else '--'}</div>
                    <div class="text-gray-400 text-xs">kg</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">😴</div>
                    <div class="text-3xl font-bold text-purple-400">{rest_days_7d}</div>
                    <div class="text-gray-400 text-xs">Rest Days</div>
                </div>
            </div>
            <div class="border-t border-white/10 pt-4">
                <div class="flex justify-between items-center cursor-pointer" onclick="toggleSection('7d-activities')">
                    <span class="text-sm text-gray-400">Activities</span>
                    <span id="7d-activities-toggle" class="text-gray-400">▶</span>
                </div>
                <div id="7d-activities-content" class="space-y-3 mt-3" style="display: none;">
                    {generate_recent_workouts(last_7_days_exercises)}
                </div>
            </div>
        </div>

        <!-- Monthly Summaries (dynamically generated) -->
        {generate_monthly_sections(monthly_stats)}

        <!-- Weight Chart -->
        <div class="glass rounded-2xl p-6 mb-6">
            <div class="flex justify-between items-start mb-4">
                <div class="flex items-center gap-3">
                    <h2 class="text-xl font-semibold">Weight Progress (from Jan 1, 2026)</h2>
                    <button id="zoomToggle" onclick="toggleWeightZoom()" class="px-3 py-1 text-xs rounded-full bg-white/10 hover:bg-white/20 transition">🔍 Zoom Out</button>
                </div>
                <div class="flex gap-8 items-start">
                    <div class="text-right">
                        <div class="text-4xl font-bold {'text-green-400' if avg_loss_per_week and avg_loss_per_week > 0 else 'text-red-400' if avg_loss_per_week and avg_loss_per_week < 0 else 'text-gray-400'}">{avg_loss_per_week if avg_loss_per_week else '--'} <span class="text-lg text-gray-400">kg/wk</span></div>
                        <div class="text-sm text-gray-400">avg since Jan 1</div>
                    </div>
                    <div class="text-right">
                        <div class="text-4xl font-bold {'text-green-400' if weight_change_30d and weight_change_30d < 0 else 'text-red-400' if weight_change_30d and weight_change_30d > 0 else 'text-gray-400'}">{abs(weight_change_30d) if weight_change_30d else '--'} <span class="text-lg text-gray-400">kg</span></div>
                        <div class="text-sm text-gray-400">{'lost' if weight_change_30d and weight_change_30d < 0 else 'gained' if weight_change_30d and weight_change_30d > 0 else ''} (30d)</div>
                    </div>
                    <div class="text-right">
                        <div class="text-4xl font-bold text-emerald-400">{latest_weight if latest_weight else '--'} <span class="text-lg text-gray-400">kg</span></div>
                        <div class="text-sm text-gray-400">current</div>
                    </div>
                </div>
            </div>
            <canvas id="weightChart" height="100"></canvas>
            <div class="border-t border-white/10 pt-4 mt-4">
                <div class="flex justify-between items-center cursor-pointer" onclick="toggleSection('weighins')">
                    <span class="text-sm text-gray-400">Weigh-ins (10 most recent)</span>
                    <span id="weighins-toggle" class="text-gray-400">▶</span>
                </div>
                <div id="weighins-content" class="space-y-2 mt-3" style="display: none;">
                    {generate_weighin_list(weights)}
                </div>
            </div>
        </div>

        <!-- 2026 Year to Date -->
        <div class="glass rounded-2xl p-6 mb-6">
            <div class="flex justify-between items-center cursor-pointer" onclick="toggleSection('ytd')">
                <h2 class="text-xl font-semibold">2026 Year to Date</h2>
                <span id="ytd-toggle" class="text-gray-400">▼</span>
            </div>
            <div id="ytd-content" class="grid grid-cols-5 gap-4 mt-4">
                <div class="text-center">
                    <div class="text-3xl mb-1">🏃</div>
                    <div class="text-3xl font-bold text-blue-400">{running_ytd}</div>
                    <div class="text-gray-400 text-xs">Running</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">🚴</div>
                    <div class="text-3xl font-bold text-green-400">{cycling_ytd}</div>
                    <div class="text-gray-400 text-xs">Cycling</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">🥾</div>
                    <div class="text-3xl font-bold text-yellow-400">{walk_hike_ytd}</div>
                    <div class="text-gray-400 text-xs">Walk/Hike</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">🎾</div>
                    <div class="text-3xl font-bold text-pink-400">{racquet_ytd}</div>
                    <div class="text-gray-400 text-xs">Tennis/Padel</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">🏋️</div>
                    <div class="text-3xl font-bold text-orange-400">{strength_ytd}</div>
                    <div class="text-gray-400 text-xs">Strength</div>
                </div>
            </div>
        </div>

        <!-- Full Activity Log -->
        <div class="glass rounded-2xl p-6 mb-6">
            <div class="flex justify-between items-center cursor-pointer" onclick="toggleSection('activity-log')">
                <h2 class="text-xl font-semibold">Activity Log (from Jan 2026)</h2>
                <span id="activity-log-toggle" class="text-gray-400">▶</span>
            </div>
            <div id="activity-log-content" class="space-y-3 mt-4" style="display: none;">
                {generate_full_activity_log(ytd_exercises)}
            </div>
        </div>
    </div>

    <script>
        // Toggle section visibility
        function toggleSection(id) {{
            const content = document.getElementById(id + '-content');
            const toggle = document.getElementById(id + '-toggle');
            if (content.style.display === 'none') {{
                content.style.display = (id === 'calendar' || id === 'summary' || id === 'activity-log' || id === '7d-activities' || id === 'weighins') ? 'block' : 'grid';
                toggle.textContent = '▼';
            }} else {{
                content.style.display = 'none';
                toggle.textContent = '▶';
            }}
        }}

        // Calendar functionality
        const exerciseDates = {json.dumps(list(set(e['date'][:10] for e in exercises)))};
        let currentCalendarDate = new Date();

        function renderCalendar() {{
            const year = currentCalendarDate.getFullYear();
            const month = currentCalendarDate.getMonth();

            // Update month label
            const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                               'July', 'August', 'September', 'October', 'November', 'December'];
            // Count exercise days in this month
            const monthExerciseDays = exerciseDates.filter(d => {{
                const date = new Date(d);
                return date.getFullYear() === year && date.getMonth() === month;
            }}).length;
            document.getElementById('calendar-month-label').textContent = `${{monthNames[month]}} ${{year}} (${{monthExerciseDays}} days)`;

            // Get first day of month and total days
            const firstDay = new Date(year, month, 1);
            const lastDay = new Date(year, month + 1, 0);
            const totalDays = lastDay.getDate();

            // Monday = 0, Sunday = 6 (adjust from JS default where Sunday = 0)
            let startDay = firstDay.getDay() - 1;
            if (startDay < 0) startDay = 6;

            const today = new Date();
            const todayStr = today.toISOString().split('T')[0];

            let html = '';

            // Empty cells for days before start of month
            for (let i = 0; i < startDay; i++) {{
                html += '<div class="aspect-square"></div>';
            }}

            // Days of the month
            for (let day = 1; day <= totalDays; day++) {{
                const dateStr = `${{year}}-${{String(month + 1).padStart(2, '0')}}-${{String(day).padStart(2, '0')}}`;
                const hasExercise = exerciseDates.includes(dateStr);
                const isToday = dateStr === todayStr;
                const isFuture = new Date(dateStr) > today;

                let bgClass = 'bg-red-500/60';
                if (hasExercise) bgClass = 'bg-green-500';
                else if (isFuture) bgClass = 'bg-gray-800/30';

                const todayRing = isToday ? 'ring-2 ring-white' : '';
                const textColor = isFuture ? 'text-gray-600' : 'text-gray-300';

                html += `<div class="aspect-square ${{bgClass}} ${{todayRing}} rounded-lg flex items-center justify-center ${{textColor}} text-sm">${{day}}</div>`;
            }}

            document.getElementById('calendar-grid').innerHTML = html;
        }}

        function prevMonth() {{
            currentCalendarDate.setMonth(currentCalendarDate.getMonth() - 1);
            renderCalendar();
        }}

        function nextMonth() {{
            currentCalendarDate.setMonth(currentCalendarDate.getMonth() + 1);
            renderCalendar();
        }}

        // Initialize calendar
        renderCalendar();

        const weightData = {json.dumps(weight_chart_with_avg)};

        // Weight Chart
        let weightChart;
        let isZoomedOut = false;

        function toggleWeightZoom() {{
            isZoomedOut = !isZoomedOut;
            const btn = document.getElementById('zoomToggle');
            if (isZoomedOut) {{
                weightChart.options.scales.y.min = 80;
                weightChart.options.scales.y.max = 100;
                btn.textContent = '🔍 Zoom In';
            }} else {{
                weightChart.options.scales.y.min = undefined;
                weightChart.options.scales.y.max = undefined;
                btn.textContent = '🔍 Zoom Out';
            }}
            weightChart.update();
        }}

        if (weightData.length > 0) {{
            weightChart = new Chart(document.getElementById('weightChart'), {{
                type: 'line',
                data: {{
                    labels: weightData.map(d => {{
                        const date = new Date(d.date);
                        return date.toLocaleDateString('en-GB', {{ day: 'numeric', month: 'short' }});
                    }}),
                    datasets: [
                        {{
                            label: 'Weight (kg)',
                            data: weightData.map(d => d.weight),
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            fill: true,
                            tension: 0.3,
                            pointBackgroundColor: '#10b981',
                            pointRadius: 4
                        }},
                        {{
                            label: '10-day Avg',
                            data: weightData.map(d => d.rolling_avg),
                            borderColor: '#f97316',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            fill: false,
                            tension: 0.3,
                            pointRadius: 0
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    plugins: {{
                        legend: {{
                            display: true,
                            position: 'top',
                            labels: {{ color: '#fff', usePointStyle: true, padding: 20 }}
                        }}
                    }},
                    scales: {{
                        y: {{
                            ticks: {{ color: '#9ca3af' }},
                            grid: {{ color: 'rgba(255,255,255,0.1)' }}
                        }},
                        x: {{
                            ticks: {{ color: '#9ca3af' }},
                            grid: {{ display: false }}
                        }}
                    }}
                }}
            }});
        }}
    </script>
</body>
</html>'''

    return html


def format_ai_paragraphs(text):
    """Format AI summary text into separate paragraphs."""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    return ''.join(f'<p>{p}</p>' for p in paragraphs)


def generate_monthly_sections(monthly_stats):
    """Generate collapsible sections for each calendar month."""
    html = ""
    for i, stats in enumerate(monthly_stats):
        section_id = f"month-{stats['year']}-{stats['month']}"
        cardio_color = 'text-green-400' if stats['cardio'] >= 16 else 'text-yellow-400' if stats['cardio'] >= 12 else 'text-red-400'
        strength_color = 'text-green-400' if stats['strength'] >= 10 else 'text-yellow-400' if stats['strength'] >= 7 else 'text-red-400'
        weight_color = 'text-green-400' if stats['weight_change'] and stats['weight_change'] < 0 else 'text-red-400' if stats['weight_change'] and stats['weight_change'] > 0 else 'text-gray-400'
        weight_display = ('+' if stats['weight_change'] and stats['weight_change'] > 0 else '') + str(stats['weight_change']) if stats['weight_change'] else '--'

        # First month expanded, others collapsed
        display = 'grid' if i == 0 else 'none'
        toggle = '▼' if i == 0 else '▶'

        html += f'''
        <div class="glass rounded-2xl p-6 mb-6">
            <div class="flex justify-between items-center cursor-pointer" onclick="toggleSection('{section_id}')">
                <h2 class="text-xl font-semibold">{stats['name']}</h2>
                <span id="{section_id}-toggle" class="text-gray-400">{toggle}</span>
            </div>
            <div id="{section_id}-content" class="grid grid-cols-5 gap-4 mt-4" style="display: {display}">
                <div class="text-center">
                    <div class="text-3xl mb-1">🏃</div>
                    <div class="text-3xl font-bold {cardio_color}">{stats['cardio']}<span class="text-lg text-gray-400">/16</span></div>
                    <div class="text-gray-400 text-xs">Cardio</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">🏋️</div>
                    <div class="text-3xl font-bold {strength_color}">{stats['strength']}<span class="text-lg text-gray-400">/10</span></div>
                    <div class="text-gray-400 text-xs">Strength</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">⏱️</div>
                    <div class="text-3xl font-bold text-green-400">{stats['hours']}</div>
                    <div class="text-gray-400 text-xs">Hours</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">⚖️</div>
                    <div class="text-3xl font-bold {weight_color}">{weight_display}</div>
                    <div class="text-gray-400 text-xs">kg</div>
                </div>
                <div class="text-center">
                    <div class="text-3xl mb-1">😴</div>
                    <div class="text-3xl font-bold text-purple-400">{stats['rest_days']}</div>
                    <div class="text-gray-400 text-xs">Rest Days</div>
                </div>
            </div>
        </div>'''
    return html


def generate_week_days(workout_days):
    """Generate week day indicators."""
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    today = datetime.now().weekday()

    html = ""
    for i, day in enumerate(days):
        is_done = i in workout_days
        is_today = i == today

        bg = "bg-green-500" if is_done else "bg-gray-700"
        border = "ring-2 ring-white" if is_today else ""

        html += f'<div class="flex-1 text-center p-3 rounded-xl {bg} {border}"><div class="text-xs text-gray-300">{day}</div><div class="text-lg">{"✓" if is_done else ""}</div></div>'

    return html


def generate_full_activity_log(workouts):
    """Generate full activity log sorted oldest to newest."""
    # Sort by date ascending (oldest first)
    sorted_workouts = sorted(workouts, key=lambda x: x['date'])

    cardio_types = {'Run', 'Walk', 'Indoor Cycle', 'Hike', 'Trail Run', 'Rucking', 'Padel', 'Tennis', 'Golf'}

    html = ""
    for w in sorted_workouts:
        types_str = ", ".join(w['types']) if w['types'] else "Workout"
        date = datetime.strptime(w['date'][:10], '%Y-%m-%d').strftime('%a %d %b')
        duration = f"{w['duration']} min" if w.get('duration') else ""

        # Determine background color based on activity type
        is_strength = 'Kettlebells' in w['types']
        is_cardio = any(t in cardio_types for t in w['types'])

        if is_strength:
            bg_class = "bg-green-500/20"  # Light green for strength
        elif is_cardio:
            bg_class = "bg-orange-500/20"  # Light orange for cardio
        else:
            bg_class = "bg-white/5"  # Default

        html += f'''<div class="flex items-center justify-between p-3 {bg_class} rounded-xl">
            <div>
                <div class="font-medium">{w.get('name') or types_str}</div>
                <div class="text-sm text-gray-400">{date}</div>
            </div>
            <div class="text-right">
                <div class="text-blue-400">{duration}</div>
                <div class="text-xs text-gray-500">{types_str}</div>
            </div>
        </div>'''

    return html


def generate_weighin_list(weights):
    """Generate weigh-in list for 10 most recent weigh-ins."""
    # Sort by date descending (newest first), limit to 10
    sorted_weights = sorted(weights, key=lambda x: x['date'], reverse=True)[:10]

    if not sorted_weights:
        return '<div class="text-gray-500 text-sm">No weigh-ins recorded</div>'

    html = ""
    for i, w in enumerate(sorted_weights):
        date = datetime.strptime(w['date'], '%Y-%m-%d').strftime('%a %d %b')
        weight = w['weight']

        # Calculate change from previous entry
        change_str = ""
        if i < len(sorted_weights) - 1:
            prev_weight = sorted_weights[i + 1]['weight']
            change = round(weight - prev_weight, 1)
            if change < 0:
                change_str = f'<span class="text-green-400">↓ {abs(change)}</span>'
            elif change > 0:
                change_str = f'<span class="text-red-400">↑ {change}</span>'
            else:
                change_str = '<span class="text-gray-400">→ 0</span>'

        html += f'''<div class="flex items-center justify-between p-2 bg-white/5 rounded-lg">
            <span class="text-gray-400 text-sm">{date}</span>
            <div class="flex items-center gap-3">
                {change_str}
                <span class="font-medium">{weight} kg</span>
            </div>
        </div>'''

    return html


def generate_recent_workouts(workouts):
    """Generate recent workouts list."""
    html = ""
    for w in workouts:
        types_str = ", ".join(w['types']) if w['types'] else "Workout"
        date = datetime.strptime(w['date'][:10], '%Y-%m-%d').strftime('%a %d %b')
        duration = f"{w['duration']} min" if w['duration'] else ""

        html += f'''<div class="flex items-center justify-between p-3 bg-white/5 rounded-xl">
            <div>
                <div class="font-medium">{w['name'] or types_str}</div>
                <div class="text-sm text-gray-400">{date}</div>
            </div>
            <div class="text-right">
                <div class="text-blue-400">{duration}</div>
                <div class="text-xs text-gray-500">{types_str}</div>
            </div>
        </div>'''

    return html


def generate_weight_card(weight, change):
    """Generate weight card if data available."""
    if not weight:
        return ""

    change_str = ""
    change_color = "text-gray-400"
    if change:
        if change < 0:
            change_str = f"↓ {abs(change)} kg"
            change_color = "text-green-400"
        else:
            change_str = f"↑ {change} kg"
            change_color = "text-red-400"

    return f'''
        <div class="glass rounded-2xl p-6 mt-6">
            <h2 class="text-xl font-semibold mb-2">Weight</h2>
            <div class="flex items-end gap-4">
                <div class="text-4xl font-bold">{weight} kg</div>
                <div class="{change_color}">{change_str}</div>
            </div>
        </div>
    '''


def main():
    init_db()

    print("Fetching exercise data from database...")
    exercises = fetch_all_exercises()
    print(f"Found {len(exercises)} exercises")

    print("Fetching weight data from database...")
    weights = fetch_weight_entries()
    print(f"Found {len(weights)} weight entries")

    print("Generating dashboard...")
    html = generate_dashboard(exercises, weights)

    output_path = os.path.join(os.path.dirname(__file__), 'dashboard.html')
    with open(output_path, 'w') as f:
        f.write(html)

    print(f"Dashboard saved to: {output_path}")


if __name__ == "__main__":
    main()
