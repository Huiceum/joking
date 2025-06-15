# 【修改後的 app.py】

from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response
import os
import secrets
from datetime import datetime, timedelta, date, time
import re
import pytz
from ics import Calendar, Event
import calendar
from authlib.integrations.flask_client import OAuth
import google.generativeai as genai
from dotenv import load_dotenv
import sqlite3 # --- NEW: 引入 sqlite3 模組

class ReverseProxied(object):
    """
    一個 WSGI 中間件，用於修正反向代理後的 URL scheme。
    它會讀取 X-Forwarded-Proto 標頭並相應地更新 wsgi.url_scheme。
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        scheme = environ.get('HTTP_X_FORWARDED_PROTO')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)

# 在建立 app 實例之前載入 .env 檔案中的環境變數
load_dotenv()

app = Flask(__name__)
# SECRET_KEY 是 Flask session 加密和 Authlib 所必需的
# 現在 os.environ.get 可以讀取到 .env 檔案中的值了

app.wsgi_app = ReverseProxied(app.wsgi_app)
app.secret_key = os.environ.get('SECRET_KEY')
app.config['SERVER_NAME'] = os.environ.get('SERVER_NAME') # 用於生成絕對 URL

# --- NEW: 資料庫與使用限制設定 ---
DATABASE = 'usage.db'
MAX_AI_USAGE = 20  # 設定每個用戶最多能使用 20 次 AI

def get_db_connection():
    """建立並返回一個資料庫連線"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # 讓查詢結果可以像字典一樣存取
    return conn

