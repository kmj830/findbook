import json
import os
import sqlite3
from flask import Flask, render_template, request, jsonify

# Optional Supabase integration
try:
    from supabase import create_client, Client
except ImportError:
    create_client = None

app = Flask(__name__, template_folder='templates')

DB_PATH = os.path.join(os.path.dirname(__file__), 'completed.db')
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data.json')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '').strip()

supabase_client: Client | None = None
if SUPABASE_URL and SUPABASE_KEY and create_client:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(" Connected to Supabase successfully.")
    except Exception as e:
        print(f"⚠️ Supabase client initialization error: {e}")

def init_local_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS completed_books (
            reg_no TEXT PRIMARY KEY,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_local_db()

_cached_completed_set = None
_last_cache_time = 0

def get_completed_set(force_refresh=False) -> set:
    global _cached_completed_set, _last_cache_time
    import time
    now = time.time()
    
    # 2.5초 캐싱으로 반복 호출 시 0.001초 즉각 응답
    if not force_refresh and _cached_completed_set is not None and (now - _last_cache_time < 2.5):
        return _cached_completed_set
        
    if supabase_client:
        try:
            res = supabase_client.table('completed_books').select('reg_no').execute()
            if res and res.data is not None:
                _cached_completed_set = set(row['reg_no'] for row in res.data)
                _last_cache_time = now
                return _cached_completed_set
        except Exception as e:
            print(f"⚠️ Supabase fetch error: {e}")
    
    # Fallback to local SQLite DB
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('SELECT reg_no FROM completed_books')
        rows = cur.fetchall()
        conn.close()
        _cached_completed_set = set(r[0] for r in rows)
        _last_cache_time = now
        return _cached_completed_set
    except Exception as e:
        print(f"⚠️ SQLite fetch error: {e}")
        return set()

# Load precomputed data
with open(DATA_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

all_barcodes = data['all_barcodes']
line_sequences = data['line_sequences']
targets = data['targets']

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/targets')
def get_targets():
    completed_set = get_completed_set()
    
    sg_list = []
    pg_list = []
    completed_list = []
    
    for code, t in targets.items():
        item = dict(t)
        item['is_completed'] = (code in completed_set)
        
        if code in completed_set:
            completed_list.append(item)
        else:
            if t['type'] == '서가배열':
                sg_list.append(item)
            else:
                pg_list.append(item)
                
    sort_func = lambda x: (
        int(x['sub_line'].split('-')[0]) if x['sub_line'].split('-')[0].isdigit() else 999,
        int(x['sub_line'].split('-')[1]),
        x['sub_idx']
    )
    
    sg_list.sort(key=sort_func)
    pg_list.sort(key=sort_func)
    completed_list.sort(key=sort_func)
    
    total_count = len(targets)
    completed_count = len(completed_list)
    remaining_count = total_count - completed_count
    progress_pct = round((completed_count / total_count * 100), 1) if total_count > 0 else 0
    
    return jsonify({
        'success': True,
        'cloud_storage': (supabase_client is not None),
        'total_count': total_count,
        'completed_count': completed_count,
        'remaining_count': remaining_count,
        'progress_pct': progress_pct,
        'sg_list': sg_list,
        'pg_list': pg_list,
        'completed_list': completed_list
    })

@app.route('/api/toggle_complete', methods=['POST'])
def toggle_complete():
    req_data = request.get_json() or {}
    code = req_data.get('code', '').strip().upper()
    if not code:
        return jsonify({'success': False, 'error': '등록번호가 필요합니다.'})
    
    completed_set = get_completed_set()
    
    if code in completed_set:
        # Uncheck
        if supabase_client:
            try:
                supabase_client.table('completed_books').delete().eq('reg_no', code).execute()
            except Exception as e:
                print(f"⚠️ Supabase delete error: {e}")
        
        # Local SQLite sync
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('DELETE FROM completed_books WHERE reg_no = ?', (code,))
        conn.commit()
        conn.close()
        is_completed = False
    else:
        # Check as completed
        if supabase_client:
            try:
                supabase_client.table('completed_books').upsert({'reg_no': code}).execute()
            except Exception as e:
                print(f"⚠️ Supabase insert error: {e}")
        
        # Local SQLite sync
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('INSERT OR REPLACE INTO completed_books (reg_no) VALUES (?)', (code,))
        conn.commit()
        conn.close()
        is_completed = True
        
    global _cached_completed_set
    _cached_completed_set = None
    
    return jsonify({
        'success': True,
        'code': code,
        'is_completed': is_completed
    })

@app.route('/api/search')
def search():
    code = request.args.get('code', '').strip().upper()
    if not code:
        return jsonify({'success': False, 'error': '등록번호를 입력해주세요.'})
    
    if code not in all_barcodes:
        matches = [k for k in all_barcodes.keys() if code in k]
        if matches:
            code = matches[0]
        else:
            return jsonify({'success': False, 'error': f'바코드 [{code}]를 찾을 수 없습니다. 등록번호를 다시 확인해주세요.'})
    
    completed_set = get_completed_set()
    curr = all_barcodes[code]
    is_target = code in targets
    target_info = targets.get(code)
    is_curr_completed = (code in completed_set)
    
    sub_line = curr['sub_line']
    sub_seq = line_sequences.get(sub_line, [])
    
    targets_in_line = []
    for item in sub_seq:
        item_code = item['code']
        # ONLY consider uncompleted targets for distance and recommendations!
        if item_code in targets and item_code not in completed_set:
            diff = item['sub_idx'] - curr['sub_idx']
            distance = abs(diff)
            
            if diff == 0:
                direction_text = '🎯 바로 현재 이 책입니다!'
                direction_badge = '현재 도서'
            elif diff > 0:
                direction_text = f'➡️ 뒤로 {diff}번째 책 ({diff}권 뒤)'
                direction_badge = f'뒤로 {diff}권'
            else:
                direction_text = f'⬅️ 앞으로 {-diff}번째 책 ({-diff}권 앞)'
                direction_badge = f'앞으로 {-diff}권'
                
            targets_in_line.append({
                'reg_no': item_code,
                'diff': diff,
                'distance': distance,
                'direction_text': direction_text,
                'direction_badge': direction_badge,
                'info': targets[item_code],
                'loc_desc': item['loc_desc'],
                'sub_idx': item['sub_idx']
            })
    
    targets_in_line_by_distance = sorted(targets_in_line, key=lambda x: x['distance'])
    targets_in_line_by_position = sorted(targets_in_line, key=lambda x: x['sub_idx'])
    
    closest_prev = None
    closest_next = None
    for t in targets_in_line_by_position:
        if t['diff'] < 0:
            closest_prev = t
        elif t['diff'] > 0 and closest_next is None:
            closest_next = t
            
    return jsonify({
        'success': True,
        'query_code': code,
        'current_book': curr,
        'is_target': is_target,
        'target_info': target_info,
        'is_curr_completed': is_curr_completed,
        'targets_count_in_line': len(targets_in_line),
        'closest_prev': closest_prev,
        'closest_next': closest_next,
        'targets_by_distance': targets_in_line_by_distance,
        'targets_by_position': targets_in_line_by_position
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
