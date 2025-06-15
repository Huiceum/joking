from flask import Flask, request, jsonify, render_template_string, session, Response
import os
import secrets
from datetime import datetime, timedelta, date, time
import re
import pytz
from ics import Calendar, Event
import calendar
import itertools

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# --- 前端 HTML/CSS/JS (已嚴格按照您的要求修改) ---
html = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>生活週習表生成器</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        /* Dark Theme (Default) */
        :root {
            --bg-color: #000000;
            --surface-color: #1a1a1a;
            --primary-accent-color: #5979b1;
            --secondary-accent-color: #6b9bbb;
            --text-color: #ffffff;
            --text-muted-color: #cccccc;
            --border-color: #333333;
            --hover-glow: 0 0 20px rgba(107, 147, 214, 0.4);
            --error-bg: rgba(248, 81, 73, 0.1);
            --error-text: #f85149;
            --success-bg: rgba(63, 185, 80, 0.1);
            --success-text: #3fb950;
            --dot-color: rgba(107, 147, 214, 0.2);
            --icon-filter: brightness(0) invert(1);
            --tooltip-bg: rgba(42, 42, 42, 0.6);
            --tooltip-border: rgba(255, 255, 255, 0.1);
            --tooltip-text: #ffffff;
            /* Overlap Colors (Dark Theme) */
            --overlap-color-0: #5979b1; /* Primary */
            --overlap-color-1: #6b9bbb; /* Secondary */
            --overlap-color-2: #7c4dff; /* Deep Purple */
            --overlap-color-3: #ff6b35; /* Orange */
            --overlap-color-4: #4caf50; /* Green */
            --overlap-color-5: #ff9800; /* Amber */
            --overlap-color-6: #00bcd4; /* Cyan */

            /* Row Heights */
            --normal-row-height: 25px;
            --collapsed-block-height: 50px;
        }

        /* Light Theme */
        [data-theme="light"] {
            --bg-color: #ffffff;
            --surface-color: #f5f5f5;
            --primary-accent-color: #385682;
            --secondary-accent-color: #4a5d96;
            --text-color: #000000;
            --text-muted-color: #666666;
            --border-color: #e0e0e0;
            --hover-glow: 0 0 20px rgba(74, 111, 165, 0.3);
            --error-bg: rgba(220, 53, 69, 0.1);
            --error-text: #dc3545;
            --success-bg: rgba(40, 167, 69, 0.1);
            --success-text: #28a745;
            --dot-color: rgba(74, 111, 165, 0.15);
            --icon-filter: brightness(0) invert(0);
            --tooltip-bg: rgba(249, 249, 249, 0.7);
            --tooltip-border: rgba(0, 0, 0, 0.1);
            --tooltip-text: #333333;
            /* Overlap Colors (Light Theme) */
            --overlap-color-0: #385682; /* Primary */
            --overlap-color-1: #4a5d96; /* Secondary */
            --overlap-color-2: #5e35b1; /* Deep Purple */
            --overlap-color-3: #e53935; /* Red */
            --overlap-color-4: #43a047; /* Green */
            --overlap-color-5: #fb8c00; /* Orange */
            --overlap-color-6: #00acc1; /* Cyan */

             /* Row Heights */
            --normal-row-height: 25px;
            --collapsed-block-height: 50px;
        }

        body {
            font-family: 'Noto Sans TC', Arial, sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle, var(--dot-color) 1px, transparent 1px);
            background-size: 10px 10px;
            color: var(--text-color);
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            box-sizing: border-box;
            overflow-x: hidden;
        }
        
        .activity-tooltip {
            position: fixed;
            z-index: 9999;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 14px;
            line-height: 1.5;
            max-width: 300px;
            white-space: pre-wrap;
            word-wrap: break-word;
            
            /* Glassmorphism Effect */
            background: var(--tooltip-bg);
            border: 1px solid var(--tooltip-border);
            backdrop-filter: blur(10px) saturate(180%);
            -webkit-backdrop-filter: blur(10px) saturate(180%);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            color: var(--tooltip-text);

            /* Transitions and initial state */
            opacity: 0;
            transform: scale(0.95);
            transition: opacity 0.2s ease, transform 0.2s ease;
            pointer-events: none; /* Crucial: lets mouse events pass through */
            display: none;
        }

        .activity-tooltip.visible {
            display: block;
            opacity: 1;
            transform: scale(1);
        }

        .theme-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: var(--surface-color);
            border-radius: 50px;
            padding: 8px 16px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: var(--text-color);
            transition: all 0.3s ease;
            z-index: 1000;
            user-select: none;
        }

        .theme-toggle:hover {
            box-shadow: var(--hover-glow);
            transform: translateY(-2px);
        }

        .content-wrapper {
            width: 100%;
            max-width: 1400px;
            margin: 60px 0 20px 0;
            padding: 2.5rem;
            background-color: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.2);
            transition: all 0.5s ease-out;
            box-sizing: border-box;
        }

        h2, h3 {
            color: var(--secondary-accent-color);
            text-align: center;
            margin: 0 0 2rem 0;
            font-weight: 500;
        }

        .input-section { margin-bottom: 2rem; }
        .form-group { margin-bottom: 1.5rem; }

        label {
            display: block;
            margin-bottom: 0.5rem;
            font-weight: 400;
            color: var(--text-muted-color);
        }

        textarea {
            width: 100%;
            height: 250px;
            padding: 12px 15px;
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            box-sizing: border-box;
            color: var(--text-color);
            font-size: 14px;
            font-family: 'Courier New', monospace;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
            resize: vertical;
        }

        textarea:focus {
            outline: none;
            border-color: var(--primary-accent-color);
            box-shadow: 0 0 8px rgba(107, 147, 214, 0.3);
        }

        .syntax-help {
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 1rem;
            margin-top: 1rem;
            font-size: 12px;
            color: var(--text-muted-color);
        }
        .syntax-help h4 { color: var(--secondary-accent-color); margin-top: 0; }
        .syntax-help code {
            background-color: var(--surface-color);
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }

        button, .styled-button {
            background-color: var(--primary-accent-color);
            color: var(--text-color);
            padding: 12px 25px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 16px;
            font-weight: 700;
            width: 100%;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            box-sizing: border-box;
            text-align: center;
        }
        button:hover, .styled-button:hover {
            background-color: var(--secondary-accent-color);
            transform: translateY(-2px);
            box-shadow: var(--hover-glow);
        }
        button:disabled, .styled-button.disabled {
            background-color: var(--text-muted-color);
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }

        .message { margin-top: 1.5rem; padding: 12px; border-radius: 6px; text-align: center; font-weight: 500; }
        .success { background-color: var(--success-bg); color: var(--success-text); }
        .error { background-color: var(--error-bg); color: var(--error-text); }
        .loading { color: var(--text-muted-color); }

        #scheduleContent { display: none; opacity: 0; transform: translateY(20px); transition: opacity 0.8s ease-out, transform 0.8s ease-out; }
        #scheduleContent.visible { display: block; opacity: 1; transform: translateY(0); }

        #mobileControls { display: none; flex-direction: column; gap: 0.5rem; margin-bottom: 1.5rem; }
        #mobileControls .day-selector { display: flex; justify-content: space-between; align-items: center; }
        #mobileControls button { padding: 8px 12px; font-size: 14px; width: auto; flex-grow: 1; }
        #mobileControls #prevDay, #mobileControls #nextDay { flex-grow: 0; width: 50px; }
        #currentDayDisplay { color: var(--primary-accent-color); font-size: 1.2em; font-weight: 700; text-align: center; flex-grow: 2; }

        #scheduleData {
            margin-top: 1rem;
            overflow-x: hidden;
        }

        /* --- NEW Grid Structure --- */
        .schedule-grid {
            display: grid;
            /* Time column + 7 Day Containers */
            grid-template-columns: 100px repeat(7, 1fr);
            /* Header row + 48 time rows - heights managed by JS */
            grid-template-rows: auto repeat(48, var(--normal-row-height)); /* Default heights */
            gap: 2px;
            min-width: 1100px;
            box-sizing: border-box;
            font-size: 0.8em;
            position: relative; /* Needed for sticky headers */
            overflow: hidden; /* Hide content that might stick out if rows are tiny */
            transition: grid-template-rows 0.3s ease; /* Animate row height changes */
        }

        /* Header Row */
        .grid-header, .grid-time-header {
            grid-row: 1;
            color: var(--secondary-accent-color);
            font-weight: 500;
            background-color: var(--bg-color);
            position: sticky;
            top: 0;
            z-index: 3; /* Above day containers */
        }
        .grid-time-header { grid-column: 1; left: 0; z-index: 4; } /* Corner cell */
        .grid-header { /* grid-column set by JS */ text-align: center; }

        /* Time Column Cells */
        .grid-slot-time {
            grid-column: 1;
            /* grid-row set by JS */
            color: var(--text-muted-color);
            font-weight: 500;
            background-color: var(--bg-color);
            position: sticky;
            left: 0;
            z-index: 2; /* Above day containers */
            font-size: 11px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 4px;
            border-radius: 4px;
            overflow: hidden; /* Hide content when row is tiny */
            transition: background-color 0.3s ease, border-color 0.3s ease;
        }

        /* Day Column Containers (hold activities) */
        .day-column-container {
            /* grid-column set by JS */
            grid-row: 2 / span 48; /* Span all time rows */
            display: grid;
            grid-template-rows: subgrid; /* Inherit rows from parent grid */
            grid-template-columns: repeat(var(--sub-columns, 1), 1fr); /* Dynamic columns for overlap */
            gap: 1px; /* Gap between activities in same day */
            position: relative; /* Needed for stacking context */
            z-index: 1; /* Below sticky headers/time */
            background-color: var(--surface-color); /* Default background for the day column area */
             border-left: 1px solid var(--border-color); /* Separator between day columns */
             border-right: 1px solid var(--border-color);
             box-sizing: border-box;
        }
        .day-column-container:first-of-type { border-left: none; }
        .day-column-container:last-of-type { border-right: none; }


        /* Activity Cells (items within day-column-container) */
        .grid-activity {
            /* grid-row and grid-column set by JS */
            padding: 4px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            overflow: hidden;
            text-overflow: ellipsis;
            word-break: break-word; /* Handle long words */
            color: var(--bg-color); /* Text color on activity background */
            font-weight: 500;
            cursor: help;
            transition: all 0.1s ease-in-out; /* Faster transition for activities */
            position: relative; /* For tooltip handling */
            /* Default background - override with overlap color */
            background-color: var(--primary-accent-color);
            box-sizing: border-box;
        }
        
        /* Overlap Colors */
        .grid-activity.overlap-0 { background-color: var(--overlap-color-0); }
        .grid-activity.overlap-1 { background-color: var(--overlap-color-1); }
        .grid-activity.overlap-2 { background-color: var(--overlap-color-2); }
        .grid-activity.overlap-3 { background-color: var(--overlap-color-3); }
        .grid-activity.overlap-4 { background-color: var(--overlap-color-4); }
        .grid-activity.overlap-5 { background-color: var(--overlap-color-5); }
        .grid-activity.overlap-6 { background-color: var(--overlap-color-6); }


        .grid-activity:hover {
            transform: scale(1.01); /* Slightly less scale than before */
            opacity: 0.95;
            box-shadow: var(--hover-glow);
            z-index: 10; /* Bring hovered activity to front */
        }
        /* Empty cells are just gaps in the grid now, no need for explicit elements */
        /* .grid-activity.empty { display: none; } */


        /* --- Collapsed/Merged Row Styles --- */
        /* Apply row-expandable to the time slot cell that starts a collapsible block */
        .grid-slot-time.row-expandable { cursor: pointer; }

        /* Hide time slots within a collapsed block (except the first) */
        .grid-slot-time.cell-hidden-by-collapse {
             display: none !important; /* Hide completely */
        }

        /* Style the header of the collapsed block (the first time slot cell) */
        .grid-slot-time.is-collapsed-merged {
             background-color: var(--surface-color) !important; /* Lighter background */
             border: 1px dashed var(--border-color) !important; /* Dashed border */
             color: var(--text-color) !important; /* Ensure text is visible */
             font-weight: 500 !important;
             justify-content: center !important;
             /* Height is controlled by grid-template-rows on the parent */
        }
         .grid-slot-time.is-collapsed-merged:hover {
             background-color: var(--bg-color) !important; /* Darker hover */
         }

        /* Hide normal time, show collapsed time text in the header */
        .grid-slot-time.is-collapsed-merged .content-normal { display: none; }
        .grid-slot-time.is-collapsed-merged .content-collapsed { display: inline; }

        /* Hide activity elements that fall within a collapsed time range */
        .activity-hidden-by-collapse { display: none !important; }


        .export-buttons { display: none; flex-direction: column; gap: 1rem; margin-top: 2rem; padding-top: 2rem; border-top: 1px solid var(--border-color); }
        .export-button { display: flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 20px; background: #00000000; backdrop-filter: blur(10px) saturate(180%); -webkit-backdrop-filter: blur(10px) saturate(180%); border: 1px solid var(--border-color); border-radius: 12px; cursor: pointer; font-size: 16px; font-weight: 500; text-decoration: none; color: var(--text-color); mix-blend-mode: difference; transition: all 0.3s ease; }
        .export-button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25); background: #00000010; }
        .export-button:disabled { background: #00000010; border: 1px solid var(--border-color); cursor: not-allowed; transform: none; box-shadow: none; opacity: 0.5; }
        .export-icon { width: 20px; height: 20px; filter: var(--icon-filter); }

        @media (max-width: 768px) {
            body { padding: 0 10px; background-size: 15px 15px; }
            .theme-toggle { top: 15px; right: 15px; padding: 6px 12px; font-size: 12px; }
            .content-wrapper { max-width: 100%; margin: 50px 0 15px 0; padding: 1.5rem 1rem; border-radius: 8px; border: none; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
            #mobileControls { display: flex; }

            /* Mobile Today View Grid Layout */
            .schedule-grid.mobile-today-view {
                /* grid-template-columns set by JS based on day's max_cols */
                min-width: unset; /* Allow shrinking */
                font-size: 0.7em;
                gap: 1px;
            }
             .schedule-grid.mobile-today-view .grid-cell { padding: 2px 1px; min-height: unset; } /* min-height unset for mobile collapse */


            /* Hide other days in Mobile Today View */
            .day-hidden { display: none !important; }

            /* Mobile Full Week View Grid Layout */
            .schedule-grid.mobile-full-view {
                 /* MODIFIED: Force table to fit screen width and shrink font */
                 min-width: unset;
                 width: 100%;
                 grid-template-columns: 40px repeat(7, 1fr); /* MODIFIED: Narrower time column */
                 font-size: 0.5em; /* Shrink font to fit */
                 gap: 1px;
            }
             .schedule-grid.mobile-full-view .grid-cell { padding: 2px 1px; min-height: unset; } /* min-height unset for mobile collapse */


            /* Adjust Day Column Containers for Mobile */
            .day-column-container {
                 grid-row: 2 / span 48; /* Still span all time rows */
                 /* grid-column set by JS */
                 gap: 0.5px; /* Smaller gap on mobile */
            }

            /* Hide tooltip on mobile by default, JS will control display on click */
             .activity-tooltip { display: none; }
             .activity-tooltip.visible { display: block; }

        }
        @media (min-width: 769px) { /* Desktop styles */
            .export-buttons { flex-direction: row; }
            .export-buttons > * { flex: 1; }

            /* Ensure day columns take equal space on desktop */
             .schedule-grid {
                grid-template-columns: 100px repeat(7, 1fr);
             }
             .day-column-container {
                 grid-column: auto !important; /* Reset explicit column set by mobile JS */
             }
             .day-hidden { display: grid !important; } /* Ensure day columns are visible */
        }

        /* Print Styles */
        .is-printing {
            background-color: #ffffff !important;
            min-width: 1200px !important;
        }
        .is-printing .grid-cell {
            background-color: #ffffff !important;
            color: #000000 !important;
            border: 1px solid #ddd !important;
        }
        .is-printing .grid-slot-time,
        .is-printing .grid-header,
        .is-printing .grid-time-header {
            background-color: #f2f2f2 !important;
            color: #000000 !important;
            position: static !important; /* Remove sticky */
        }
        .is-printing .day-column-container {
             background-color: #ffffff !important; /* White background for day columns */
             border-color: #ddd !important;
             grid-row: 2 / span 48 !important; /* Ensure spanning */
             grid-column: auto !important; /* Ensure correct column placement */
        }
         .is-printing .day-column-container:first-of-type { border-left: 1px solid #ddd !important; } /* Add border back */
         .is-printing .day-column-container:last-of-type { border-right: 1px solid #ddd !important; }


        .is-printing .grid-activity {
            background-color: #e3f2fd !important; /* Default light blue for print */
            color: #000000 !important;
            border: 1px solid #ddd !important; /* Add border to activities */
             /* Reset overlap colors for print if needed, or keep the light blue */
             background-color: #e3f2fd !important;
        }
         .is-printing .grid-activity.overlap-0,
         .is-printing .grid-activity.overlap-1,
         .is-printing .grid-activity.overlap-2,
         .is-printing .grid-activity.overlap-3,
         .is-printing .grid-activity.overlap-4,
         .is-printing .grid-activity.overlap-5,
         .is-printing .grid-activity.overlap-6 {
             background-color: #e3f2fd !important;
         }


        .is-printing .activity-tooltip { display: none !important; } /* Hide tooltips */

        /* Ensure all elements are visible during printing, overriding collapse states */
        .is-printing .cell-hidden-by-collapse {
            display: flex !important; /* Re-show time slots */
        }
        .is-printing .activity-hidden-by-collapse {
            display: flex !important; /* Re-show activities */
        }
        .is-printing .grid-slot-time.is-collapsed-merged .content-normal {
            display: block !important; /* Show normal time for collapsed rows */
        }
        .is-printing .grid-slot-time.is-collapsed-merged .content-collapsed {
            display: none !important; /* Hide collapsed time */
        }
        /* Restore normal time slot background/border for print */
        .is-printing .grid-slot-time.expanded.is-collapsed-merged {
             background-color: #f2f2f2 !important; /* Restore normal time header background */
             border: 1px solid #ddd !important; /* Restore normal border */
             color: #000000 !important;
        }
         /* Ensure the default 25px height for rows during print */
         .is-printing.schedule-grid {
             grid-template-rows: auto repeat(48, var(--normal-row-height)) !important;
         }
    </style>
</head>
<body>
    <!-- NEW: Tooltip Element -->
    <div id="activity-tooltip" class="activity-tooltip"></div>

    <div class="theme-toggle" onclick="toggleTheme()">
        <span id="theme-text">dark</span>
    </div>

    <div class="content-wrapper">
        <h2 id="mainTitle">生活週習表生成器</h2>
        
        <div class="input-section">
            <form id="scheduleForm">
                <div class="form-group">
                    <label for="scheduleInput">請輸入您的週習表描述:</label>
                    <textarea id="scheduleInput" name="scheduleInput" placeholder="範例：
config:ics_repeat=3m

週一 08:00-10:30 晨間運動 [記得帶水和毛巾]
週一 09:00-11:00 專案開發 [完成登入模塊]
二 9:00-12:00 辦公室工作
三 14:00-15:00 團隊會議 [準備進度報告]
三 14:30-16:00 客戶拜訪 [重疊會議]
五 23:00-次日 01:00 看電影 [放鬆一下]"></textarea>
                    <div class="syntax-help">
                        <h4>語法說明：</h4>
                        <ul>
                            <li><b>活動格式:</b> <code>[星期] [開始時間]-[結束時間] [活動名稱] [[備註]]</code></li>
                            <li><b>星期:</b> <code>週一</code>, <code>週二</code>... 或 <code>一</code>, <code>二</code>...<code>日</code></li>
                            <li><b>時間:</b> 24小時制，例如 <code>09:00</code>, <code>14:30</code></li>
                            <li><b>跨天:</b> <code>週一 23:00-次日 01:30 夜間學習</code></li>
                            <li><b>備註:</b> 在行末使用方括號 <code>[這是我的備註]</code></li>
                            <li><b>重疊活動:</b> 系統會自動將重疊的活動拆分到不同欄位中並用不同顏色區分</li>
                            <li><b>全局設定:</b> <code>config:ics_repeat=3m</code> (設定日曆匯出重複3個月，預設6個月)</li>
                        </ul>
                    </div>
                </div>
                <button type="submit" id="generateBtn">生成週習表</button>
            </form>
        </div>
        
        <div id="message"></div>
        
        <div id="scheduleContent">
            <div id="mobileControls">
                <div class="day-selector">
                    <button id="prevDay"><</button>
                    <span id="currentDayDisplay"></span>
                    <button id="nextDay">></button>
                </div>
                <button id="toggleViewBtn">顯示整週</button>
            </div>
            <div id="scheduleData"></div>
            <div class="export-buttons" id="exportContainer">
                <button class="export-button" id="exportPngBtn">
                    <svg class="export-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21,15 16,10 5,21"/></svg>
                    導出為 PNG
                </button>
                <button class="export-button" id="exportPdfBtn">
                    <svg class="export-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14,2 L20,8 L20,22 L4,22 L4,2 L14,2 Z"/><polyline points="14,2 14,8 20,8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10,9 9,9 8,9"/></svg>
                    導出為 PDF
                </button>
                <button class="export-button" id="exportIcsBtn">
                    <svg class="export-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
                    添加到日曆 (.ics)
                </button>
            </div>
        </div>
    </div>

    <script>
        let currentDayIndex = 0;
        let currentViewMode = "today"; // "today", "full-mobile", "full-desktop"
        const dayNames = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"];
        let processedScheduleData = null; // Store fetched processed schedule data

        // Define row heights (read from CSS variables)
        let normalRowHeight = 25;
        let collapsedBlockHeight = 50;


        function getCssVariable(name) {
             const style = getComputedStyle(document.documentElement);
             return parseFloat(style.getPropertyValue(name).replace('px', ''));
        }

        function updateCssVariables() {
             normalRowHeight = getCssVariable('--normal-row-height');
             collapsedBlockHeight = getCssVariable('--collapsed-block-height');
        }


        function toggleTheme() {
            const newTheme = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
            document.documentElement.setAttribute('data-theme', newTheme);
            document.getElementById('theme-text').textContent = newTheme;
            localStorage.setItem('theme', newTheme);
            updateCssVariables(); // Update variables if theme changes them
            updateTableView(); // Re-render grid with potentially new heights
        }

        function loadTheme() {
            const savedTheme = localStorage.getItem('theme') || 'dark';
            document.documentElement.setAttribute('data-theme', savedTheme);
            document.getElementById('theme-text').textContent = savedTheme;
        }

        function setupMobileView() {
            const isMobile = window.innerWidth <= 768;
            const mobileControls = document.getElementById("mobileControls");
            if (!document.querySelector(".schedule-grid")) return;

            mobileControls.style.display = isMobile ? "flex" : "none";

            if (isMobile && currentViewMode !== "full-mobile" && currentViewMode !== "today") {
                let today = new Date().getDay(); // 0 is Sunday, 1 is Monday...
                currentDayIndex = (today === 0) ? 6 : today - 1; // Convert to 0=Mon, ..., 6=Sun
                currentViewMode = "today";
            } else if (!isMobile && (currentViewMode === "today" || currentViewMode === "full-mobile")) {
                 // If switching from mobile to desktop, revert to full desktop view
                 currentViewMode = "full-desktop";
            }
            updateTableView(); // Always call updateTableView after setting mode
        }

        function renderScheduleGrid(data) {
             processedScheduleData = data; // Store the data globally
             updateCssVariables(); // Get initial heights from CSS

             const weekDays = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"];
             const numSlots = 48; // 00:00 to 23:30

             let html = '<div class="schedule-grid">';

             // Header Row (grid-row: 1)
             html += '<div class="grid-cell grid-time-header"></div>'; // Corner (grid-column: 1)
             for (let i = 0; i < 7; i++) {
                 // Day headers (grid-column: 2 to 8)
                 html += `<div class="grid-cell grid-header" data-day-index="${i}" style="grid-column: ${i + 2};">${weekDays[i]}</div>`;
             }

             // Time Column Cells (grid-column: 1, grid-row: 2 to 49)
             for (let slotIdx = 0; slotIdx < numSlots; slotIdx++) {
                 const startTime = `${String(Math.floor(slotIdx / 2)).padStart(2, '0')}:${String((slotIdx % 2) * 30).padStart(2, '0')}`;
                 
                 html += `
                     <div class="grid-cell grid-slot-time" data-slot-index="${slotIdx}" style="grid-row: ${slotIdx + 2};">
                        <span class="content-normal">${startTime}</span>
                        <span class="content-collapsed"></span>
                     </div>
                 `;
             }

             // Day Column Containers (grid-column: 2 to 8, grid-row: 2 / span 48)
             for (let dayIdx = 0; dayIdx < 7; dayIdx++) {
                 const maxCols = data.max_day_cols[dayIdx] || 1;
                 html += `
                     <div class="day-column-container" data-day-index="${dayIdx}" style="grid-column: ${dayIdx + 2}; grid-row: 2 / span 48; --sub-columns: ${maxCols};">
                         <!-- Activities for Day ${dayIdx} will be appended here by JS -->
                     </div>
                 `;
             }

             html += '</div>'; // Close schedule-grid

             // Append activities to their respective day containers
             const tempDiv = document.createElement('div');
             tempDiv.innerHTML = html;

             data.day_activities.forEach((activities, dayIdx) => {
                 const dayContainer = tempDiv.querySelector(`.day-column-container[data-day-index="${dayIdx}"]`);
                 if (!dayContainer) return;

                 activities.forEach(activity => {
                     const duration = activity.end_slot - activity.start_slot;
                     const colSpan = activity.col_span || 1; // Default col_span is 1
                     const overlapClass = `overlap-${activity.col_index % 7}`; // Use modulo 7 for color variety

                     const activityHtml = `
                         <div class="grid-activity has-activity ${overlapClass}"
                              data-note="${activity.note || ''}"
                              data-is-empty="false"
                              data-slot-index="${activity.start_slot}"
                              data-day-index="${activity.day}"
                              data-end-slot="${activity.end_slot}"
                              style="grid-row: ${activity.start_slot + 1} / span ${duration}; grid-column: ${activity.col_index + 1} / span ${colSpan};">
                             ${activity.name}
                         </div>
                     `;
                     dayContainer.innerHTML += activityHtml;
                 });
             });

             document.getElementById("scheduleData").innerHTML = tempDiv.innerHTML;
        }


        function updateTableView() {
            const isMobile = window.innerWidth <= 768;
            const grid = document.querySelector(".schedule-grid");
            if (!grid || !processedScheduleData) return; // Ensure grid and data exist

             // Reset previous states related to view mode
             grid.classList.remove("mobile-today-view", "mobile-full-view");
             grid.style.gridTemplateColumns = ""; // Reset main grid columns


             const timeSlots = Array.from(grid.querySelectorAll(".grid-slot-time"));
             const dayContainers = Array.from(grid.querySelectorAll(".day-column-container"));
             const allActivities = Array.from(grid.querySelectorAll(".grid-activity"));
             const dayHeaders = Array.from(grid.querySelectorAll(".grid-header"));


             // Reset collapsing/hiding classes and styles on time slots
             timeSlots.forEach(slot => {
                 // Keep 'expanded' class if it exists, reset others
                 slot.classList.remove("row-expandable", "is-collapsed-merged", "cell-hidden-by-collapse");
                 slot.style.display = 'flex'; // Make sure it's visible
                 slot.querySelector('.content-normal').style.display = 'flex'; // Show normal time
                 slot.querySelector('.content-collapsed').style.display = 'none'; // Hide collapsed time
                 slot.querySelector('.content-collapsed').textContent = ''; // Clear collapsed text
                 delete slot.dataset.groupStart;
                 delete slot.dataset.groupEnd;
             });
             // Reset hiding classes on activities
             allActivities.forEach(activity => {
                 activity.classList.remove("activity-hidden-by-collapse");
                 activity.style.display = ''; // Ensure activities are visible initially
             });
             // Reset hiding classes on day containers and headers
             dayContainers.forEach(container => {
                 container.classList.remove("day-hidden");
                 container.style.gridColumn = ''; // Reset explicit grid-column on desktop
             });
             dayHeaders.forEach(header => {
                 header.classList.remove("day-hidden");
                 header.style.gridColumn = ''; // Reset explicit grid-column
             });


            // Apply view mode settings (mobile single day vs full week)
            if (isMobile && currentViewMode === "today") {
                document.getElementById("toggleViewBtn").textContent = "顯示整週";
                // Set main grid columns for mobile today view
                const mobileSubCols = processedScheduleData.max_day_cols[currentDayIndex] || 1;
                grid.style.setProperty('--mobile-sub-columns', mobileSubCols);
                grid.classList.add("mobile-today-view");
                grid.style.gridTemplateColumns = `60px repeat(var(--mobile-sub-columns), 1fr)`;


                // Hide other day containers and headers
                dayContainers.forEach(container => {
                    if (container.dataset.dayIndex != currentDayIndex) {
                        container.classList.add("day-hidden");
                    } else {
                         // Explicitly set grid-column for the visible day in mobile today view
                         container.style.gridColumn = '2 / span var(--mobile-sub-columns)';
                    }
                });
                 dayHeaders.forEach(header => {
                    if (header.dataset.dayIndex != currentDayIndex) {
                        header.classList.add("day-hidden");
                    } else {
                        // MODIFIED: Make the visible day header span all content columns
                        header.style.gridColumn = '2 / -1';
                    }
                });

            } else if (isMobile && currentViewMode === "full-mobile") {
                 grid.classList.add("mobile-full-view");
                 // The rest is handled by CSS for .mobile-full-view
            } else if (!isMobile) { // Desktop full week view
                 // Desktop view - ensure full week columns
                 grid.style.gridTemplateColumns = "100px repeat(7, 1fr)";
                 // Day containers grid-column is auto by default in desktop CSS
            }


            // --- Collapsing Logic ---
            const rowHeights = Array(48).fill(`${normalRowHeight}px`); // Array to build grid-template-rows string
            let currentBlock = null; // { startSlotIdx: N, endSlotIdx: M }
            let collapsibleBlocks = []; // Array to store detected blocks

            const isSlotEmptyInCurrentView = (slotIndex) => {
                // Check if any activity is active during this slot on the relevant day(s)
                for (let dayIdx = 0; dayIdx < 7; dayIdx++) {
                    // In mobile 'today' mode, only check the current day
                    if (isMobile && currentViewMode === "today" && dayIdx != currentDayIndex) {
                        continue;
                    }
                    // In other modes (full week, mobile full week), check all days

                    const activitiesInSlotOnDay = processedScheduleData.day_activities[dayIdx].filter(act =>
                         act.start_slot <= slotIndex && act.end_slot > slotIndex
                    );
                    if (activitiesInSlotOnDay.length > 0) {
                        return false; // Found activity, slot is NOT empty in this view
                    }
                }
                return true; // No activities found in this slot for the relevant day(s)
            };


            // 1. Detect contiguous empty blocks based on the current view mode
            for (let i = 0; i < timeSlots.length; i++) {
                const slotIndex = parseInt(timeSlots[i].dataset.slotIndex);

                if (isSlotEmptyInCurrentView(slotIndex)) {
                    if (currentBlock === null) {
                        currentBlock = { startSlotIdx: i, endSlotIdx: i };
                    } else {
                        currentBlock.endSlotIdx = i; // Extend the current block
                    }
                } else {
                    if (currentBlock !== null) {
                        if (currentBlock.endSlotIdx > currentBlock.startSlotIdx) { // Only consider blocks > 1 slot
                            collapsibleBlocks.push(currentBlock); // Finalize the block
                        }
                        currentBlock = null;
                    }
                }
            }
            // Finalize any pending block after the loop
            if (currentBlock !== null && currentBlock.endSlotIdx > currentBlock.startSlotIdx) {
                collapsibleBlocks.push(currentBlock);
            }

            // 2. Apply collapsing states and update element visibility/styles for detected blocks
            collapsibleBlocks.forEach(block => {
                const headerSlotEl = timeSlots[block.startSlotIdx];
                if (!headerSlotEl) return;

                // Check if this block is currently expanded (based on the presence of 'expanded' class on the header)
                const isExpanded = headerSlotEl.classList.contains('expanded');

                // Add row-expandable class to the header regardless of expanded state
                headerSlotEl.classList.add("row-expandable");
                headerSlotEl.dataset.groupStart = timeSlots[block.startSlotIdx].dataset.slotIndex;
                headerSlotEl.dataset.groupEnd = timeSlots[block.endSlotIdx].dataset.slotIndex;

                if (!isExpanded) { // Apply collapsed state if not expanded
                     headerSlotEl.classList.add("is-collapsed-merged");

                     // Update the text for the merged block header
                     const startTimeText = timeSlots[block.startSlotIdx].querySelector('.content-normal').textContent.trim();
                     const endSlotIndex = parseInt(timeSlots[block.endSlotIdx].dataset.slotIndex) + 1;
                     const endTime = `${String(Math.floor(endSlotIndex / 2)).padStart(2, '0')}:${String((endSlotIndex % 2) * 30).padStart(2, '0')}`;
                     headerSlotEl.querySelector('.content-collapsed').textContent = `${startTimeText} ${endTime}`;
                     headerSlotEl.querySelector('.content-normal').style.display = 'none'; // Hide normal time
                     headerSlotEl.querySelector('.content-collapsed').style.display = 'inline'; // Show collapsed time

                     // Hide subsequent time slots within this merged block
                     for (let k = block.startSlotIdx + 1; k <= block.endSlotIdx; k++) {
                         const currentSlotEl = timeSlots[k];
                         if (currentSlotEl) {
                             currentSlotEl.classList.add("cell-hidden-by-collapse");
                         }
                     }

                     // Hide all activity elements that fall within this collapsed time range and are relevant to the view
                     allActivities.forEach(activity => {
                         const activityStart = parseInt(activity.dataset.slotIndex);
                         const activityEnd = parseInt(activity.dataset.endSlot);
                         const blockStart = parseInt(headerSlotEl.dataset.groupStart);
                         const blockEnd = parseInt(headerSlotEl.dataset.groupEnd);

                         const doesOverlap = (activityStart < blockEnd + 1) && (activityEnd > blockStart);
                         const isRelevantForView = (!isMobile || currentViewMode !== "today" || parseInt(activity.dataset.dayIndex) === currentDayIndex);

                         if (doesOverlap && isRelevantForView) {
                             activity.classList.add("activity-hidden-by-collapse");
                         }
                     });

                     // Set the height for rows in the main grid corresponding to this collapsed block
                     // The first row of the block gets the fixed height, the rest get 0 height
                     rowHeights[block.startSlotIdx] = `${collapsedBlockHeight}px`;
                     for (let k = block.startSlotIdx + 1; k <= block.endSlotIdx; k++) {
                         rowHeights[k] = `0px`;
                     }
                }
                // No 'else' needed here, as the default state is expanded, which is handled
                // by the initial `rowHeights` array and the reset logic at the beginning.
            });

            // 3. Apply the calculated grid-template-rows to the main grid
            // Row 1 is the header row (auto height), then 48 time rows
            const gridTemplateRowsCSS = `auto ${rowHeights.join(' ')}`;
            grid.style.gridTemplateRows = gridTemplateRowsCSS;


            // Update mobile controls display
            document.getElementById("currentDayDisplay").textContent = dayNames[currentDayIndex];
            document.getElementById("prevDay").disabled = (currentDayIndex === 0 && currentViewMode === "today");
            document.getElementById("nextDay").disabled = (currentDayIndex === 6 && currentViewMode === "today");
        }

        async function performExport(type) {
            const grid = document.querySelector('.schedule-grid');
            const button = document.getElementById(`export${type}Btn`);
            const originalText = button.innerHTML;
            button.innerHTML = `<svg class="export-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/></svg>生成中...`;
            button.disabled = true;

            grid.classList.add('is-printing');
            // Ensure full week view for print
            grid.classList.remove('mobile-today-view', 'mobile-full-view');
            grid.style.gridTemplateColumns = "100px repeat(7, 1fr)"; // Force desktop full view columns
            grid.style.setProperty('--mobile-sub-columns', ''); // Remove mobile specific var
            grid.style.gridTemplateRows = `auto repeat(48, ${normalRowHeight}px)`; // Restore normal row heights for print


            // Expand all merged/collapsed rows by removing hiding/collapsing classes and resetting styles
            grid.querySelectorAll('.grid-slot-time').forEach(slot => {
                 slot.classList.remove("row-expandable", "is-collapsed-merged", "expanded", "cell-hidden-by-collapse");
                 // Restore default styles
                 slot.style.display = 'flex'; // Restore display
                 slot.querySelector('.content-normal').style.display = 'flex'; // Show normal time
                 slot.querySelector('.content-collapsed').style.display = 'none'; // Hide collapsed time
                 slot.querySelector('.content-collapsed').textContent = ''; // Clear collapsed text
                 delete slot.dataset.groupStart;
                 delete slot.dataset.groupEnd;
            });
             grid.querySelectorAll('.grid-activity').forEach(activity => {
                 activity.classList.remove("activity-hidden-by-collapse");
                 activity.style.display = ''; // Ensure activities are visible
             });


            try {
                // Wait a moment for layout to settle after expansion
                await new Promise(resolve => setTimeout(resolve, 100));

                const canvas = await html2canvas(grid, { scale: 2, useCORS: true, backgroundColor: '#ffffff' });

                const link = document.createElement('a');
                if (type === 'Png') {
                    link.download = 'weekly_schedule.png';
                    link.href = canvas.toDataURL('image/png');
                    link.click();
                } else if (type === 'Pdf') {
                    const { jsPDF } = window.jspdf;
                    const imgData = canvas.toDataURL('image/png');
                    // Calculate PDF size based on canvas dimensions, maintain aspect ratio
                    const aspectRatio = canvas.width / canvas.height;
                    const a4WidthPx = 210 * 3.779528; // A4 width in pixels (approx, 72dpi)
                    const a4HeightPx = 297 * 3.779528; // A4 height in pixels (approx, 72dpi)

                    let pdfWidth = a4WidthPx;
                    let pdfHeight = a4WidthPx / aspectRatio;
                    let orientation = 'p'; // portrait

                    if (canvas.width > canvas.height) { // Landscape if canvas is wider
                         pdfHeight = a4HeightPx;
                         pdfWidth = pdfHeight * aspectRatio;
                         orientation = 'l';
                    }

                    // If the calculated height is still too large for A4, scale down
                    if (pdfHeight > a4HeightPx && orientation === 'p') {
                         const scaleFactor = a4HeightPx / pdfHeight;
                         pdfHeight = a4HeightPx;
                         pdfWidth = pdfWidth * scaleFactor;
                    } else if (pdfWidth > a4WidthPx && orientation === 'l') {
                         const scaleFactor = a4WidthPx / pdfWidth;
                         pdfWidth = a4WidthPx;
                         pdfHeight = pdfHeight * scaleFactor;
                    }


                    const pdf = new jsPDF({ orientation: orientation, unit: 'px', format: [pdfWidth, pdfHeight] });
                    pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight);
                    pdf.save('weekly_schedule.pdf');
                }
            } catch (error) {
                console.error('Export failed:', error);
                alert('導出失敗，請查看控制台日誌。');
            } finally {
                // Revert to original display mode after export
                grid.classList.remove('is-printing');
                updateTableView(); // This will re-apply collapse/mobile view
                button.innerHTML = originalText;
                button.disabled = false;
            }
        }

        document.addEventListener("DOMContentLoaded", () => {
            loadTheme();
            updateCssVariables(); // Get initial heights on load

            // --- Tooltip Logic ---
            const tooltip = document.getElementById('activity-tooltip');
            const scheduleDataContainer = document.getElementById('scheduleData');
            let tooltipVisible = false;
            let activeTooltipTarget = null; // Keep track of the element showing the tooltip

            const showTooltip = (target, event) => {
                const note = target.dataset.note;
                if (!note) return; // Only show if there's a note

                // If a tooltip is already visible from a *different* target, hide it first
                if (tooltipVisible && activeTooltipTarget && activeTooltipTarget !== target) {
                    hideTooltip();
                }

                tooltip.innerHTML = note;
                tooltip.classList.add('visible');
                tooltipVisible = true;
                activeTooltipTarget = target;
                updateTooltipPosition(event);
            };

            const hideTooltip = () => {
                tooltip.classList.remove('visible');
                tooltipVisible = false;
                activeTooltipTarget = null;
            };

            const updateTooltipPosition = (event) => {
                if (!tooltipVisible || !activeTooltipTarget) return;
                
                const offsetX = 15;
                const offsetY = 15;
                const tooltipRect = tooltip.getBoundingClientRect();
                const viewportWidth = window.innerWidth;
                const viewportHeight = window.innerHeight;

                let x = event.clientX + offsetX;
                let y = event.clientY + offsetY;

                // Boundary checks
                if (x + tooltipRect.width > viewportWidth - 10) { // Add a small buffer
                    x = event.clientX - tooltipRect.width - offsetX;
                }
                if (y + tooltipRect.height > viewportHeight - 10) { // Add a small buffer
                    y = event.clientY - tooltipRect.height - offsetY;
                }
                
                // Ensure tooltip doesn't go off left/top edge
                 if (x < 5) x = 5;
                 if (y < 5) y = 5;

                tooltip.style.left = `${x}px`;
                tooltip.style.top = `${y}px`;
            };
            
            // Event Listeners for Tooltip (Delegation on scheduleDataContainer)
            scheduleDataContainer.addEventListener('mouseover', (event) => {
                if (window.innerWidth > 768) { // Desktop only
                    const target = event.target.closest('.grid-activity[data-note]');
                    if (target) {
                        // Don't show tooltip if the activity is hidden by collapsing
                        if (!target.classList.contains('activity-hidden-by-collapse')) {
                             showTooltip(target, event);
                        }
                    } else {
                         // If mouse moves off an activity, hide tooltip
                         const relatedTarget = event.relatedTarget;
                         if (activeTooltipTarget && (!relatedTarget || !scheduleDataContainer.contains(relatedTarget))) {
                             hideTooltip();
                         }
                    }
                }
            });

            scheduleDataContainer.addEventListener('mouseout', (event) => {
                 if (window.innerWidth > 768) { // Desktop only
                    const target = event.target.closest('.grid-activity[data-note]');
                    const relatedTarget = event.relatedTarget;

                    if (target && (!relatedTarget || !target.contains(relatedTarget) && !tooltip.contains(relatedTarget))) {
                         setTimeout(() => {
                             const elementUnderMouse = document.elementFromPoint(event.clientX, event.clientY);
                             if (activeTooltipTarget === target && !tooltip.contains(elementUnderMouse) && !target.contains(elementUnderMouse)) {
                                 hideTooltip();
                             }
                         }, 50); // Small delay
                    }
                 }
            });

             // Mousemove listener for desktop to update tooltip position
            scheduleDataContainer.addEventListener('mousemove', (event) => {
                if (window.innerWidth > 768) { // Desktop only
                    updateTooltipPosition(event);
                }
            });

            scheduleDataContainer.addEventListener('click', (event) => {
                if (window.innerWidth <= 768) { // Mobile only
                    const target = event.target.closest('.grid-activity[data-note]');
                    if (target) {
                        // Only show tooltip if the activity is NOT hidden by collapsing
                        if (!target.classList.contains('activity-hidden-by-collapse')) {
                            event.preventDefault();
                            event.stopPropagation();

                            if (tooltipVisible && activeTooltipTarget === target) {
                                hideTooltip();
                            } else {
                                showTooltip(target, event);
                            }
                        }
                    } else {
                         // Clicked outside an activity, hide tooltip if visible
                         if (tooltipVisible) {
                             hideTooltip();
                         }
                    }
                }
            });
            
            // Hide tooltip on any click *outside* the tooltip or an activity on mobile
            document.body.addEventListener('click', (event) => {
                if (window.innerWidth <= 768 && tooltipVisible) {
                    const isClickInsideTooltip = tooltip.contains(event.target);
                    const isClickInsideActivity = event.target.closest('.grid-activity[data-note]');
                    
                    if (!isClickInsideTooltip && !isClickInsideActivity) {
                        hideTooltip();
                    }
                }
            }, true);


            // Event listener for row collapsing/expanding
            scheduleDataContainer.addEventListener("click", event => {
                const expandableRow = event.target.closest(".grid-slot-time.row-expandable");
                if (!expandableRow) return;

                // Toggle the 'expanded' state on the clicked time slot element
                expandableRow.classList.toggle("expanded");

                // Re-run updateTableView to recalculate collapse states and row heights
                // based on the new expanded state of this row.
                updateTableView();

                // Hide tooltip if it was showing for an activity that just got hidden
                 if (tooltipVisible && activeTooltipTarget && activeTooltipTarget.classList.contains('activity-hidden-by-collapse')) {
                     hideTooltip();
                 }
            });


            document.getElementById("exportPngBtn").addEventListener("click", () => performExport("Png"));
            document.getElementById("exportPdfBtn").addEventListener("click", () => performExport("Pdf"));
            document.getElementById("exportIcsBtn").addEventListener("click", () => window.location.href = '/api/export/ics');
            document.getElementById("prevDay").addEventListener("click", () => { if (currentDayIndex > 0) { currentDayIndex--; updateTableView(); } });
            document.getElementById("nextDay").addEventListener("click", () => { if (currentDayIndex < 6) { currentDayIndex++; updateTableView(); } });
            document.getElementById("toggleViewBtn").addEventListener("click", () => { if (window.innerWidth <= 768) { currentViewMode = (currentViewMode === "today") ? "full-mobile" : "today"; updateTableView(); } else { /* Desktop toggle not implemented */ } });
            window.addEventListener("resize", setupMobileView);
        });

        document.getElementById("scheduleForm").addEventListener("submit", async function(event) {
            event.preventDefault();
            const scheduleInput = document.getElementById("scheduleInput").value;
            const generateBtn = document.getElementById("generateBtn");
            const messageDiv = document.getElementById("message");

            generateBtn.disabled = true;
            generateBtn.textContent = "生成中...";
            messageDiv.innerHTML = '<div class="loading">正在解析語法並生成週習表...</div>';
            document.getElementById("scheduleContent").classList.remove("visible");

            try {
                const response = await fetch("/api/generate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ schedule_input: scheduleInput }),
                });
                const result = await response.json();
                if (result.status === "success") {
                    messageDiv.innerHTML = '<div class="success">週習表生成成功！</div>';
                    renderScheduleGrid(result.data); // Render the grid with the new data structure
                    document.getElementById("scheduleContent").classList.add("visible");
                    document.getElementById("exportContainer").style.display = "flex";
                    setupMobileView(); // Apply view settings including new collapse logic
                } else {
                    messageDiv.innerHTML = `<div class="error">生成失敗: ${result.message}</div>`;
                }
            } catch (error) {
                messageDiv.innerHTML = `<div class="error">發生錯誤: ${error.message}</div>`;
            } finally {
                generateBtn.disabled = false;
                generateBtn.textContent = "生成週習表";
            }
        });
    </script>
</body>
</html>
'''

# --- 後端 Python 代碼 (已更新以實現新的重疊佈局邏輯) ---
@app.route('/')
def index():
    return render_template_string(html)

def parse_schedule_input(input_text):
    """解析週習表輸入語法"""
    activities = []
    config = {'ics_repeat_months': 6} # 預設重複6個月
    
    day_map = {
        '一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6,
        '週一': 0, '週二': 1, '週三': 2, '週四': 3, '週五': 4, '週六': 5, '週日': 6
    }
    
    line_regex = re.compile(
        r'^\s*(週?[一二三四五六日])\s+'
        r'(\d{1,2}:\d{2})\s*-\s*'
        r'(次日\s+)?(\d{1,2}:\d{2})\s+'
        r'([^[]+)'
        r'(?:\s*\[(.+?)\])?\s*$'
    )
    
    config_regex = re.compile(r'^\s*config:ics_repeat=(\d+)m\s*$', re.IGNORECASE)

    for line in input_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue

        config_match = config_regex.match(line)
        if config_match:
            config['ics_repeat_months'] = int(config_match.group(1))
            continue

        match = line_regex.match(line)
        if not match:
            raise ValueError(f"語法錯誤，無法解析此行：'{line}'")
        
        day_str, start_time_str, is_next_day, end_time_str, name, note = match.groups()
        
        day_index = day_map.get(day_str)
        if day_index is None:
            raise ValueError(f"無效的星期：'{day_str}'")

        start_h, start_m = map(int, start_time_str.split(':'))
        end_h, end_m = map(int, end_time_str.split(':'))

        if start_m not in [0, 30] or end_m not in [0, 30]:
            raise ValueError(f"時間必須是整點或半點 (00 或 30)，錯誤於：'{line}'")

        start_slot = start_h * 2 + (start_m // 30)
        end_slot = end_h * 2 + (end_m // 30)

        if is_next_day:
            end_slot += 48 # Activities crossing midnight will have end_slot > 47

        if start_slot >= end_slot:
            raise ValueError(f"結束時間必須晚於開始時間，錯誤於：'{line}'")

        activities.append({
            'day': day_index,
            'start_slot': start_slot,
            'end_slot': end_slot,
            'name': name.strip(),
            'note': note.strip() if note else None
        })
        
    return {'activities': activities, 'config': config}

def calculate_overlap_layout(activities_for_day):
    """
    Calculates column index and span for overlapping activities for a single day.
    This version groups overlapping events and gives non-overlapping events full width.
    """
    if not activities_for_day:
        return [], 1

    # Sort activities by start time
    sorted_activities = sorted(activities_for_day, key=lambda x: x['start_slot'])
    
    # Identify groups of overlapping activities
    groups = []
    if sorted_activities:
        current_group = [sorted_activities[0]]
        for activity in sorted_activities[1:]:
            # Check if this activity overlaps with the *time range* of the current group
            group_end_time = max(act['end_slot'] for act in current_group)
            if activity['start_slot'] < group_end_time:
                current_group.append(activity)
            else:
                groups.append(current_group)
                current_group = [activity]
        groups.append(current_group)

    max_day_cols = 1
    # Process each group to assign column indices
    for group in groups:
        # For each time slot, find the max number of overlapping events within this group
        max_overlap_in_group = 0
        min_start = min(act['start_slot'] for act in group)
        max_end = max(act['end_slot'] for act in group)

        for slot in range(min_start, max_end):
            count = sum(1 for act in group if act['start_slot'] <= slot < act['end_slot'])
            if count > max_overlap_in_group:
                max_overlap_in_group = count
        
        if max_overlap_in_group > max_day_cols:
            max_day_cols = max_overlap_in_group

        # Assign column index and span within the group
        for activity in group:
            activity['total_cols_in_group'] = max_overlap_in_group
            
        # More sophisticated column assignment within the group
        group.sort(key=lambda x: x['start_slot'])
        for i, activity in enumerate(group):
            # Find available column index
            taken_cols = set()
            for j in range(i):
                prev_act = group[j]
                # Check if prev_act overlaps with current activity
                if max(activity['start_slot'], prev_act['start_slot']) < min(activity['end_slot'], prev_act['end_slot']):
                    if 'col_index' in prev_act:
                        taken_cols.add(prev_act['col_index'])
            
            col = 0
            while col in taken_cols:
                col += 1
            activity['col_index'] = col

    # Final pass: non-overlapping events should span all columns
    all_processed_activities = []
    for group in groups:
        for activity in group:
            if activity['total_cols_in_group'] == 1:
                activity['col_span'] = max_day_cols
            else:
                activity['col_span'] = 1
            all_processed_activities.append(activity)

    return sorted(all_processed_activities, key=lambda x: x['start_slot']), max_day_cols


def process_schedule_data(activities):
    """
    Processes activities to prepare data for grid rendering, including overlap calculation.
    Returns activities grouped by day and max columns needed per day.
    """
    num_slots = 48 # 00:00-23:30
    
    # Group activities by day
    activities_by_day = {i: [] for i in range(7)}
    for activity in activities:
        # Handle activities crossing midnight - assign them to the start day for layout calculation
        # The end_slot might be > 47, which is handled by the duration calculation
        activities_by_day[activity['day']].append(activity)

    # Calculate overlap layout for each day
    processed_activities_by_day = []
    max_day_cols = [1] * 7 # Default to 1 column per day

    for day_index in range(7):
        day_activities, current_max_cols = calculate_overlap_layout(activities_by_day[day_index])
        processed_activities_by_day.append(day_activities)
        max_day_cols[day_index] = current_max_cols

    return {
        'day_activities': processed_activities_by_day,
        'max_day_cols': max_day_cols,
    }


@app.route('/api/generate', methods=['POST'])
def api_generate():
    try:
        data = request.get_json()
        schedule_input = data.get('schedule_input', '')
        
        parsed_data = parse_schedule_input(schedule_input)
        session['schedule_data'] = parsed_data # Store parsed data

        processed_data = process_schedule_data(parsed_data['activities'])
        session['processed_schedule_data'] = processed_data # Store processed data

        # Frontend will now render based on processed_data
        return jsonify({"status": "success", "data": processed_data})

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        # Log the full traceback for debugging
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": f"伺服器內部錯誤: {str(e)}"}), 500

@app.route('/api/export/ics')
def export_ics():
    # ICS export logic remains largely the same, it uses the original parsed activities
    if 'schedule_data' not in session:
        return "錯誤：週習表資訊不存在。請先生成週習表。", 400

    schedule_data = session['schedule_data']
    activities = schedule_data['activities']
    config = schedule_data['config']
    
    tz = pytz.timezone('Asia/Taipei')
    cal = Calendar()
    
    today = datetime.now(tz).date()
    start_date = today
    
    repeat_months = config.get('ics_repeat_months', 6)
    end_year = today.year + (today.month + repeat_months - 1) // 12
    end_month = (today.month + repeat_months - 1) % 12 + 1
    last_day_of_month = calendar.monthrange(end_year, end_month)[1]
    end_day = min(today.day, last_day_of_month)
    end_date = date(end_year, end_month, end_day)

    activities_by_day = {i: [] for i in range(7)}
    for act in activities:
        activities_by_day[act['day']].append(act)

    current_date = start_date
    while current_date <= end_date:
        weekday = current_date.weekday()
        
        if weekday in activities_by_day:
            for activity in activities_by_day[weekday]:
                start_h = activity['start_slot'] // 2
                start_m = (activity['start_slot'] % 2) * 30
                
                # Handle activities crossing midnight for ICS export
                start_datetime = tz.localize(datetime.combine(current_date, time(start_h, start_m)))

                duration_in_slots = activity['end_slot'] - activity['start_slot']
                duration = timedelta(minutes=duration_in_slots * 30)
                end_datetime = start_datetime + duration

                e = Event()
                e.name = activity['name']
                e.begin = start_datetime
                e.end = end_datetime
                if activity['note']:
                    e.description = activity['note']
                
                cal.events.add(e)
        
        current_date += timedelta(days=1)

    return Response(
        str(cal),
        mimetype="text/calendar",
        headers={"Content-disposition": "attachment; filename=weekly_schedule.ics"}
    )


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)