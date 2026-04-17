# Technical Overview: Daily Tracker (The Canvas)

## Overview
"The Canvas" is a high-performance, aesthetically-driven personal productivity and time-tracking application. It provides a dual-mode workflow: a **Live Session Tracker** for monitoring active work duration (weekly/monthly goals) and a **Habit Checklist** for managing recurring routines and one-time deadlines. The application features a rich, interactive dashboard with real-time visual analytics, including a circular donut breakdown for daily focus and historical activity heatmaps. Designed with a "Signal/Noise" philosophy, it prioritizes a premium, distraction-free user experience. The system is architecture-agnostic, supporting local-first deployments via SQLite and enterprise-scale cloud hosting via PostgreSQL and Supabase.

## Features
- **Project-Based Timing**: Direct start/stop timer functionality with persistent state recovery across browser sessions.
- **Dynamic Donut Charts**: Real-time visualization of daily time distribution by task color, featuring centered summary metrics.
- **Manual Logging**: Simplified manual entry of minutes for tasks, optimized for rapid data entry by removing redundant time-range selectors.
- **Habit Recurrence Patterns**: Automated tracking for Daily, Weekly, Monthly, and One-time tasks with intelligent period management.
- **Consolidated Task Management**: Unified "Add Task" forms with inline editing and show/hide toggles for advanced configurations.
- **Logical Day Offsets**: Customizable "Day Start" hour (e.g., 2 AM) to ensure late-night sessions are logged to the correct logical date.
- **Multi-Tenant Database Design**: Scoped data access using `owner_id` for user isolation, compatible with cloud authentication.
- **Aesthetic Excellence**: A premium dark luxury theme using Space Grotesk and DM Mono typography with subtle micro-animations.

## Relevant Files
```text
.
├── app.py                  # Backend engine: API endpoints, Database migrations, and Auth middleware.
├── index.html              # Frontend core: Single-file SPA containing all styles (CSS), layout, and JS logic.
├── requirements.txt        # Backend dependencies (Flask, PyJWT, psycopg2).
├── api/
│   └── index.py            # Vercel serverless entry point.
├── user_data.db            # Default local persistence layer (SQLite).
├── .env                    # Runtime configuration for Postgres and Supabase (Secret).
└── stitch_the_canvas/      # Design assets and UI mockups.
```

## Basic Information
- **Programming Languages**: 
  - **Python**: ~2,000 lines (Backend API, Schema Management, Auth).
  - **JavaScript**: ~3,800 lines (State management, Real-time rendering, Timer logic).
  - **CSS3**: ~1,500 lines (Embedded "Signal/Noise" design system).
- **Services Used**:
  - **Supabase**: Primary cloud provider for PostgreSQL and JWT-based authentication.
  - **Vercel**: Deployment target for serverless execution.
- **Tech Stack**:
  - **Backend**: Flask, PyJWT, psycopg2-binary, sqlite3.
  - **Frontend**: Vanilla ES6+ JavaScript, CSS Grid/Flexbox, HTML5.
- **How to Run**:
  1. Install environment: `pip install -r requirements.txt`
  2. Set `.env` variables if using cloud storage.
  3. Start application: `python app.py` (Local address: `http://localhost:5005`).

## Files & Interactions

### `app.py`
The backend acts as the authoritative source of truth and persistence controller:
- **Database Abstraction**: Implements a wrapper pattern (`PostgresDbWrapper`) to allow business logic to remain agnostic of the underlying driver (SQLite vs Postgres).
- **Authentication**: Gatekeeps API access via Supabase JWT verification. It includes a `DISABLE_SIGN_IN` development flag to bypass auth during local prototyping.
- **Timer Management**: Persists active timer start times. It calculates logical durations on-the-fly to ensure accuracy even if the server restarts.
- **Aggregation Engine**: Performs complex SQL joins across `work_logs`, `tasks`, and `daily_task_completions` to provide data for the frontend's visual charts.

### `index.html`
The frontend is a self-contained application layer responsible for the entire user interaction cycle:
- **Design System**: A comprehensive CSS-variable based system that defines the visual language (Surface Scale, Accent Glows, Motion Easing). 
- **State Management**: Maintains a local replica of the `tasks` and `daily_tasks` objects, enabling optimistic UI updates for a snappy experience.
- **Dynamic Charting**: Uses native CSS and JavaScript to render the daily Donut Chart (`conic-gradient`), weekly activity bars, and monthly calendar heatmaps.
- **Timer Ticking**: Orchestrates the client-side `setInterval` loop that provides second-by-second updates to the UI, syncing increments to the server only on Stop or at regular intervals.

### `api/index.py`
Exposes the Flask instance specifically for Vercel's serverless runtime requirements.

---

## Security Vulnerabilities & Bug Reports

🔴 **Very dangerous and urgent bug/security problem**
- **Hardcoded Auth Bypass**: The `DISABLE_SIGN_IN = True` flag is hardcoded in `app.py`. If deployed in this state, any user can bypass authentication entirely and access the `local_dev_user` data, or potentially other users' data if the ID is guessed. This should be moved to an environment variable.

🟠 **Slightly dangerous and urgent bug/security problem**
- **Update Race Condition**: The `update_work_log` and `delete_work_log` endpoints calculate the new `elapsed_seconds` in Python before sending it to the database. In a multi-session environment, this could lead to data loss or inconsistent totals if multiple updates occur simultaneously for the same task.
- **Missing CSRF Protection**: While Bearer tokens provide some protection, there is no explicit CSRF middleware for the session-based or local-dev flows, which could pose a risk if authentication methods change.

🟡 **Bugs that should be fixed, but not urgently**
- **SQLite Parameter Limit**: The `get_daily_tasks` query uses `IN (?)` with a list of IDs generated from all daily tasks. If a user accumulates more than 999 daily tasks, the query will crash in SQLite due to the parameter limit.
- **Hardcoded Fallbacks**: Several JS functions in `index.html` (e.g., `updateTodayCircle`) used hardcoded hex colors (#e9ecef) instead of CSS variables, leading to theme inconsistencies in specific empty states. (Partial fix implemented).

🟢 **Small bugs / security problems (niche situations)**
- **SQL Data Type Mismatch**: Some schema migrations use `INTEGER` for timestamps in SQLite but `BIGINT` in Postgres. While functional, it could lead to precision issues or range errors in specific extreme edge cases.
- **Frontend State Overflow**: Long task names or category strings are truncated on the backend but may cause layout shifting in the frontend if not strictly handled by CSS `text-overflow`.
