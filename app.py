import json
import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__, template_folder='templates')

# Load precomputed data
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data.json')
with open(DATA_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

all_barcodes = data['all_barcodes']
line_sequences = data['line_sequences']
targets = data['targets']

@app.route('/')
def index():
    target_list = sorted(list(targets.values()), key=lambda x: (
        int(x['sub_line'].split('-')[0]) if x['sub_line'].split('-')[0].isdigit() else 999,
        int(x['sub_line'].split('-')[1]),
        x['sub_idx']
    ))
    return render_template('index.html', target_list=target_list, total_targets_count=len(targets))

@app.route('/healthz')
def healthz():
    return jsonify({'status': 'ok'})

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
    
    curr = all_barcodes[code]
    is_target = code in targets
    target_info = targets.get(code)
    
    sub_line = curr['sub_line']
    sub_seq = line_sequences.get(sub_line, [])
    
    targets_in_line = []
    for item in sub_seq:
        item_code = item['code']
        if item_code in targets:
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
        'targets_count_in_line': len(targets_in_line),
        'closest_prev': closest_prev,
        'closest_next': closest_next,
        'targets_by_distance': targets_in_line_by_distance,
        'targets_by_position': targets_in_line_by_position
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
