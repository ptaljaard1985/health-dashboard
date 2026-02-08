# Health Coach Telegram Bot - Specification

## Overview
Daily Telegram notification sent at 8pm summarising health progress and providing actionable guidance for the next day.

---

## Goals & Targets

### Weekly Targets (Rolling 7 Days)
**Definition:** Today + 6 days before. Always exactly 7 days.
Example: If today is Feb 8, "last 7 days" = Feb 2-8.

| Metric | Target | Grace |
|--------|--------|-------|
| Cardio activities | 4 | 3 acceptable |
| Strength activities (Kettlebells) | 3 | 2 acceptable |

### Monthly Targets (Calendar Month)
| Metric | Target | Grace |
|--------|--------|-------|
| Cardio activities | 16 | 1 behind pace |
| Strength activities | 10 | 1 behind pace |

### Other Thresholds
| Metric | Alert Threshold |
|--------|-----------------|
| Consecutive rest days | 2+ (warning), 3+ (urgent) |
| Days since weigh-in | 3+ days |

---

## Message Structure

### Header
```
📊 Feb Day 5
```
Shows current month and day number.

### Section 1: Weekly Progress (Last 7 Days)
```
This week:
🏃 Cardio: 3/4 ✓
🏋️ Strength: 1/3 ⚠️
```
- ✓ = on target or within grace
- ⚠️ = below target

### Section 2: Monthly Progress (Calendar Month)
```
February:
🏃 Cardio: 5/16 ✓
🏋️ Strength: 2/10 ⚠️
```
- Compares against pro-rata expected pace
- ✓ = on pace (within 1 session grace)
- ⚠️ = behind pace

### Section 3: Pace Alerts (Only if Behind)
```
Need 2.5 strength/week to hit monthly goal
```
- Only shown if behind on monthly pace
- Calculates sessions per week needed for remaining days

### Section 4: Rest Day Warning (Only if 2+ Days)
```
😴 2 rest days in a row
```
or (if 3+):
```
😴 **3 rest days in a row**
```
Bold formatting for urgency at 3+ days.

### Section 5: Weight Status
**If weighed in recently (< 3 days):**
```
⚖️ 91.2 kg (↓ 0.4 kg this week)
```
Shows current weight and 7-day trend.

**If no weigh-in for 3+ days:**
```
⚖️ **No weigh-in for 4 days**
```
Bold reminder to weigh in.

### Section 6: Tomorrow Suggestion
```
Tomorrow:
→ [suggestion based on logic below]
```

---

## Tomorrow Suggestion Logic

Priority order (first matching condition wins):

| Priority | Condition | Suggestion |
|----------|-----------|------------|
| 1 | 3+ consecutive rest days | "Get moving today. Even a 20min walk counts." |
| 2 | 2 consecutive rest days | "Time to move. Light cardio or kettlebells." |
| 3 | Weekly strength < 2 AND no strength in last 2 days | "Kettlebells - you're behind this week" |
| 4 | Weekly cardio < 3 AND no cardio in last 2 days | "Cardio session - you're behind this week" |
| 5 | Monthly strength behind pace | "Kettlebells session" |
| 6 | Monthly cardio behind pace | "MAF cardio (walk, run, or cycle)" |
| 7 | No strength in last 3 days | "Kettlebells (none in last 3 days)" |
| 8 | No cardio in last 3 days | "Easy cardio for recovery" |
| 9 | All targets met | "On track. Rest or light movement." |

---

## Example Messages

### Example 1: On Track
```
📊 Feb Day 12

This week:
🏃 Cardio: 4/4 ✓
🏋️ Strength: 3/3 ✓

February:
🏃 Cardio: 8/16 ✓
🏋️ Strength: 5/10 ✓

⚖️ 90.8 kg (↓ 0.6 kg this week)

Tomorrow:
→ On track. Rest or light movement.
```

### Example 2: Behind on Strength
```
📊 Feb Day 8

This week:
🏃 Cardio: 3/4 ✓
🏋️ Strength: 1/3 ⚠️

February:
🏃 Cardio: 5/16 ✓
🏋️ Strength: 2/10 ⚠️

Need 2.7 strength/week to hit monthly goal

⚖️ 91.2 kg (↓ 0.3 kg this week)

Tomorrow:
→ Kettlebells - you're behind this week
```

### Example 3: Rest Day Warning + No Weigh-in
```
📊 Feb Day 15

This week:
🏃 Cardio: 2/4 ⚠️
🏋️ Strength: 2/3 ✓

February:
🏃 Cardio: 7/16 ⚠️
🏋️ Strength: 5/10 ✓

Need 4.5 cardio/week to hit monthly goal

😴 **3 rest days in a row**

⚖️ **No weigh-in for 5 days**

Tomorrow:
→ Get moving today. Even a 20min walk counts.
```

---

## Activity Type Definitions

### Cardio Types
- Run
- Trail Run
- Walk
- Hike
- Rucking
- Indoor Cycle
- Tennis
- Padel
- Golf

### Strength Types
- Kettlebells

---

## Technical Details

### Data Sources
- **Notion Database**: Exercise entries with Date, Type (multi-select), Weight (kg)
- **Filters**:
  - Exercises: Type does not contain "Weigh-in"
  - Weights: Type contains "Weigh-in"

### Schedule
- **Time**: 8:00 PM daily
- **Method**: macOS launchd (com.health.notifications.plist)

### Telegram API
- **Bot Token**: Stored in .env as TELEGRAM_BOT_TOKEN
- **Chat ID**: Stored in .env as TELEGRAM_CHAT_ID
- **Parse Mode**: HTML (for bold formatting)

---

## Configuration

```python
# Weekly targets
WEEKLY_CARDIO_GOAL = 4
WEEKLY_STRENGTH_GOAL = 3

# Monthly targets
MONTHLY_CARDIO_GOAL = 16
MONTHLY_STRENGTH_GOAL = 10

# Alert thresholds
REST_DAY_WARNING = 2
REST_DAY_URGENT = 3
WEIGHIN_REMINDER_DAYS = 3
```

---

## Future Enhancements (Not Implemented)
- Morning reminder option (7am)
- Reply commands (/status, /week, /month)
- Streak celebrations (7-day, 30-day)
- Weekly summary on Sundays
- Integration with weight goal countdown
