import importlib.util
import io
import json
from pathlib import Path
import unittest
import urllib.error

path = Path(__file__).resolve().parents[1] / 'collector' / 'collect_news.py'
spec = importlib.util.spec_from_file_location('collector_module', path)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def article(n=1, **changes):
    result = {'title': f'Vietnam news {n}', 'url': f'https://example.test/news/{n}',
              'publishedAt': '2026-09-30T18:00:00Z',
              'source': {'id': None, 'name': 'Nguồn kiểm thử'}, 'content': 'Nội dung rút gọn'}
    return {**result, **changes}


class CollectorTests(unittest.TestCase):
    def test_normalize_timezone_and_content(self):
        row = c.normalize_article(article(publishedAt='2026-10-01T01:00:00+07:00'), 'Vietnam')
        self.assertEqual(row['published_at'].hour, 18)
        self.assertEqual(row['published_at'].day, 30)
        self.assertEqual(row['content'], 'Nội dung rút gọn')

    def test_bad_articles_are_skipped(self):
        for item in [None, article(title='[Removed]'), article(title=' '),
                     article(url=None), article(url='file:///tmp/x'),
                     article(url='https://['), article(publishedAt='bad')]:
            self.assertIsNone(c.normalize_article(item, 'Vietnam'))

    def test_source_fallback(self):
        self.assertEqual(c.normalize_article(article(source=None), 'Vietnam')['source_name'], 'example.test')

    def test_duplicate_fragment_and_query(self):
        a = c.normalize_article(article(url='https://example.test/a#one'), 'Vietnam')
        b = c.normalize_article(article(url='https://example.test/a#two'), 'Vietnam')
        d = c.normalize_article(article(url='https://example.test/a?id=2'), 'Vietnam')
        self.assertEqual(a['url_hash'], b['url_hash'])
        self.assertNotEqual(a['url_hash'], d['url_hash'])

    def test_day_windows_no_overlap(self):
        start = c.parse_timestamp('2026-09-29T22:00:00Z')
        end = c.parse_timestamp('2026-10-01T02:00:00Z')
        windows = list(c.day_windows(start, end))
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0][0], start)
        self.assertEqual(windows[-1][1], end)
        for left, right in zip(windows, windows[1:]):
            self.assertEqual(right[0] - left[1], c.timedelta(seconds=1))

    def test_key_is_header_only(self):
        def opener(req, timeout):
            self.assertNotIn('SECRET123', req.full_url)
            self.assertEqual(req.get_header('X-api-key'), 'SECRET123')
            self.assertIn('q=Vietnam', req.full_url)
            self.assertNotIn('language=vi', req.full_url)
            return io.BytesIO(b'{"status":"ok","articles":[],"totalResults":0}')
        t = c.parse_timestamp('2026-09-29T00:00:00Z')
        c.fetch_page('SECRET123', 'Vietnam', t, t, 1, opener=opener)

    def test_http_error_preserves_safe_code(self):
        def opener(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 429, 'quota', {}, io.BytesIO(b'{"code":"rateLimited","message":"secret"}'))
        t = c.parse_timestamp('2026-09-29T00:00:00Z')
        with self.assertRaises(c.CollectionError) as error:
            c.fetch_page('KEY', 'Vietnam', t, t, 1, opener=opener)
        self.assertEqual(str(error.exception), 'rateLimited')

    def run_window(self, pages, max_pages=3):
        stats = dict.fromkeys(['requests_made', 'articles_received', 'articles_inserted', 'articles_skipped', 'capped_windows'], 0)
        saved = set()
        def save(row):
            before = len(saved)
            saved.add(row['url_hash'])
            return int(len(saved) > before)
        responses = iter(pages)
        def opener(req, timeout):
            return io.BytesIO(json.dumps(next(responses)).encode())
        t = c.parse_timestamp('2026-09-29T00:00:00Z')
        c.fetch_window('KEY', 'Vietnam', t, t, max_pages, '', lambda: None, save, stats, opener)
        return stats

    def test_pagination_dedup_and_invalid(self):
        first = [article(n) for n in range(100)]
        second = [article(99), article(100), article(101, title='[Removed]')]
        stats = self.run_window([{'status': 'ok', 'articles': first, 'totalResults': 103},
                                 {'status': 'ok', 'articles': second, 'totalResults': 103}])
        self.assertEqual(stats['requests_made'], 2)
        self.assertEqual(stats['articles_inserted'], 101)
        self.assertEqual(stats['articles_skipped'], 1)
        self.assertEqual(stats['capped_windows'], 0)

    def test_cap_is_reported(self):
        stats = self.run_window([{'status': 'ok', 'articles': [article(n) for n in range(100)], 'totalResults': 200}], max_pages=1)
        self.assertEqual(stats['capped_windows'], 1)

    def test_budget_blocks_http(self):
        def reserve():
            raise c.CollectionError('local_daily_budget_exhausted')
        def forbidden(req, timeout):
            self.fail('Không được gửi HTTP khi hết ngân sách')
        t = c.parse_timestamp('2026-09-29T00:00:00Z')
        with self.assertRaises(c.CollectionError):
            c.fetch_window('KEY', 'Vietnam', t, t, 1, '', reserve, lambda row: 1,
                           {'requests_made': 0}, forbidden)


if __name__ == '__main__':
    unittest.main()
