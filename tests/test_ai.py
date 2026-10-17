import io
import json
import math
import sys
import unittest
import urllib.error
from unittest.mock import Mock
from datetime import date,timedelta
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'collector'))
from analytics.gemini import GeminiError,analyze_batch,input_hash,validate_results
from analytics.forecast import predict,backtest
from analytics.evaluation import classification_metrics
from analytics.superset_client import SupersetClient,SupersetError
from analytics.errors import failure_message


def result(identity=1,**changes):
    return {'id':identity,'sentiment':'neutral','sentiment_score':0,'confidence':0.7,
            'topic':'kinh_te','summary_vi':'Tóm tắt kiểm thử.','rationale_vi':'Đoạn tin mang tính thông báo.',
            'language':'en',**changes}


class GeminiTests(unittest.TestCase):
    def test_ids_must_be_exactly_once(self):
        for rows in [[result(),result()],[result(2)],[]]:
            with self.assertRaises(GeminiError):
                validate_results({'articles':rows},{1})

    def test_untrusted_response_cannot_be_arbitrary(self):
        for change in [{'sentiment':'execute_sql'},{'topic':'DROP TABLE articles'},
                       {'summary_vi':''},{'summary_vi':'a'*501},{'id':True},
                       {'sentiment':'positive','sentiment_score':-0.5}]:
            with self.assertRaises(GeminiError):
                validate_results({'articles':[result(**change)]},{1})

    def test_reject_nan_bool_and_out_of_range(self):
        for change in [{'confidence':True},{'confidence':math.nan},{'confidence':1.01},
                       {'sentiment_score':-1.1},{'sentiment_score':math.inf}]:
            with self.assertRaises(GeminiError):
                validate_results({'articles':[result(**change)]},{1})

    def test_key_only_in_header_and_strict_json_schema(self):
        def opener(request,timeout):
            self.assertNotIn('TEST_KEY',request.full_url)
            self.assertEqual(request.get_header('X-goog-api-key'),'TEST_KEY')
            payload=json.loads(request.data)
            self.assertEqual(payload['generationConfig']['responseMimeType'],'application/json')
            self.assertIn('responseJsonSchema',payload['generationConfig'])
            body={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps({'articles':[result()]})}]}}],
                  'usageMetadata':{'promptTokenCount':120,'candidatesTokenCount':60}}
            return io.BytesIO(json.dumps(body).encode())
        rows,usage=analyze_batch([{'id':1,'title':'Vietnam update'}],'TEST_KEY','gemini-3.5-flash-lite',opener)
        self.assertEqual(rows[0]['id'],1)
        self.assertEqual(usage['input_tokens'],120)

    def test_blocked_or_truncated_is_not_saved_as_success(self):
        for reason in ['SAFETY','MAX_TOKENS']:
            def opener(request,timeout):
                return io.BytesIO(json.dumps({'candidates':[{'finishReason':reason}]}).encode())
            with self.assertRaises(GeminiError):
                analyze_batch([{'id':1}],'KEY','gemini-3.5-flash-lite',opener)

    def test_http_errors_do_not_leak_key_or_body(self):
        def opener(request,timeout):
            raise urllib.error.HTTPError(request.full_url,429,'quota',{},io.BytesIO(b'private TEST_KEY'))
        with self.assertRaisesRegex(GeminiError,'^gemini_http_429$'):
            analyze_batch([{'id':1}],'TEST_KEY','gemini-3.5-flash-lite',opener)

    def test_missing_key_never_calls_http(self):
        def forbidden(*args,**kwargs):
            self.fail('No key must not cause a network call')
        with self.assertRaises(GeminiError):
            analyze_batch([{'id':1}],'','gemini-3.5-flash-lite',forbidden)

    def test_hash_matches_only_transmitted_input(self):
        row={'id':1,'title':'a'*400+'hidden one','source_name':'Source'}
        self.assertEqual(input_hash(row),input_hash({**row,'title':'a'*400+'hidden two'}))
        self.assertNotEqual(input_hash(row),input_hash({**row,'title':'Different title'}))


