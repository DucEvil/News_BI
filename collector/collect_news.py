"""Thu thập tin có từ khóa Vietnam. Khóa API chỉ được gửi qua HTTP header."""
import argparse
import hashlib
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
LOG = logging.getLogger('news-bi')
ENDPOINT = 'https://newsapi.org/v2/everything'


class CollectionError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def parse_timestamp(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso(value):
    return value.astimezone(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')


def day_windows(start, end):
    """Chia khoảng đóng thành từng ngày UTC; không chồng lấn ranh giới."""
    current = start.replace(microsecond=0)
    end = end.replace(microsecond=0)
    while current <= end:
        next_day = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        finish = min(end, next_day - timedelta(seconds=1))
        yield current, finish
        current = finish + timedelta(seconds=1)


def normalize_article(article, keyword):
    """Bỏ dữ liệu thiếu tiêu đề, URL hoặc ngày; giữ nguyên nội dung API trả về."""
    if not isinstance(article, dict):
        return None
    title = article.get('title')
    url = article.get('url')
    if not isinstance(title, str) or not title.strip() or title.strip() == '[Removed]':
        return None
    if not isinstance(url, str):
        return None
    url = url.strip()
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return None
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return None
    try:
        published = parse_timestamp(article.get('publishedAt') or '')
    except (ValueError, TypeError, AttributeError):
        return None
    source = article.get('source') or {}
    if not isinstance(source, dict):
        source = {}
    # Bỏ fragment (#...), giữ query string vì nó có thể định danh bài báo.
    canonical_url = urllib.parse.urlunsplit(parts._replace(fragment=''))
    name = source.get('name')
    if not isinstance(name, str) or not name.strip():
        name = parts.hostname
    return {
        'url_hash': hashlib.sha256(canonical_url.encode()).hexdigest(),
        'url': canonical_url, 'title': title.strip(),
        'description': article.get('description'), 'content': article.get('content'),
        'source_id': source.get('id'), 'source_name': name.strip(),
        'author': article.get('author'), 'image_url': article.get('urlToImage'),
        'published_at': published, 'query_keyword': keyword,
    }


def fetch_page(api_key, keyword, start, end, page, language='', opener=None):
    params = {'q': keyword, 'from': iso(start), 'to': iso(end),
              'sortBy': 'publishedAt', 'pageSize': 100, 'page': page}
    if language:
        params['language'] = language
    req = urllib.request.Request(
        ENDPOINT + '?' + urllib.parse.urlencode(params),
        headers={'X-Api-Key': api_key, 'User-Agent': 'VietnamNewsBIStudent/1.0'},
    )
    try:
        with (opener or urllib.request.urlopen)(req, timeout=45) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            code = json.loads(exc.read()).get('code') or 'http_' + str(exc.code)
        except (ValueError, AttributeError):
            code = 'http_' + str(exc.code)
        raise CollectionError(code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CollectionError('network_error') from None
    except ValueError:
        raise CollectionError('invalid_json') from None
    if not isinstance(data, dict):
        raise CollectionError('invalid_response')
    if data.get('status') != 'ok':
        raise CollectionError(data.get('code') or 'api_error')
    if not isinstance(data.get('articles'), list):
        raise CollectionError('invalid_articles')
    return data


def fetch_window(api_key, keyword, start, end, max_pages, language, reserve, save, stats, opener=None):
    for page in range(1, max_pages + 1):
        reserve()  # Dành ngân sách trước khi gửi request, kể cả request lỗi.
        stats['requests_made'] += 1
        try:
            data = fetch_page(api_key, keyword, start, end, page, language, opener)
        except CollectionError as exc:
            if exc.code == 'maximumResultsReached':
                stats['capped_windows'] += 1
                return
            raise
        articles = data['articles']
        stats['articles_received'] += len(articles)
        for article in articles:
            row = normalize_article(article, keyword)
            if row is None:
                stats['articles_skipped'] += 1
            else:
                stats['articles_inserted'] += save(row)
        total = int(data.get('totalResults') or 0)
        if len(articles) < 100 or total <= page * 100:
            return
        if page == max_pages:
            stats['capped_windows'] += 1


INSERT_SQL = '''
INSERT INTO articles(url_hash,url,title,description,content,source_id,source_name,
                     author,image_url,published_at,query_keyword)
VALUES (%(url_hash)s,%(url)s,%(title)s,%(description)s,%(content)s,%(source_id)s,
        %(source_name)s,%(author)s,%(image_url)s,%(published_at)s,%(query_keyword)s)
ON CONFLICT (url_hash) DO NOTHING RETURNING id
'''


def connect_db():
    import psycopg2  # Chỉ cần cài trong container; các kiểm tra logic dùng thư viện chuẩn.
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'postgres'),
        dbname=os.environ.get('DB_NAME', 'news_db'),
        user=os.environ.get('DB_USER', 'news'),
        password=os.environ['DB_PASSWORD'], connect_timeout=15,
    )


def collect(args):
    key = os.environ.get('NEWSAPI_KEY', '').strip()
    if not key:
        raise CollectionError('missing_api_key')
    keyword = os.environ.get('NEWS_QUERY', 'Vietnam')
    language = os.environ.get('NEWS_LANGUAGE', '').strip()
    if language == 'vi':
        raise CollectionError('unsupported_language_vi')
    end = parse_timestamp(args.to_at) if args.to_at else (
        datetime.now(UTC) - timedelta(hours=float(os.environ.get('NEWS_DELAY_HOURS', '25')))
    )
    start = parse_timestamp(args.from_at) if args.from_at else (
        end - timedelta(days=int(os.environ.get('LOOKBACK_DAYS', '7')))
    )
    max_pages = int(os.environ.get('MAX_PAGES_PER_DAY', '1'))
    budget = int(os.environ.get('DAILY_REQUEST_BUDGET', '80'))
    if start > end or max_pages < 1 or not 1 <= budget <= 100:
        raise CollectionError('invalid_configuration')
    stats = dict.fromkeys(['requests_made', 'articles_received', 'articles_inserted',
                           'articles_skipped', 'capped_windows'], 0)
    conn = connect_db()
    conn.autocommit = True
    cur = conn.cursor()
    run_id = None
    status = 'success'
    error_code = None
    try:
        cur.execute('SELECT pg_try_advisory_lock(80321001)')
        if not cur.fetchone()[0]:
            raise CollectionError('another_collector_is_running')
        cur.execute('''INSERT INTO collection_runs(query_keyword,from_at,to_at)
                       VALUES(%s,%s,%s) RETURNING id''', (keyword, start, end))
        run_id = cur.fetchone()[0]

        def reserve():
            cur.execute('''INSERT INTO api_daily_usage(usage_date,requests_made)
                           VALUES((now() AT TIME ZONE 'UTC')::date,1)
                           ON CONFLICT(usage_date) DO UPDATE
                           SET requests_made=api_daily_usage.requests_made+1
                           WHERE api_daily_usage.requests_made < %s
                           RETURNING requests_made''', (budget,))
            if cur.fetchone() is None:
                raise CollectionError('local_daily_budget_exhausted')

        def save(row):
            cur.execute(INSERT_SQL, row)
            return int(cur.fetchone() is not None)

        # Ngày gần nhất trước: ưu tiên cập nhật, sau đó bổ sung lịch sử.
        for left, right in reversed(list(day_windows(start, end))):
            fetch_window(key, keyword, left, right, max_pages, language, reserve, save, stats)
        if stats['capped_windows']:
            status = 'partial'
    except Exception as exc:
        status = 'error'
        error_code = exc.code if isinstance(exc, CollectionError) else type(exc).__name__
        # Không in traceback/DSN hay message API có thể chứa thông tin cấu hình.
        raise CollectionError(error_code) from None
    finally:
        try:
            if run_id:
                cur.execute('''UPDATE collection_runs SET finished_at=now(),status=%s,
                               requests_made=%s,articles_received=%s,articles_inserted=%s,
                               articles_skipped=%s,capped_windows=%s,error_code=%s WHERE id=%s''',
                            (status, stats['requests_made'], stats['articles_received'],
                             stats['articles_inserted'], stats['articles_skipped'],
                             stats['capped_windows'], error_code, run_id))
        finally:
            cur.close()
            conn.close()  # Giải phóng advisory lock của phiên.
    LOG.info('Kết quả: trạng thái=%s; %s', status, json.dumps(stats))
    return stats


def main():
    parser = argparse.ArgumentParser(description='Thu thập tin tức về Vietnam vào PostgreSQL')
    parser.add_argument('--loop', action='store_true', help='Thu thập định kỳ')
    parser.add_argument('--from', dest='from_at', help='Thời điểm UTC, ví dụ 2026-09-20T00:00:00Z')
    parser.add_argument('--to', dest='to_at', help='Thời điểm UTC kết thúc')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    interval = int(os.environ.get('COLLECT_INTERVAL_SECONDS', '21600'))
    if args.loop and interval < 3600:
        parser.error('Chu kỳ tối thiểu 3600 giây; mặc định 21600 giây = 6 giờ.')
    while True:
        try:
            collect(args)
        except Exception as exc:
            code = exc.code if isinstance(exc, CollectionError) else type(exc).__name__
            LOG.error('Thu thập chưa thành công: %s', code)
            if not args.loop:
                return 1
        if not args.loop:
            return 0
        LOG.info('Chờ %s giây đến lần thu thập tiếp theo.', interval)
        time.sleep(interval)


if __name__ == '__main__':
    raise SystemExit(main())
