-- Dữ liệu tin tức và dữ liệu cấu hình Superset nằm trong hai database khác nhau.
CREATE DATABASE superset_meta OWNER news;

CREATE TABLE IF NOT EXISTS articles (
    id BIGSERIAL PRIMARY KEY,
    url_hash CHAR(64) NOT NULL UNIQUE,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    source_id TEXT,
    source_name TEXT NOT NULL,
    author TEXT,
    image_url TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    query_keyword TEXT NOT NULL,
    CONSTRAINT valid_title CHECK (length(trim(title)) > 0)
);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_source_name ON articles(source_name);

CREATE TABLE IF NOT EXISTS collection_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    query_keyword TEXT NOT NULL,
    from_at TIMESTAMPTZ NOT NULL,
    to_at TIMESTAMPTZ NOT NULL,
    requests_made INTEGER NOT NULL DEFAULT 0,
    articles_received INTEGER NOT NULL DEFAULT 0,
    articles_inserted INTEGER NOT NULL DEFAULT 0,
    articles_skipped INTEGER NOT NULL DEFAULT 0,
    capped_windows INTEGER NOT NULL DEFAULT 0,
    error_code TEXT
);

CREATE TABLE IF NOT EXISTS api_daily_usage (
    usage_date DATE PRIMARY KEY,
    requests_made INTEGER NOT NULL DEFAULT 0
);

-- Ngày phân tích theo Việt Nam, độc lập múi giờ hệ điều hành/container.
CREATE OR REPLACE VIEW v_articles AS
SELECT id, title, description, content, source_name, author, url,
       published_at, collected_at, query_keyword,
       (published_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS published_date_vn
FROM articles;

CREATE OR REPLACE VIEW v_daily_news AS
SELECT published_date_vn AS news_date, count(*)::bigint AS article_count
FROM v_articles GROUP BY published_date_vn;

CREATE OR REPLACE VIEW v_source_news AS
SELECT source_name, count(*)::bigint AS article_count
FROM articles GROUP BY source_name;

-- Dùng lịch liên tục để ngày không có dữ liệu lưu được hiển thị bằng 0.
CREATE OR REPLACE VIEW v_daily_news_complete AS
WITH bounds AS (
  SELECT min(published_date_vn) AS first_day, max(published_date_vn) AS last_day
  FROM v_articles
), calendar AS (
  SELECT generate_series(first_day::timestamp, last_day::timestamp, interval '1 day')::date AS news_date
  FROM bounds
)
SELECT c.news_date, coalesce(d.article_count, 0)::bigint AS article_count
FROM calendar c LEFT JOIN v_daily_news d USING (news_date);

COMMENT ON COLUMN articles.content IS 'Phần nội dung rút gọn do NewsAPI trả về, không phải toàn văn';
COMMENT ON VIEW v_daily_news_complete IS '0 nghĩa là không có bài đã lưu; không kết luận thực tế không có tin';
