"""Kết nối dùng chung; không in API key, mật khẩu hoặc nội dung phản hồi lỗi."""
import json
import os
from pathlib import Path
from collect_news import connect_db

OUTPUT = Path(os.environ.get('TH2_OUTPUT_DIR', '/app/output/th2'))


def write_json(name, value):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / name
    temporary = target.with_suffix(target.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporary.replace(target)


def migrate():
    path = Path(os.environ.get('AI_SCHEMA_PATH', '/app/sql/002_ai.sql'))
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute(path.read_text(encoding='utf-8'))


def project_status():
    with connect_db() as conn, conn.cursor() as cur:
        cur.execute('SELECT count(*), count(*) FILTER (WHERE analysis_status=\'analyzed\') FROM v_ai_articles')
        total, analyzed = cur.fetchone()
        cur.execute('SELECT id,status,model_name,articles_analyzed,error_code,finished_at FROM ai_runs ORDER BY id DESC LIMIT 1')
        row = cur.fetchone()
        latest = dict(zip(['id','status','model','analyzed','error_code','finished_at'],row)) if row else None
    return {'articles': total, 'analyzed': analyzed, 'pending': total-analyzed,
            'coverage_percent': round(100*analyzed/total,2) if total else 0,
            'gemini_key_configured': bool(os.environ.get('GEMINI_API_KEY','').strip()), 'latest_ai_run': latest}
