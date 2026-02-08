#!/usr/bin/env python3
"""
Garmin Connect Sync Script
===========================
Syncs activities and weight data from Garmin Connect to the local SQLite database.

Author: Pierre (SimpleWealth)
Created: February 2026
"""

import os
import sys
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from garminconnect import Garmin
from db import init_db, get_connection

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('garmin_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Garmin Configuration
GARMIN_EMAIL = os.getenv('GARMIN_EMAIL')
GARMIN_PASSWORD = os.getenv('GARMIN_PASSWORD')

# Sync Settings
DAYS_TO_SYNC = int(os.getenv('DAYS_TO_SYNC', '7'))  # How many days back to sync

# =============================================================================
# ACTIVITY TYPE MAPPING
# =============================================================================
# Maps Garmin activity types to tracked activity types

GARMIN_TO_TYPE = {
    # Running
    'running': 'Run',
    'trail_running': 'Trail Run',
    'treadmill_running': 'Run',

    # Walking & Hiking
    'walking': 'Walk',
    'hiking': 'Hike',
    'casual_walking': 'Walk',

    # Cycling
    'cycling': 'Indoor Cycle',  # Adjust if you add outdoor cycling
    'indoor_cycling': 'Indoor Cycle',
    'virtual_ride': 'Indoor Cycle',

    # Strength
    'strength_training': 'Kettlebells',
    'cardio': 'Kettlebells',  # Often used for KB workouts

    # Racquet Sports
    'tennis': 'Tennis',
    'tennis_v2': 'Tennis',
    'padel': 'Padel',
    'paddelball': 'Padel',
    'racquet_ball': 'Padel',

    # Golf
    'golf': 'Golf',

    # Other cardio that maps to rucking (weighted walks)
    'other': 'Walk',  # Default fallback
}

# Activity types to skip (not relevant to your tracking)
SKIP_ACTIVITY_TYPES = [
    'sleep',
    'uncategorized',
]


# =============================================================================
# GARMIN CLIENT
# =============================================================================

class GarminClient:
    """Handles Garmin Connect API interactions."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.client = None

    def connect(self) -> bool:
        """Authenticate with Garmin Connect."""
        try:
            self.client = Garmin(self.email, self.password)
            self.client.login()
            logger.info("Successfully connected to Garmin Connect")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Garmin: {e}")
            return False

    def get_activities(self, days: int = 7) -> list:
        """Fetch activities from the last N days."""
        if not self.client:
            logger.error("Not connected to Garmin")
            return []

        try:
            # Get activities (returns most recent first)
            activities = self.client.get_activities(0, 100)  # Last 100 activities

            # Filter to last N days
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_activities = []

            for activity in activities:
                activity_date = datetime.strptime(
                    activity['startTimeLocal'][:10], '%Y-%m-%d'
                )
                if activity_date >= cutoff_date:
                    recent_activities.append(activity)

            logger.info(f"Found {len(recent_activities)} activities in last {days} days")
            return recent_activities

        except Exception as e:
            logger.error(f"Failed to fetch activities: {e}")
            return []

    def get_weight_data(self, days: int = 7) -> list:
        """Fetch weight measurements from the last N days."""
        if not self.client:
            logger.error("Not connected to Garmin")
            return []

        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            weight_data = self.client.get_body_composition(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )

            # Extract daily weight entries
            weights = []
            if weight_data and 'dateWeightList' in weight_data:
                for entry in weight_data['dateWeightList']:
                    if entry.get('weight'):
                        weights.append({
                            'date': entry['calendarDate'],
                            'weight_kg': round(entry['weight'] / 1000, 2),  # Convert grams to kg
                        })

            logger.info(f"Found {len(weights)} weight entries in last {days} days")
            return weights

        except Exception as e:
            logger.error(f"Failed to fetch weight data: {e}")
            return []


# =============================================================================
# DATABASE OPERATIONS
# =============================================================================

def get_existing_garmin_ids() -> set:
    """Get all Garmin Activity IDs already in the database."""
    conn = get_connection()
    rows = conn.execute("SELECT garmin_activity_id FROM activities WHERE garmin_activity_id IS NOT NULL").fetchall()
    conn.close()
    ids = {row['garmin_activity_id'] for row in rows}
    logger.info(f"Found {len(ids)} existing Garmin entries in database")
    return ids


def get_existing_weight_dates() -> set:
    """Get all dates that already have weight entries."""
    conn = get_connection()
    rows = conn.execute("SELECT date FROM weigh_ins").fetchall()
    conn.close()
    dates = {row['date'] for row in rows}
    logger.info(f"Found {len(dates)} existing weight entries in database")
    return dates


def create_activity_entry(activity: dict, activity_type: str) -> bool:
    """Create a new activity entry in the database."""
    try:
        activity_id = str(activity['activityId'])
        activity_name = activity.get('activityName', activity_type)
        activity_date = activity['startTimeLocal'][:10]  # YYYY-MM-DD

        duration = None
        if activity.get('duration'):
            duration = round(activity['duration'] / 60, 1)  # seconds → minutes

        distance = None
        if activity.get('distance'):
            distance = round(activity['distance'] / 1000, 2)  # meters → km

        calories = activity.get('calories')
        avg_hr = activity.get('averageHR')
        max_hr = activity.get('maxHR')
        notes = activity.get('description', '')[:2000] if activity.get('description') else None

        conn = get_connection()
        conn.execute(
            """INSERT OR IGNORE INTO activities
               (exercise, date, type, garmin_activity_id, duration, distance,
                calories, avg_heart_rate, max_heart_rate, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (activity_name, activity_date, activity_type, activity_id,
             duration, distance, calories, avg_hr, max_hr, notes)
        )
        conn.commit()
        conn.close()

        logger.info(f"Created activity: {activity_name} ({activity_date})")
        return True

    except Exception as e:
        logger.error(f"Failed to create activity entry: {e}")
        return False


def create_weight_entry(weight_data: dict) -> bool:
    """Create a new weight entry in the database."""
    try:
        date = weight_data['date']
        weight_kg = weight_data['weight_kg']

        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO weigh_ins (date, weight_kg) VALUES (?, ?)",
            (date, weight_kg)
        )
        conn.commit()
        conn.close()

        logger.info(f"Created weight entry: {weight_kg} kg ({date})")
        return True

    except Exception as e:
        logger.error(f"Failed to create weight entry: {e}")
        return False


