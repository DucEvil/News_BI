-- Migration TH2: an toàn khi chạy lại, giữ nguyên dữ liệu và dashboard TH1.
CREATE TABLE IF NOT EXISTS ai_runs (
    id BIGSERIAL PRIMARY KEY, started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ, status TEXT NOT NULL, model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL, articles_selected INTEGER NOT NULL DEFAULT 0,
    articles_analyzed INTEGER NOT NULL DEFAULT 0, requests_made INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
    latency_seconds DOUBLE PRECISION NOT NULL DEFAULT 0, error_code TEXT
);
CREATE TABLE IF NOT EXISTS ai_daily_usage (
    usage_date DATE PRIMARY KEY, requests_made INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS article_ai (
    article_id BIGINT NOT NULL REFERENCES articles(id), model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL, input_hash CHAR(64) NOT NULL,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('positive','neutral','negative','mixed')),
    sentiment_score DOUBLE PRECISION NOT NULL CHECK (sentiment_score BETWEEN -1 AND 1),
    confidence DOUBLE PRECISION NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    topic TEXT NOT NULL, summary_vi TEXT NOT NULL, rationale_vi TEXT NOT NULL,
    language TEXT NOT NULL, analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    run_id BIGINT REFERENCES ai_runs(id), PRIMARY KEY(article_id,model_name,prompt_version)
);
CREATE INDEX IF NOT EXISTS idx_article_ai_analyzed_at ON article_ai(analyzed_at);
CREATE TABLE IF NOT EXISTS forecast_runs (
    id BIGSERIAL PRIMARY KEY, generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL, train_start DATE, train_end DATE, n_observations INTEGER NOT NULL,
    selected_model TEXT, metrics JSONB NOT NULL DEFAULT '{}'::jsonb, note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS news_forecasts (
    run_id BIGINT NOT NULL REFERENCES forecast_runs(id), forecast_date DATE NOT NULL,
    predicted_count DOUBLE PRECISION NOT NULL CHECK (predicted_count >= 0),
    model_name TEXT NOT NULL, PRIMARY KEY(run_id,forecast_date)
);
CREATE OR REPLACE VIEW v_ai_articles AS
WITH latest AS (
 SELECT DISTINCT ON (article_id) * FROM article_ai ORDER BY article_id,analyzed_at DESC
)
SELECT a.id,a.title,a.description,a.content,a.source_name,a.published_at,a.url,
       a.published_date_vn,b.sentiment,b.sentiment_score,b.confidence,b.topic,
       b.summary_vi,b.rationale_vi,b.language,b.model_name,b.analyzed_at,
       CASE WHEN b.article_id IS NULL THEN 'pending' ELSE 'analyzed' END AS analysis_status
FROM v_articles a LEFT JOIN latest b ON b.article_id=a.id;
CREATE OR REPLACE VIEW v_ai_analyzed AS SELECT * FROM v_ai_articles WHERE analysis_status='analyzed';
CREATE OR REPLACE VIEW v_ai_daily_activity AS
SELECT (analyzed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date AS analysis_date,
       count(*)::bigint AS analyzed_count
FROM v_ai_analyzed
GROUP BY (analyzed_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
CREATE OR REPLACE VIEW v_ai_source_coverage AS
SELECT source_name,count(*)::bigint AS total_articles,
       count(*) FILTER (WHERE analysis_status='analyzed')::bigint AS analyzed_articles,
       count(*) FILTER (WHERE analysis_status='pending')::bigint AS pending_articles,
       round(100.0*count(*) FILTER (WHERE analysis_status='analyzed')/count(*),2) AS coverage_percent
FROM v_ai_articles GROUP BY source_name;
CREATE OR REPLACE VIEW v_forecast_series AS
WITH latest AS (SELECT id FROM forecast_runs WHERE id=(SELECT max(id) FROM forecast_runs) AND status='success'), points AS (
 SELECT news_date,article_count::double precision AS observed_count,NULL::double precision AS predicted_count
 FROM v_daily_news
 UNION ALL
 SELECT f.forecast_date,NULL::double precision,f.predicted_count
 FROM news_forecasts f JOIN latest ON f.run_id=latest.id
)
SELECT news_date,max(observed_count) AS observed_count,max(predicted_count) AS predicted_count
FROM points GROUP BY news_date;
CREATE OR REPLACE VIEW v_forecast_metrics AS
SELECT r.id,r.generated_at,r.train_start,r.train_end,r.n_observations,r.selected_model,
       m.key AS model_name,(m.value->>'mae')::double precision AS mae,
       (m.value->>'smape')::double precision AS smape,(m.value->>'test_days')::int AS test_days,
       CASE WHEN (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date-r.train_end > 3
            THEN 'stale_data' ELSE 'fresh_data' END AS data_status,
       (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date-r.train_end AS data_lag_days
FROM forecast_runs r CROSS JOIN LATERAL jsonb_each(r.metrics) m
WHERE r.id=(SELECT max(id) FROM forecast_runs
            WHERE status IN ('success','stale_data') AND metrics <> '{}'::jsonb);
COMMENT ON VIEW v_ai_articles IS 'pending nghĩa là chưa có kết quả Gemini; không gán nhãn giả';
COMMENT ON VIEW v_forecast_series IS 'Dự báo số bài đã thu thập, không phải toàn bộ tin tức; thiếu ngày thu thập không gán 0';
COMMENT ON VIEW v_forecast_metrics IS 'Kiểm định lịch sử vẫn có giá trị khi dữ liệu cũ; hiển thị độ trễ, không coi đây là dự báo mới';
COMMENT ON VIEW v_ai_daily_activity IS 'Số bài theo ngày của bản phân tích gần nhất, múi giờ Việt Nam; không phải số request Gemini';
COMMENT ON VIEW v_ai_source_coverage IS 'Độ bao phủ là tỷ lệ bài có kết quả AI, không phải độ chính xác của mô hình';
