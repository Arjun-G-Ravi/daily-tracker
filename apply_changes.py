import re

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Update <head> with Google Fonts
fonts = """    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap" rel="stylesheet">\n"""
if "fonts.googleapis.com" not in html:
    html = html.replace('<title>🖼️ The Canvas</title>', f'<title>🖼️ The Canvas</title>\n{fonts}')

# 2. Replace CSS completely
with open('styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

html = re.sub(r'<style>.*?</style>', f'<style>\n{css}\n    </style>', html, flags=re.DOTALL)

# 3. Rewrite HTML structure
old_sidebar_str = """    <div class="container" id="appRoot" style="display:none;">
        <div class="dashboard-layout">
            <div class="left-panel">
                <div class="header">
                    <div>
                        <h1>The Canvas</h1>
                        <div class="current-day-label" id="currentDayLabel">Current Day: --</div>
                    </div>
                    <div class="header-right">
                        <div class="app-user-row" id="appUserRow" style="display:none;">
                            <button type="button" class="app-sync-btn" id="appSyncBtn" title="Syncing with database"
                                onclick="manualSyncNow()">🔴</button>
                            <span class="app-user-email" id="appUserEmail">Signed in</span>
                            <button type="button" class="app-signout-btn" onclick="handleSignOut()">Sign out</button>
                        </div>
                        <div class="today-circle" id="todayCircle">
                            <div class="today-circle-inner">
                                <div class="today-label">Today Total</div>
                                <div class="today-value" id="todayTotal">00:00:00</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="tabs">
                    <button id="tabBtnWeekly" class="tab-button active"
                        onclick="switchTab('weekly', this)">Weekly</button>
                    <button id="tabBtnMonthly" class="tab-button" onclick="switchTab('monthly', this)">Monthly</button>
                    <button id="tabBtnTasks" class="tab-button" onclick="switchTab('tasks', this)">Tasks</button>
                    <button id="tabBtnSettings" class="tab-button"
                        onclick="switchTab('settings', this)">Settings</button>
                </div>"""

new_sidebar_str = """    <div class="app-shell" id="appRoot" style="display:none;">
        <div class="sidebar">
            <div class="sidebar-header">
                <h1>The Canvas</h1>
                <div class="current-day-label" id="currentDayLabel">Current Day: --</div>
            </div>
            
            <div class="sidebar-nav">
                <button id="tabBtnWeekly" class="sidebar-nav-item active" onclick="switchTab('weekly', this)">Dashboard</button>
                <button id="tabBtnMonthly" class="sidebar-nav-item" onclick="switchTab('monthly', this)">Monthly</button>
                <button id="tabBtnTasks" class="sidebar-nav-item" onclick="switchTab('tasks', this)">Tasks</button>
                <button id="tabBtnSettings" class="sidebar-nav-item" onclick="switchTab('settings', this)">Settings</button>
            </div>
            
            <div class="sidebar-footer">
                <div class="today-circle" id="todayCircle">
                    <div class="today-label">Today Total</div>
                    <div class="today-value" id="todayTotal">00:00:00</div>
                </div>
                
                <div class="app-user-row" id="appUserRow" style="display:none;">
                    <button type="button" class="app-sync-btn" id="appSyncBtn" title="Syncing with database" onclick="manualSyncNow()">🔴</button>
                    <span class="app-user-email" id="appUserEmail">Signed in</span>
                    <button type="button" class="app-signout-btn" onclick="handleSignOut()">Sign out</button>
                </div>
            </div>
        </div>
        <div class="main-content">"""

html = html.replace(old_sidebar_str, new_sidebar_str)

# 4. Integrate Right Panel into Weekly Tab
old_weekly_start = """                <div id="weekly" class="tab-content active">
                    <ul class="tasks" id="weeklyTaskList"></ul>
                </div>"""

new_weekly_wrapper = """                <div id="weekly" class="tab-content active">
                    <div class="weekly-layout">
                        <ul class="tasks" id="weeklyTaskList"></ul>
                        
                        <!-- Right Panel moved here -->
                        <div class="right-panel" id="weeklyRightPanel">
                            <div class="chart-title" id="weeklyChartTitle">This Week</div>
                            <div class="chart-outer">
                                <div class="chart-y-axis" id="chartYAxis"></div>
                                <div class="chart-body">
                                    <div class="chart-bars-area" id="weeklyChart"></div>
                                    <div class="chart-labels-row" id="chartLabelsRow"></div>
                                </div>
                            </div>
                            <div class="daily-tasks-panel" id="weeklyTasksPanel">
                                <div class="daily-tasks-panel-title">Tasks (due soon first)</div>
                                <ul class="dtp-list" id="dtpUnifiedList"></ul>
                            </div>
                        </div>
                    </div>
                </div>"""

html = html.replace(old_weekly_start, new_weekly_wrapper)

# 5. Remove the old right panel from end of dashboard layout
old_right_panel = """            </div>
            <div class="right-panel" id="weeklyRightPanel">
                <div class="chart-title" id="weeklyChartTitle">This Week</div>
                <div class="chart-outer">
                    <div class="chart-y-axis" id="chartYAxis"></div>
                    <div class="chart-body">
                        <div class="chart-bars-area" id="weeklyChart"></div>
                        <div class="chart-labels-row" id="chartLabelsRow"></div>
                    </div>
                </div>
                <div class="daily-tasks-panel" id="weeklyTasksPanel">
                    <div class="daily-tasks-panel-title">Tasks (due soon first)</div>
                    <ul class="dtp-list" id="dtpUnifiedList"></ul>
                </div>
            </div>
        </div>
    </div>"""

new_end_shell = """    </div>
    </div>"""

if old_right_panel in html:
    html = html.replace(old_right_panel, new_end_shell)
else:
    # Just aggressively strip out things
    # Wait, the structure was:
    #                 </div>
    #             </div>
    #             <div class="right-panel" id="weeklyRightPanel"> ...
    #             </div>
    #         </div>
    #     </div>
    # So we do a regex replace to remove that block
    import re
    # Remove right-panel entirely
    html = re.sub(r'<div class="right-panel" id="weeklyRightPanel">.*?</div>\n        </div>\n    </div>', '</div>\n    </div>', html, flags=re.DOTALL)
    
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)
