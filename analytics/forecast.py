"""Dự báo lượng BÀI ĐÃ LƯU; backtest theo thời gian, không gán ngày mất dữ liệu bằng 0."""
import math
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from analytics.common import connect_db,write_json

METHODS = ('last_value','moving_average_7','linear_trend')


def predict(history, target, method):
    if not history:
        raise ValueError('empty_history')
    if method=='last_value':
        value = history[-1][1]
    elif method=='moving_average_7':
        values = [count for _,count in history[-7:]]
        value = sum(values)/len(values)
    elif method=='linear_trend':
        origin = history[0][0]
        x = [(day-origin).days for day,_ in history]
        y = [count for _,count in history]
        mx,my = sum(x)/len(x),sum(y)/len(y)
        denominator = sum((v-mx)**2 for v in x)
        slope = sum((v-mx)*(w-my) for v,w in zip(x,y))/denominator if denominator else 0
        value = my+slope*((target-origin).days-mx)
    else:
        raise ValueError('unknown_forecast_model')
    return max(0.0,float(value))


def backtest(history):
    if len(history)<10:
        raise ValueError('insufficient_observed_days')
    holdout = min(5,len(history)-7)
    scores = {}
    for method in METHODS:
        errors,smape = [],[]
        for i in range(len(history)-holdout,len(history)):
            day,actual = history[i]
            estimate = predict(history[:i],day,method)
            errors.append(abs(actual-estimate))
            denominator = abs(actual)+abs(estimate)
            smape.append(200*abs(actual-estimate)/denominator if denominator else 0)
        scores[method] = {'mae':sum(errors)/holdout,'smape':sum(smape)/holdout,'test_days':holdout}
    selected = min(METHODS,key=lambda m:scores[m]['mae'])
    return selected,scores


def run_forecast(horizon=7):
    if not 1<=horizon<=14:
        raise ValueError('invalid_forecast_horizon')
    today = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    note = ('Dự báo số bài đã lưu, không phải toàn bộ tin tức. Bỏ ngày biên đầu/cuối để giảm ảnh hưởng '
            'cửa sổ thu thập cắt ngày; không điền 0 cho ngày mất dữ liệu. Backtest rolling-origin, '
            'mỗi bước chỉ dùng dữ liệu quá khứ. Giới hạn trang/API và ngày không chạy máy gây thiên lệch. '
            'Sai số trên số ngày kiểm tra ít có độ bất định cao; không suy diễn tính ổn định dài hạn.')
    with connect_db() as conn,conn.cursor() as cur:
        cur.execute('SELECT news_date,article_count FROM v_daily_news WHERE news_date < %s ORDER BY news_date',(today,))
        observed = [(day,int(count)) for day,count in cur.fetchall()]
        history = observed[1:-1][-28:]
        result = {'status':'insufficient_data','note':note,'n_observations':len(history),'horizon_days':horizon}
        if len(history)>=10:
            selected,scores = backtest(history)
            stale_days = (today-history[-1][0]).days
            result.update({'status':'stale_data' if stale_days>3 else 'success',
                'train_start':history[0][0],'train_end':history[-1][0],
                'data_lag_days':stale_days,'selected_model':selected,'metrics':scores})
        else:
            scores,selected = {},None
        import json
        cur.execute('''INSERT INTO forecast_runs(status,train_start,train_end,n_observations,selected_model,metrics,note)
                       VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING id''',
            (result['status'],history[0][0] if history else None,history[-1][0] if history else None,
             len(history),selected,json.dumps(scores),note))
        run_id = cur.fetchone()[0]
        result['run_id'] = run_id
        result['forecasts'] = []
        if result['status']=='success':
            for step in range(1,horizon+1):
                day = today+timedelta(days=step)
                estimate = round(predict(history,day,selected),2)
                cur.execute('INSERT INTO news_forecasts VALUES(%s,%s,%s,%s)',(run_id,day,estimate,selected))
                result['forecasts'].append({'date':day,'predicted_count':estimate})
    write_json('forecast_evaluation.json',result)
    return result