# =============================================================================
# MAIN SYNC FUNCTION
# =============================================================================

def sync_garmin():
    """Main function to sync Garmin data to the local database."""

    logger.info("=" * 60)
    logger.info("Starting Garmin sync")
    logger.info("=" * 60)

    # Validate configuration
    if not all([GARMIN_EMAIL, GARMIN_PASSWORD]):
        logger.error("Missing required environment variables. Check your .env file.")
        logger.error("Required: GARMIN_EMAIL, GARMIN_PASSWORD")
        sys.exit(1)

    # Initialise database
    init_db()

    # Connect to Garmin
    garmin = GarminClient(GARMIN_EMAIL, GARMIN_PASSWORD)
    if not garmin.connect():
        logger.error("Failed to connect to Garmin. Exiting.")
        sys.exit(1)

    # Get existing entries to avoid duplicates
    existing_garmin_ids = get_existing_garmin_ids()
    existing_weight_dates = get_existing_weight_dates()

    # Sync activities
    activities = garmin.get_activities(DAYS_TO_SYNC)
    activities_created = 0
    activities_skipped = 0

    for activity in activities:
        activity_id = str(activity['activityId'])

        # Skip if already synced
        if activity_id in existing_garmin_ids:
            activities_skipped += 1
            continue

        # Get activity type
        garmin_type = activity.get('activityType', {}).get('typeKey', 'other').lower()

        # Skip unwanted activity types
        if garmin_type in SKIP_ACTIVITY_TYPES:
            continue

        # Map to tracked type
        activity_type = GARMIN_TO_TYPE.get(garmin_type, 'Walk')

        # Log unknown activity types for mapping updates
        if garmin_type not in GARMIN_TO_TYPE:
            logger.warning(f"Unknown activity type: {garmin_type} - mapping to '{activity_type}'")

        # Create entry
        if create_activity_entry(activity, activity_type):
            activities_created += 1

    # Sync weight data
    weight_entries = garmin.get_weight_data(DAYS_TO_SYNC)
    weights_created = 0
    weights_skipped = 0

    for weight in weight_entries:
        date = weight['date']

        # Skip if already have weight for this date
        if date in existing_weight_dates:
            weights_skipped += 1
            continue

        if create_weight_entry(weight):
            weights_created += 1

    # Summary
    logger.info("=" * 60)
    logger.info("Sync complete!")
    logger.info(f"Activities: {activities_created} created, {activities_skipped} already existed")
    logger.info(f"Weight entries: {weights_created} created, {weights_skipped} already existed")
    logger.info("=" * 60)

    return {
        'activities_created': activities_created,
        'activities_skipped': activities_skipped,
        'weights_created': weights_created,
        'weights_skipped': weights_skipped,
    }


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    sync_garmin()
