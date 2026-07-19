# Endurolytics — Project Planning Document

## Overview

Endurolytics is a personal endurance training analytics platform designed to analyze long-course triathlon training progression over time.

The goal is not to replace Garmin Connect or TrainingPeaks, but to provide a deeper view into:

* Training load progression
* 3:1 training blocks
* Fitness vs fatigue
* Sport-specific volume
* Long-term Ironman preparation
* Performance trends

The primary question Endurolytics should answer:

> "Am I training appropriately and progressing toward my endurance goals?"

---

# High-Level Architecture

Endurolytics will consist of two separate processes:

## 1. Data Pipeline

Responsible for:

* Pulling Garmin Connect data
* Filtering relevant activities
* Processing activities
* Calculating training metrics
* Storing results in PostgreSQL

Runs automatically using GitHub Actions.

## 2. Dashboard Application

Responsible for:

* Reading processed data
* Visualizing trends
* Providing analytics views

Runs as a Dash application hosted on Render.

Architecture:

```
Garmin Connect
      |
      v
GitHub Actions Scheduled Pipeline
      |
      v
Activity Processing
      |
      v
PostgreSQL Database
      |
      v
Dash Application (Render)
      |
      v
User Dashboard
```

---

# Repository Structure

Use a single repository.

Repository:

```
endurolytics/
```

Structure:

```
endurolytics/

├── app/
│   ├── app.py
│   ├── server.py
│   │
│   ├── pages/
│   │   ├── overview.py
│   │   ├── weekly.py
│   │   ├── activities.py
│   │   ├── training_load.py
│   │   ├── performance.py
│   │   └── settings.py
│   │
│   ├── callbacks/
│   ├── components/
│   └── assets/
│
├── pipeline/
│   ├── sync_garmin.py
│   ├── filter_activities.py
│   └── process_activities.py
│
├── analytics/
│   ├── tss.py
│   ├── ctl.py
│   ├── atl.py
│   ├── tsb.py
│   └── weekly.py
│
├── database/
│   ├── models.py
│   ├── connection.py
│   └── migrations/
│
├── tests/
│
├── .github/
│   └── workflows/
│       └── garmin_sync.yml
│
├── requirements.txt
├── Dockerfile
├── render.yaml
└── README.md
```

---

# Technology Stack

## Frontend

* Dash
* Plotly
* Python

## Backend Database

* PostgreSQL
* Hosted on Neon free tier

## Data Pipeline

* GitHub Actions
* python-garminconnect

## ORM

* SQLAlchemy

## Database Migrations

* Alembic

---

# Data Pipeline

## Goal

Automatically update Endurolytics data without requiring a local computer.

Pipeline schedule:

Example:

```
Every 3 hours:

1. Authenticate with Garmin Connect
2. Pull recent activities
3. Identify new activities
4. Process activity data
5. Calculate training metrics
6. Update PostgreSQL
```

---

# Garmin Import

Use:

`python-garminconnect`

The importer should:

* Pull activity history
* Store Garmin activity ID
* Avoid duplicate imports
* Support incremental updates

Activity ID is the unique identifier.

Logic:

```
Pull Garmin activities

For each activity:

    If activity_id exists:
        update

    Else:
        insert
```

---

# Activity Filtering

Only include endurance activities.

## Include

### Run

* Running
* Trail running
* Treadmill running

### Bike

* Cycling
* Indoor cycling
* Virtual cycling
* Gravel cycling

### Swim

* Pool swimming
* Open water swimming

## Exclude initially

* Walking
* Strength
* Yoga
* Cardio
* Other activities

---

# Database Design

## Raw Activity Storage

Keep raw Garmin data.

Table:

`activity_raw`

Fields:

```
activity_id
garmin_json
import_timestamp
```

Purpose:

* Preserve source data
* Allow future reprocessing
* Debug import issues

---

# Processed Activity Table

`activities`

Fields:

```
activity_id

date
activity_name

sport
subsport

duration_seconds
distance

avg_hr
max_hr

avg_power
normalized_power

pace

elevation_gain
```

---

# Activity Metrics Table

`activity_metrics`

Calculated values:

```
activity_id

tss

intensity_factor

bike_tss
run_tss
swim_tss

zone_distribution
```

---

# Weekly Training Table

Primary table for dashboard analytics.

`weekly_training`

Fields:

```
week_start

total_tss
bike_tss
run_tss
swim_tss

total_hours

bike_hours
run_hours
swim_hours

bike_distance
run_distance
swim_distance

ctl
atl
tsb

longest_run
longest_bike
longest_swim
```

---

# Training Load Calculations

Calculate within the analytics layer.

Do not calculate inside Dash.

---

## Bike TSS

Use power-based TSS.

Inputs:

* FTP
* Normalized Power
* Duration

---

## Run TSS

Use threshold pace.

Inputs:

* Running threshold pace
* Activity pace
* Duration

---

## Swim TSS

Use CSS-based calculations.

Inputs:

* Critical Swim Speed
* Pace
* Duration

---

# Dashboard Pages

## Overview

Purpose:

Quick status check.

Display:

* Current CTL
* ATL
* TSB
* Weekly TSS
* Training hours
* Recovery metrics

---

# Weekly View

Primary training review page.

Example:

```
Week 28

Bike
- Miles
- Hours
- TSS

Run
- Miles
- Hours
- TSS

Swim
- Yards
- Hours
- TSS

Total
- Hours
- TSS
```

Include:

* Daily workout calendar
* Goal vs actual comparison

---

# Training Blocks

Support 3:1 training cycles.

Example:

```
Block 12

Week 1
Build

Week 2
Build

Week 3
Build

Week 4
Recovery
```

Track:

* Starting CTL
* Ending CTL
* Total TSS
* Total hours
* Volume changes

---

# Activities Page

Purpose:

Detailed workout history.

Features:

* Chronological activity list
* Sorting
* Filtering

Filters:

* All
* Swim
* Bike
* Run

Columns:

```
Date
Activity Name
Sport
Duration
Distance
TSS
Intensity Factor
Heart Rate
Power
Pace
```

---

# Performance Page

Track improvements.

Metrics:

## Bike

* FTP
* Power curve
* Long ride power

## Run

* Threshold pace
* Race predictions
* Pace trends

## Swim

* CSS
* Pace per 100 yards
* Long swim pace

---

# Deployment

## Render

Hosts:

* Dash application

Reads:

* PostgreSQL database

---

## Neon PostgreSQL

Stores:

* Activities
* Metrics
* Weekly summaries
* Athlete settings

---

## GitHub Actions

Runs:

* Garmin synchronization
* Database updates

---

# Development Principles

## Separate concerns

The dashboard should:

* Read data
* Display insights

The pipeline should:

* Pull data
* Transform data
* Calculate metrics
* Update database

---

## Avoid duplicated logic

All calculations should exist in:

```
analytics/
```

Example:

Bad:

```
Dash calculates CTL
Pipeline calculates CTL
```

Good:

```
analytics/ctl.py
```

Both use the same implementation.

---

# Future Features

Potential additions:

* Race countdown
* Training plan comparison
* Goal setting
* Fatigue alerts
* HRV integration
* Nutrition tracking
* Fueling analysis
* Race simulations
* Predictive performance models

---

# Initial MVP

Build order:

1. PostgreSQL setup
2. Garmin importer
3. Activity database
4. TSS calculations
5. Weekly aggregation
6. Activities page
7. Weekly training page
8. Training load charts
9. Automated GitHub Action sync
10. Deploy Dash app

```
```