class ForecastTests(unittest.TestCase):
    def test_calendar_gaps_are_not_zero_observations(self):
        start=date(2026,1,1)
        history=[(start,10),(start+timedelta(days=2),14),(start+timedelta(days=5),20)]
        self.assertAlmostEqual(predict(history,start+timedelta(days=6),'linear_trend'),22)
        self.assertEqual(predict(history,start+timedelta(days=6),'moving_average_7'),44/3)

    def test_backtest_linear_signal_uses_past_only(self):
        start=date(2026,1,1)
        history=[(start+timedelta(days=i),10+2*i) for i in range(14)]
        selected,scores=backtest(history)
        self.assertEqual(selected,'linear_trend')
        self.assertAlmostEqual(scores['linear_trend']['mae'],0)
        self.assertGreater(scores['last_value']['mae'],0)

    def test_zero_counts_have_defined_smape(self):
        start=date(2026,1,1)
        _,scores=backtest([(start+timedelta(days=i),0) for i in range(12)])
        self.assertEqual(scores['moving_average_7']['smape'],0)

    def test_no_forecast_without_sufficient_history(self):
        with self.assertRaises(ValueError):
            backtest([(date(2026,1,1),10)])

    def test_negative_linear_predictions_are_clipped(self):
        start=date(2026,1,1)
        self.assertEqual(predict([(start,5),(start+timedelta(days=1),1)],start+timedelta(days=5),'linear_trend'),0)


class EvaluationTests(unittest.TestCase):
    def test_confusion_and_macro_f1_are_computed_from_truth(self):
        metrics=classification_metrics(['positive','positive','negative','negative'],
            ['positive','negative','negative','positive'],['positive','neutral','negative','mixed'])
        self.assertEqual(metrics['accuracy'],0.5)
        self.assertEqual(metrics['macro_f1_supported_classes'],0.5)
        self.assertEqual(metrics['per_class']['neutral']['support'],0)

    def test_no_accuracy_for_empty_labels(self):
        with self.assertRaises(ValueError):
            classification_metrics([],[],['positive','negative'])


class SupersetClientTests(unittest.TestCase):
    def test_nested_mcp_login_failure_is_actionable(self):
        root=RuntimeError('mcp_tool_failed: Error executing tool ensure_ai_dashboard: superset_http_401: POST /api/v1/security/login')
        group=ExceptionGroup('task group',[ExceptionGroup('stdio',[root])])
        message=failure_message(group)
        self.assertIn('Superset login rejected (401)',message)
        self.assertIn('-SyncAdminPassword',message)
        self.assertNotIn('ExceptionGroup',message)

    def test_error_groups_keep_distinct_causes_and_limit_output(self):
        grouped=ExceptionGroup('task group',[ValueError('invalid_chart_id'),ValueError('invalid_chart_id'),ValueError('other_error')])
        self.assertEqual(failure_message(grouped),'invalid_chart_id; other_error')
        self.assertEqual(len(failure_message(ValueError('x'*1000))),500)

    def test_expired_token_refreshes_once_without_leaking_credentials(self):
        client=SupersetClient()
        client.token='expired'
        def login():
            client.token='fresh'
            client.csrf='csrf'
        client.login=Mock(side_effect=login)
        client.opener=Mock()
        client.opener.open.side_effect=[
            urllib.error.HTTPError('http://superset:8088/api/v1/dashboard/',401,'expired',{},io.BytesIO()),
            io.BytesIO(b'{"result": []}')]
        self.assertEqual(client.request('GET','/api/v1/dashboard/'),{'result':[]})
        client.login.assert_called_once()
        self.assertEqual(client.opener.open.call_count,2)

    def test_auth_failure_does_not_retry_forever(self):
        client=SupersetClient()
        client.token='bad'
        client.login=Mock(side_effect=lambda:setattr(client,'token','also-bad'))
        client.opener=Mock()
        client.opener.open.side_effect=urllib.error.HTTPError('http://superset',401,'bad',{},io.BytesIO())
        with self.assertRaises(SupersetError):
            client.request('GET','/api/v1/dashboard/')
        self.assertEqual(client.opener.open.call_count,2)


if __name__=='__main__':
    unittest.main()
