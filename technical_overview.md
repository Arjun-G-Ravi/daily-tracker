# Technical Overview: Daily Tracker (The Canvas)

## Overview
Daily Tracker, referred to internally as "The Canvas," is a comprehensive productivity application designed for meticulous time and task management. It provides a dual tracking system: a timer-based module for monitoring duration-specific activities (weekly/monthly goals) and a checklist-style module for recurring habits and one-time tasks. The application features a rich, interactive dashboard with real-time analytics, including bar charts for weekly/monthly trends and a heatmap-style calendar for activity history. Designed to be lightweight yet powerful, it supports multi-user environments via Supabase authentication and offers flexible persistence layers spanning local SQLite databases to cloud-hosted PostgreSQL instances.

## Features
- **Project-Based Timing**: Create reusable weekly or monthly tasks with active start/stop timers.
- **Manual Time Entry**: Log time sessions manually or by specifying "From/To" ranges for past activities.
- **Daily habit Tracking**: Manage task lists with various recurrence patterns: Daily, Weekly, Monthly, and One-time.
- **Goal-Oriented Tasks**: Support for both binary "Checkbox" completion and "Integer" target tracking (e.g., "60 minutes of reading").
- **Dynamic Analytics**: Visualizations including weekly stacked bar charts, 6-month historical overviews, and monthly activity heatmaps.
- **Micro-Management Settings**: Customizable "Logical Day" start hour (e.g., 2 AM) to accommodate late-night productivity, and adjustable week start days.
- **Dual Database Support**: Seamlessly switches between local SQLite for development and PostgreSQL/Supabase for production/Vercel deployments.
- **Authentication**: Secure user isolation using Supabase JWT-based authentication.

## Relevant Files
```text
.
├── app.py              # Main Flask application (API + Static Serving)
├── index.html          # Single-Page Application (Frontend logic + Styles)
├── vercel.json         # Vercel deployment configuration
├── requirements.txt    # Python dependencies
├── user_data.db        # Core SQLite database (default)
└── weekly_tracker.db   # Legacy database for bootstrapping (optional)
```

## Basic Information
- **Programming Languages**: 
  - **Python**: ~2,000 lines (Backend API, Database Migrations, Auth logic)
  - **JavaScript**: ~3,500 lines (Frontend logic, Chart rendering, State management)
  - **HTML/CSS**: Embedded within `index.html` (~1,200 lines of styling)
- **Services Used**:
  - **Supabase**: Used for multi-user authentication (JWT) and persistent PostgreSQL storage.
  - **Vercel**: Recommended hosting platform with serverless function support.
- **Tech Stack**:
  - **Core**: Python 3.x, Flask.
  - **Database**: SQLite, PostgreSQL (`psycopg2-binary`).
  - **Security**: `PyJWT` for authentication verification.
  - **Frontend**: Vanilla JavaScript (ES6+), CSS3 Flexbox/Grid, SVG for icons.
- **How to Run**:
  1. Install dependencies: `pip install -r requirements.txt`
  2. (Optional) Set environment variables in `.env` for Supabase/Postgres.
  3. Start the server: `python app.py`
  4. Access via `http://localhost:5000`

## Files & Interactions
- **`app.py`**: The central nervous system of the application. It handles:
  - **Database Lifecycle**: Initializes either SQLite or Postgres schemas and manages migrations.
  - **Authentication Middleware**: Verifies Supabase JWT tokens on every request to `/api/` paths (except health checks).
  - **Timer Logic**: Real-time calculation of elapsed time for running tasks, ensuring accuracy even across server restarts by combining persisted "elapsed_seconds" with "started_at" timestamps.
  - **Analytics Engine**: Computes complex aggregations for the weekly breakdown, monthly overview, and calendar heatmaps.
  - **Task Management**: CRUD operations for both `tasks` (timer-based) and `daily_tasks` (recurrence-based).

- **`index.html`**: A massive, self-contained frontend that orchestrates the user experience.
  - **State Management**: Uses a robust client-side state object to manage tasks, completions, and UI settings locally before syncing with the API.
  - **Timer Sync**: Implements a `setInterval` ticker (`tickRunningTimers`) to provide visual real-time updates and incremental analytics updates without frequent polling.
  - **Component Rendering**: Dynamically generates UI elements for task lists, settings, and modal logs using template literals and DOM manipulation.
  - **Charts & Visuals**: Renders custom bar charts and calendar grids using optimized CSS-based layouts (no heavy graphing libraries needed).

- **Database Interaction**:
  - The `app.py` script uses a wrapper pattern (`PostgresDbWrapper`) to allow the core logic to interact with both SQLite and PostgreSQL using a unified interface. 
  - The frontend (`index.html`) communicates with `app.py` via a centralized `apiRequest` function that handles the inclusion of bearer tokens and error management.
  - Changes in timers or habit completions are immediately reflected in the local state for a snappy UI, with server-side mutations queued or enqueued for eventual consistency.
