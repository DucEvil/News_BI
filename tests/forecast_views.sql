-- Regression test on migrated PostgreSQL. Test rows are always rolled back.
\set ON_ERROR_STOP on
BEGIN;
DO $$
DECLARE
    run_id bigint;
    stale_id bigint;
    today date := (now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date;
    scores jsonb := '{"last_value":{"mae":8.4,"smape":11.2,"test_days":5},"moving_average_7":{"mae":11.8,"smape":14.8,"test_days":5},"linear_trend":{"mae":10.5,"smape":13.2,"test_days":5}}';
BEGIN
    INSERT INTO forecast_runs(status,train_start,train_end,n_observations,selected_model,metrics,note)
    VALUES ('stale_data',today-27,today-6,22,'last_value',scores,'Regression test; rolled back')
    RETURNING id INTO stale_id;
    IF (SELECT count(*) FROM v_forecast_metrics WHERE id=stale_id
        AND data_status='stale_data' AND data_lag_days=6) <> 3 THEN
        RAISE EXCEPTION 'Stale historical backtest must retain all three models';
    END IF;
    INSERT INTO news_forecasts VALUES (stale_id,today+1,99,'last_value');
    IF EXISTS (SELECT 1 FROM v_forecast_series WHERE predicted_count IS NOT NULL) THEN
        RAISE EXCEPTION 'Stale runs must not expose new predictions';
    END IF;

    INSERT INTO forecast_runs(status,n_observations,metrics,note)
    VALUES ('insufficient_data',0,'{}','Regression test; rolled back');
    IF (SELECT count(*) FROM v_forecast_metrics WHERE id=stale_id) <> 3 THEN
        RAISE EXCEPTION 'An empty later run must not erase the last backtest';
    END IF;

    INSERT INTO forecast_runs(status,train_start,train_end,n_observations,selected_model,metrics,note)
    VALUES ('success',today-22,today-1,22,'last_value',scores,'Regression test; rolled back')
    RETURNING id INTO run_id;
    INSERT INTO news_forecasts VALUES (run_id,today+1,77,'last_value');
    IF (SELECT count(*) FROM v_forecast_metrics WHERE id=run_id
        AND data_status='fresh_data' AND data_lag_days=1) <> 3 THEN
        RAISE EXCEPTION 'Fresh runs must replace the historical backtest';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM v_forecast_series WHERE news_date=today+1 AND predicted_count=77) THEN
        RAISE EXCEPTION 'A successful run must expose its prediction';
    END IF;
END $$;
ROLLBACK;