def init_db():
    """初始化資料庫，如果 user_usage 表不存在則建立它"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_usage (
            email TEXT PRIMARY KEY,
            usage_count INTEGER NOT NULL DEFAULT 0,
            last_used TIMESTAMP NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized.")
# --- END NEW ---


# --- OAuth 設定 ---
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={'scope': 'openid email profile'},
    jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
)

# --- Gemini API 設定 ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- 核心業務邏輯函數 ---

def parse_schedule_input(input_text):
    """解析週習表輸入語法"""
    activities = []
    config = {'ics_repeat_months': 6} # 預設重複6個月
    
    day_map = {
        '一': 0, '二': 1, '三': 2, '四': 3, '五': 4, '六': 5, '日': 6,
        '週一': 0, '週二': 1, '週三': 2, '週四': 3, '週五': 4, '週六': 5, '週日': 6
    }
    
    # 修正：在正則表達式前加上 r，使其成為原始字串
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
    """計算重疊活動的佈局"""
    if not activities_for_day:
        return [], 1

    sorted_activities = sorted(activities_for_day, key=lambda x: x['start_slot'])
    
    groups = []
    if sorted_activities:
        current_group = [sorted_activities[0]]
        for activity in sorted_activities[1:]:
            group_end_time = max(act['end_slot'] for act in current_group)
            if activity['start_slot'] < group_end_time:
                current_group.append(activity)
            else:
                groups.append(current_group)
                current_group = [activity]
        groups.append(current_group)

    max_day_cols = 1
    for group in groups:
        max_overlap_in_group = 0
        min_start = min(act['start_slot'] for act in group)
        max_end = max(act['end_slot'] for act in group)

        for slot in range(min_start, max_end):
            count = sum(1 for act in group if act['start_slot'] <= slot < act['end_slot'])
            if count > max_overlap_in_group:
                max_overlap_in_group = count
        
        if max_overlap_in_group > max_day_cols:
            max_day_cols = max_overlap_in_group

        for activity in group:
            activity['total_cols_in_group'] = max_overlap_in_group
            
        group.sort(key=lambda x: x['start_slot'])
        for i, activity in enumerate(group):
            taken_cols = set()
            for j in range(i):
                prev_act = group[j]
                if max(activity['start_slot'], prev_act['start_slot']) < min(activity['end_slot'], prev_act['end_slot']):
                    if 'col_index' in prev_act:
                        taken_cols.add(prev_act['col_index'])
            
            col = 0
            while col in taken_cols:
                col += 1
            activity['col_index'] = col

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
    """處理活動數據以供前端渲染"""
    activities_by_day = {i: [] for i in range(7)}
    for activity in activities:
        activities_by_day[activity['day']].append(activity)

    processed_activities_by_day = []
    max_day_cols = [1] * 7

    for day_index in range(7):
        day_activities, current_max_cols = calculate_overlap_layout(activities_by_day[day_index])
        processed_activities_by_day.append(day_activities)
        max_day_cols[day_index] = current_max_cols

    return {
        'day_activities': processed_activities_by_day,
        'max_day_cols': max_day_cols,
    }

# --- 路由 (Routes) ---

# 修正：這是唯一的主頁路由
@app.route('/')
def index():
    # 將 session 傳遞給模板，以便前端判斷登入狀態
    return render_template('index.html', session=session.get('user'))

# 在 app.py 中找到 login 函數

@app.route('/login')
def login():
    # 重定向到 Google 登入頁面
    redirect_uri = url_for('callback', _external=True)
    
    # --- 除錯程式碼 ---
    # 這個 print 語句的輸出會顯示在 Render 的 Log 中
    print("="*50)
    print(f"RENDER SERVER is generating this redirect_uri: {redirect_uri}")
    print("="*50)
    # --- 除錯結束 ---
    
    return google.authorize_redirect(redirect_uri)

@app.route('/callback')
def callback():
    # 處理 Google 回調
    token = google.authorize_access_token()
    # 使用 google.parse_id_token() 更安全地解析用戶資訊
    user_info = google.parse_id_token(token, nonce=session.get('nonce'))
    session['user'] = user_info # 將用戶資訊存入 session
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user', None) # 清除 session 中的用戶資訊
    return redirect(url_for('index'))

# --- MODIFIED: 修改 /api/chat 路由以整合使用次數限制 ---
@app.route('/api/chat', methods=['POST'])
def api_chat():
    if 'user' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    # --- NEW: 檢查使用次數 ---
    user_email = session['user'].get('email')
    if not user_email:
        return jsonify({"error": "User email not found in session"}), 401

    conn = get_db_connection()
    user = conn.execute('SELECT usage_count FROM user_usage WHERE email = ?', (user_email,)).fetchone()
    
    current_usage = user['usage_count'] if user else 0

    if current_usage >= MAX_AI_USAGE:
        conn.close()
        # 使用 403 Forbidden 狀態碼表示權限問題 (已達上限)
        remaining_count = MAX_AI_USAGE - current_usage
        if remaining_count < 0:
            remaining_count = 0
        message = f"您好，您已達到 {MAX_AI_USAGE} 次的使用上限，剩餘次數：{remaining_count}。感謝您的使用！"
        return jsonify({"error": message}), 403

    # --- END NEW ---

    if not GEMINI_API_KEY:
        conn.close() # 如果 API Key 不存在，也要關閉連線
        return jsonify({"error": "Gemini API key not configured on the server."}), 500

    data = request.get_json()
    user_message = data.get('message')
    chat_history = data.get('history', [])

    if not user_message:
        conn.close() # 如果訊息為空，也要關閉連線
        return jsonify({"error": "Empty message"}), 400

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        system_prompt = {
            'role': 'user', 
            'parts': [
                "你是一位專業且友善的「生活週習表」諮詢師。你的目標是透過對話幫助使用者規劃他們的每週行程。當使用者提到具體的行程安排時，你必須嚴格按照以下格式將其總結在一個 Markdown 程式碼區塊中：\n"
                "```schedule\n"
                "[星期] [開始時間]-[結束時間] [活動名稱] [[備註]]\n"
                "```\n"
                "例如：\n"
                "```schedule\n"
                "週一 09:00-11:00 專案開發 [完成登入模塊]\n"
                "週三 14:00-15:00 團隊會議\n"
                "```\n"
                "請只在使用者明確提出行程安排時才使用此格式。對於一般對話，請自然地回應。"
            ]
        }
        model_greeting = {'role': 'model', 'parts': ["好的，我明白了。我會扮演好生活週習表諮詢師的角色，並在適當的時候使用指定的格式來總結行程。請問有什麼可以為您服務的嗎？"]}
        
        full_history = [system_prompt, model_greeting] + chat_history
        
        chat = model.start_chat(history=full_history)
        response = chat.send_message(user_message)
        
        # --- NEW: 成功呼叫後，更新使用次數 ---
        # 使用 UPSERT (UPDATE or INSERT) 語法
        # 如果 email 已存在，就將 usage_count + 1
        # 如果不存在，就插入一筆新的紀錄，usage_count 設為 1
        conn.execute('''
            INSERT INTO user_usage (email, usage_count, last_used)
            VALUES (?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(email) DO UPDATE SET
                usage_count = usage_count + 1,
                last_used = CURRENT_TIMESTAMP
        ''', (user_email,))
        conn.commit()
        # --- END NEW ---
        
        return jsonify({"reply": response.text})

    except Exception as e:
        app.logger.error(f"Gemini API error: {e}")
        return jsonify({"error": f"An error occurred with the AI service: {e}"}), 500
    finally:
        # --- NEW: 確保資料庫連線總是會被關閉 ---
        if conn:
            conn.close()

@app.route('/api/generate', methods=['POST'])
def api_generate():
    try:
        data = request.get_json()
        schedule_input = data.get('schedule_input', '')
        
        parsed_data = parse_schedule_input(schedule_input)
        session['schedule_data'] = parsed_data

        processed_data = process_schedule_data(parsed_data['activities'])
        session['processed_schedule_data'] = processed_data

        return jsonify({"status": "success", "data": processed_data})

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({"status": "error", "message": f"伺服器內部錯誤: {str(e)}"}), 500

@app.route('/api/export/ics')
def export_ics():
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
                
                start_datetime = tz.localize(datetime.combine(current_date, time(start_h, start_m)))
                duration = timedelta(minutes=(activity['end_slot'] - activity['start_slot']) * 30)
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

# --- 啟動設定 ---
if __name__ == '__main__':
    # --- NEW: 在應用程式啟動時初始化資料庫 ---
    init_db()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)