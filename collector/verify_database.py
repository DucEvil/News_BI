"""Kiểm tra dữ liệu thật sau khi thu thập, không gọi NewsAPI."""
from collect_news import connect_db

conn = connect_db()
try:
    with conn.cursor() as cur:
        cur.execute('SELECT count(*),count(DISTINCT source_name),min(published_at),max(published_at) FROM articles')
        count, sources, first, last = cur.fetchone()
        print(f'Tổng bài: {count}; tổng nguồn: {sources}; từ {first} đến {last}')
        cur.execute('SELECT coalesce(sum(article_count),0) FROM v_daily_news_complete')
        assert cur.fetchone()[0] == count, 'Tổng biểu đồ ngày không khớp tổng bài'
        cur.execute('SELECT coalesce(sum(article_count),0) FROM v_source_news')
        assert cur.fetchone()[0] == count, 'Tổng theo nguồn không khớp tổng bài'
        cur.execute('SELECT count(*) FROM articles WHERE title IS NULL OR published_at IS NULL OR source_name IS NULL')
        assert cur.fetchone()[0] == 0, 'Có dữ liệu thiếu trường bắt buộc'
        cur.execute('SELECT id,status,requests_made,articles_received,articles_inserted,capped_windows,error_code FROM collection_runs ORDER BY id DESC LIMIT 5')
        print('5 lần thu thập gần nhất (id, trạng thái, requests, nhận, thêm mới, khoảng bị giới hạn, lỗi):')
        for row in cur.fetchall():
            print(row)
        if count == 0:
            raise SystemExit('Chưa có bài báo: xem nhật ký trước khi đánh dấu checklist hoàn thành.')
        print('ĐẠT: tổng số bài theo ngày/nguồn khớp với bảng articles.')
finally:
    conn.close()
