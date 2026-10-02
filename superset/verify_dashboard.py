"""Kiểm tra đăng nhập và truy vấn thật cho mọi biểu đồ đã lưu trong Superset."""
import json
import os
import requests
from superset.app import create_app
from superset import db

app = create_app()
with app.app_context():
    from superset.models.dashboard import Dashboard
    dashboard = db.session.query(Dashboard).filter_by(slug='tin-tuc-viet-nam').one()
    charts = [(chart.id, chart.slice_name) for chart in dashboard.slices]
    assert len(charts) == 6, 'Dashboard phải có đủ 6 biểu đồ'

session = requests.Session()
base = 'http://127.0.0.1:8088'
response = session.post(base + '/api/v1/security/login', json={
    'username': os.environ.get('SUPERSET_ADMIN_USERNAME', 'admin'),
    'password': os.environ['SUPERSET_ADMIN_PASSWORD'], 'provider': 'db', 'refresh': False,
}, timeout=30)
assert response.status_code == 200, f'Đăng nhập thất bại: HTTP {response.status_code}'
session.headers['Authorization'] = 'Bearer ' + response.json()['access_token']
results = []
chart_data = {}
for chart_id, title in sorted(charts):
    response = session.get(base + f'/api/v1/chart/{chart_id}/data/',
                           params={'force': 'true'}, timeout=90)
    assert response.status_code == 200, f'{title}: HTTP {response.status_code}: {response.text[:500]}'
    payload = response.json()['result']
    assert payload and all(item.get('status') == 'success' for item in payload), f'{title}: truy vấn thất bại'
    chart_data[title] = payload[0]['data']
    results.append({'id': chart_id, 'title': title, 'rows': len(payload[0]['data']),
                    'status': 'success'})
total = chart_data['Tổng số bài đã lưu'][0]['Số bài báo']
sources = chart_data['Số nguồn tin'][0]['Số nguồn tin']
assert sum(row['Số bài theo ngày'] for row in chart_data['Số bài theo ngày (giờ Việt Nam)']) == total
source_rows = chart_data['Tỷ trọng bài theo nguồn (toàn bộ nguồn)']
assert len(source_rows) == sources
assert sum(row['Số bài báo'] for row in source_rows) == total
top_rows = chart_data['10 nguồn có nhiều bài nhất']
expected = sorted(row['Số bài báo'] for row in source_rows)[-10:]
assert sorted(row['Số bài báo'] for row in top_rows) == expected, 'Top 10 không khớp các nguồn có nhiều bài nhất'
print(json.dumps({'dashboard': 'tin-tuc-viet-nam', 'login': 'success',
                  'articles': total, 'sources': sources, 'totals_match': True,
                  'top10_match': True, 'charts': results}, ensure_ascii=False))
