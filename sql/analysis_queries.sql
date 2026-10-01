-- Có thể dán từng truy vấn vào SQL Lab của Superset.
-- 1. Số bài đã lưu theo ngày Việt Nam (gồm ngày chưa có bài trong khoảng đã lưu).
SELECT news_date, article_count FROM v_daily_news_complete ORDER BY news_date;

-- 2. Mười nguồn có nhiều bài đã lưu nhất.
SELECT source_name, count(*) AS so_bai
FROM articles GROUP BY source_name ORDER BY so_bai DESC, source_name LIMIT 10;

-- 3. Tỷ trọng từng nguồn trong toàn bộ dữ liệu đã lưu.
SELECT source_name, count(*) AS so_bai,
       round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS ty_trong_phan_tram
FROM articles GROUP BY source_name ORDER BY so_bai DESC;

-- 4. Kiểm tra chống trùng: kết quả phải rỗng.
SELECT url_hash, count(*) FROM articles GROUP BY url_hash HAVING count(*) > 1;

-- 5. Nhật ký thu thập và giới hạn kết quả.
SELECT id, started_at, finished_at, status, requests_made, articles_received,
       articles_inserted, articles_skipped, capped_windows, error_code
FROM collection_runs ORDER BY id DESC LIMIT 20;

-- 6. Ngân sách API bộ mã này đã dùng (không gồm request từ ứng dụng khác).
SELECT * FROM api_daily_usage ORDER BY usage_date DESC;
