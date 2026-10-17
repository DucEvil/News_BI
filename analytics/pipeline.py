"""Worker TH2: cache theo đầu vào/mô hình/prompt, giới hạn request và lịch tùy chọn."""
import argparse
import json
import logging
import os
import time
from analytics.common import connect_db,migrate,project_status,write_json
from analytics.gemini import PROMPT_VERSION,GeminiError,analyze_batch,input_hash

LOG = logging.getLogger('news-ai')


def run_ai(limit=None):
    model = os.environ.get('GEMINI_MODEL','gemini-3.5-flash-lite').strip()
    key = os.environ.get('GEMINI_API_KEY','').strip()
    limit = int(os.environ.get('AI_MAX_ARTICLES_PER_RUN','20')) if limit is None else limit
    batch_size = int(os.environ.get('AI_BATCH_SIZE','5'))
    budget = int(os.environ.get('AI_DAILY_REQUEST_BUDGET','20'))
    if not 1<=limit<=500 or not 1<=batch_size<=10 or not 1<=budget<=1000:
        raise ValueError('invalid_ai_configuration')
    conn = connect_db()
    conn.autocommit=True
    cur = conn.cursor()
    run_id = None
    state = {'status':'running','model':model,'articles_selected':0,'articles_analyzed':0,
             'requests_made':0,'input_tokens':0,'output_tokens':0,'error_code':None}
    started = time.monotonic()
    try:
        cur.execute('SELECT pg_try_advisory_lock(80321002)')
        if not cur.fetchone()[0]:
            return {'status':'already_running'}
        cur.execute('INSERT INTO ai_runs(status,model_name,prompt_version) VALUES(%s,%s,%s) RETURNING id',
                    ('running',model,PROMPT_VERSION))
        run_id = cur.fetchone()[0]
        if not key:
            state['status']='waiting_key'
            state['error_code']='missing_gemini_key'
            return state
        # Kiểm tra hash trong Python vì input có giới hạn độ dài và phải giống payload gửi Gemini.
        cur.execute('''SELECT a.id,a.title,a.description,a.content,b.input_hash FROM articles a
                       LEFT JOIN article_ai b ON b.article_id=a.id AND b.model_name=%s AND b.prompt_version=%s
                       ORDER BY a.published_at DESC,a.id DESC''',(model,PROMPT_VERSION))
        rows = []
        for values in cur.fetchall():
            row = dict(zip(['id','title','description','content','stored_hash'],values))
            row['input_hash']=input_hash(row)
            if row['stored_hash']!=row['input_hash']:
                rows.append(row)
                if len(rows)>=limit:
                    break
        state['articles_selected']=len(rows)
        for offset in range(0,len(rows),batch_size):
            batch=rows[offset:offset+batch_size]
            cur.execute('''INSERT INTO ai_daily_usage VALUES((now() AT TIME ZONE 'UTC')::date,1)
                           ON CONFLICT(usage_date) DO UPDATE SET requests_made=ai_daily_usage.requests_made+1
                           WHERE ai_daily_usage.requests_made < %s RETURNING requests_made''',(budget,))
            if cur.fetchone() is None:
                raise GeminiError('ai_daily_budget_exhausted')
            state['requests_made']+=1
            results,usage=analyze_batch(batch,key,model)
            state['input_tokens']+=usage['input_tokens']
            state['output_tokens']+=usage['output_tokens']
            hashes={row['id']:row['input_hash'] for row in batch}
            # Toàn batch chỉ ghi sau khi tất cả kết quả đã qua validation.
            with conn:
                for row in results:
                    cur.execute('''INSERT INTO article_ai(article_id,model_name,prompt_version,input_hash,sentiment,
                         sentiment_score,confidence,topic,summary_vi,rationale_vi,language,run_id)
                         VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                         ON CONFLICT(article_id,model_name,prompt_version) DO UPDATE SET
                         input_hash=excluded.input_hash,sentiment=excluded.sentiment,sentiment_score=excluded.sentiment_score,
                         confidence=excluded.confidence,topic=excluded.topic,summary_vi=excluded.summary_vi,
                         rationale_vi=excluded.rationale_vi,language=excluded.language,run_id=excluded.run_id,analyzed_at=now()''',
                         (row['id'],model,PROMPT_VERSION,hashes[row['id']],row['sentiment'],row['sentiment_score'],
                          row['confidence'],row['topic'],row['summary_vi'],row['rationale_vi'],row['language'],run_id))
            state['articles_analyzed']+=len(results)
        state['status']='success'
    except Exception as exc:
        state['status']='partial' if state['articles_analyzed'] else 'error'
        state['error_code']=str(exc) if isinstance(exc,GeminiError) else type(exc).__name__
    finally:
        state['latency_seconds']=round(time.monotonic()-started,3)
        try:
            if run_id:
                cur.execute('''UPDATE ai_runs SET finished_at=now(),status=%s,articles_selected=%s,
                    articles_analyzed=%s,requests_made=%s,input_tokens=%s,output_tokens=%s,latency_seconds=%s,error_code=%s WHERE id=%s''',
                    (state['status'],state['articles_selected'],state['articles_analyzed'],state['requests_made'],
                     state['input_tokens'],state['output_tokens'],state['latency_seconds'],state['error_code'],run_id))
        finally:
            cur.close()
            conn.close()
    return state


def run_once(limit=None):
    from analytics.forecast import run_forecast
    from analytics.evaluation import evaluate
    from analytics.report import export_report
    migrate()
    result=run_ai(limit)
    LOG.info('AI: %s',json.dumps(result,ensure_ascii=False))
    forecast=run_forecast()
    evaluation=evaluate()
    result={'ai':result,'forecast':forecast,'evaluation':evaluation,'database':project_status()}
    write_json('pipeline_status.json',result)
    export_report(result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--loop',action='store_true')
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    interval=int(os.environ.get('AI_INTERVAL_SECONDS','21600'))
    if args.loop and interval<3600:
        parser.error('AI interval must be at least 3600 seconds')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    while True:
        try:
            result=run_once(args.limit)
        except Exception as exc:
            LOG.error('Pipeline failed: %s',type(exc).__name__)
            if not args.loop:
                return 1
        else:
            if not args.loop:
                return 1 if result['ai']['status'] in ('error','partial') else 0
        LOG.info('Next AI run in %s seconds',interval)
        time.sleep(interval)


if __name__=='__main__':
    raise SystemExit(main())
