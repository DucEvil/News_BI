"""Xuất số liệu thực tế và mẫu bài báo để đối chiếu bài nộp; không xuất bí mật."""
import json
from datetime import datetime, timezone
from pathlib import Path
from collect_news import connect_db

target = Path('/app/output')
target.mkdir(parents=True, exist_ok=True)
conn = connect_db()
try:
    with conn.cursor() as cur:
        cur.execute('''SELECT count(*),count(DISTINCT source_name),min(published_at),max(published_at),
                       count(*) FILTER (WHERE content IS NULL OR trim(content) = '') FROM articles''')
        total, sources, first, last, missing_content = cur.fetchone()
        if not total:
            raise SystemExit('Chưa có dữ liệu thật để xuất báo cáo.')
        cur.execute('SELECT news_date,article_count FROM v_daily_news_complete ORDER BY news_date')
        days = [{'date': str(day), 'articles': count} for day, count in cur.fetchall()]
        cur.execute('SELECT source_name,article_count FROM v_source_news ORDER BY article_count DESC,source_name')
        all_sources = [{'source': name, 'articles': count} for name, count in cur.fetchall()]
        cur.execute('SELECT count(*)-count(DISTINCT url_hash) FROM articles')
        duplicates = cur.fetchone()[0]
        assert sum(day['articles'] for day in days) == total
        assert sum(source['articles'] for source in all_sources) == total
        assert duplicates == 0
        cur.execute('''SELECT id,started_at,finished_at,status,requests_made,articles_received,
                       articles_inserted,articles_skipped,capped_windows,error_code
                       FROM collection_runs ORDER BY id DESC LIMIT 10''')
        names = [column.name for column in cur.description]
        runs = [dict(zip(names, row)) for row in cur.fetchall()]
        cur.execute('''SELECT title,description,content,source_name,published_at,url
                       FROM articles ORDER BY published_at DESC LIMIT 20''')
        names = [column.name for column in cur.description]
        sample = [dict(zip(names, row)) for row in cur.fetchall()]
finally:
    conn.close()

generated = datetime.now(timezone.utc).isoformat()
summary = {'generated_at_utc': generated, 'keyword': 'Vietnam', 'articles': total,
           'sources': sources, 'first_publication_utc': first, 'last_publication_utc': last,
           'missing_content': missing_content, 'duplicate_urls': duplicates,
           'daily_counts_vn': days, 'source_counts': all_sources, 'collection_runs': runs}
for filename, data in [('verification.json', summary), ('articles_sample.json', sample)]:
    (target / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
peak = max(day['articles'] for day in days)
peak_days = ', '.join(day['date'] for day in days if day['articles'] == peak)
top = all_sources[0]
markdown = f'''# Báo cáo thực hành: Theo dõi và phân tích tin tức Việt Nam

Thời điểm xuất số liệu (UTC): {generated}

## Mục tiêu và kiến trúc

Thu thập tin có từ khóa `Vietnam` qua NewsAPI bằng Python, làm sạch dữ liệu,
lưu vào PostgreSQL 16 và phân tích trên Apache Superset 5.0.0.
Luồng dữ liệu: NewsAPI → Python → PostgreSQL → Superset.

## Kết quả từ dữ liệu thực tế

- Tổng số bài đã lưu: **{total}**.
- Số nguồn khác nhau: **{sources}**.
- Thời điểm xuất bản sớm nhất (UTC): {first}.
- Thời điểm xuất bản muộn nhất (UTC): {last}.
- Ngày có nhiều bài đã lưu nhất (giờ Việt Nam): **{peak_days}**, **{peak} bài**.
- Nguồn có nhiều bài đã lưu nhất: **{top['source']}**, **{top['articles']} bài**.
- Bài không có nội dung rút gọn: {missing_content}.
- Bản ghi trùng theo URL đã chuẩn hóa: **{duplicates}**.
- Tổng theo ngày và tổng theo nguồn đều khớp tổng bài trong bảng `articles`.

## Thiết kế dữ liệu

Bảng `articles` lưu tiêu đề, mô tả, nội dung rút gọn, nguồn, ngày xuất bản,
URL, tác giả, ảnh và thời điểm thu thập. `url_hash` có ràng buộc UNIQUE;
`ON CONFLICT DO NOTHING` chống trùng khi chạy lại. `collection_runs` lưu
nhật ký thu thập, `api_daily_usage` theo dõi ngân sách request của dự án.
Các views phân tích tính ngày theo `Asia/Ho_Chi_Minh` (UTC+7).

## Đối chiếu checklist của đề

| Yêu cầu | Kết quả |
|---|---|
| Python gọi NewsAPI với từ khóa Vietnam | Đã thu thập dữ liệu thật, xem `collection_runs` |
| Lưu tiêu đề, nội dung, nguồn, ngày xuất bản | Đã lưu trong bảng `articles`; mẫu ở `articles_sample.json` |
| Cài và kết nối Apache Superset | Dịch vụ hoạt động, kết nối PostgreSQL và hai datasets |
| Dashboard theo thời gian và nguồn phổ biến | Sáu biểu đồ; bằng chứng truy vấn ở `superset_checks.json` |

## Dashboard

1. Tổng số bài đã lưu.
2. Số nguồn tin.
3. Số bài theo ngày Việt Nam.
4. Top 10 nguồn có nhiều bài nhất.
5. Tỷ trọng bài theo toàn bộ nguồn.
6. Danh sách tiêu đề, nguồn, thời gian, mô tả và URL bài báo.

Địa chỉ: http://localhost:8088/superset/dashboard/tin-tuc-viet-nam/

## Phạm vi và giới hạn

Kết quả phản ánh các bài đã thu thập với từ khóa `Vietnam`; có thể gồm tin
quốc tế nói về Việt Nam. NewsAPI không hỗ trợ bộ lọc `language=vi` và chỉ
cung cấp nội dung rút gọn tới 200 ký tự, có thể không có trường `content`.
Ngày bằng 0 nghĩa là chưa lưu bài, không chứng minh thực tế không có tin.
Gói Developer có độ trễ; giới hạn số trang có thể khiến lần thu thập ở trạng
thái `partial`. Số bài theo nguồn không đo lượt đọc hay độ tin cậy.

## Bằng chứng đối chiếu

- `verification.json`: tổng bài, ngày, nguồn và 10 nhật ký thu thập gần nhất.
- `articles_sample.json`: tối đa 20 bài thật để kiểm tra các trường lưu trữ.
- `superset_checks.json`: kết quả đăng nhập, truy vấn sáu biểu đồ, kiểm tra tổng và Top 10.
- `dashboard.png`, `dashboard_sources.png`: ảnh giao diện có dữ liệu thật.

Tài liệu: [NewsAPI](https://newsapi.org/docs/endpoints/everything),
[Apache Superset](https://superset.apache.org/docs/installation/docker-compose/).
'''
markdown += '\n## Số bài theo ngày Việt Nam\n\n| Ngày | Số bài đã lưu |\n|---|---:|\n'
markdown += ''.join(f"| {day['date']} | {day['articles']} |\n" for day in days)
markdown += '\n## Top 10 nguồn trong dữ liệu đã lưu\n\n| Nguồn | Số bài |\n|---|---:|\n'
markdown += ''.join(f"| {source['source'].replace('|', '/')} | {source['articles']} |\n" for source in all_sources[:10])
(target / 'BAO_CAO.md').write_text(markdown, encoding='utf-8')
print(f'Đã xuất output/BAO_CAO.md, verification.json và articles_sample.json: {total} bài, {sources} nguồn.')
