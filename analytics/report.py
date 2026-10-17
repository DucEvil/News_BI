"""Báo cáo kỹ thuật TH2 được sinh từ số liệu thật và trạng thái kiểm chứng."""
import json
from datetime import datetime,timezone
from analytics.common import OUTPUT


def export_report(result):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    db=result['database']
    ai=result['ai']
    forecast=result['forecast']
    evaluation=result['evaluation']
    metrics=forecast.get('metrics') or {}
    rows='\n'.join(f"| {name} | {score['mae']:.3f} | {score['smape']:.2f}% | {score['test_days']} |" for name,score in metrics.items())
    mcp_path=OUTPUT/'mcp_checks.json'
    mcp=json.loads(mcp_path.read_text(encoding='utf-8')) if mcp_path.exists() else None
    mcp_status=(f"Đã initialize MCP stdio, gọi {len(mcp['tools'])} tools và kiểm tra {len(mcp['charts'])} chart qua MCP; thời điểm {mcp.get('generated_at_utc','không ghi')} UTC."
                if mcp else 'Chờ chạy analytics.verify_mcp; chưa xác nhận kết nối MCP ở lần triển khai này.')
    report=f'''# TH2: Hệ thống phân tích tin tức tích hợp Gemini AI và Apache Superset MCP

Thời điểm tạo: {datetime.now(timezone.utc).isoformat()} (UTC).

## 1. Đề xuất và kiến trúc dữ liệu trung tâm

Đề tài chọn nhánh **hệ thống phân tích tin tức** của yêu cầu. Luồng thu thập
NewsAPI từ TH1 được giữ lại. PostgreSQL `news_db` là kho dữ liệu trung tâm;
`superset_meta` chỉ chứa tài khoản, dataset và cấu hình dashboard.

```mermaid
flowchart LR
  N[NewsAPI: Vietnam] --> C[Python collector]
  C --> A[(PostgreSQL: articles)]
  A --> G[Gemini: cảm xúc, chủ đề, tóm tắt]
  G --> B[(article_ai và ai_runs)]
  A --> F[Dự báo và backtest theo thời gian]
  F --> P[(forecast_runs và news_forecasts)]
  B --> V[SQL views phân tích]
  P --> V
  V --> S[Apache Superset]
  H[MCP host hoặc client kiểm chứng] --> M[MCP server stdio]
  M --> R[Superset REST API]
  R --> S
```

Migration `sql/002_ai.sql` có thể chạy lại, không xóa bài báo hay dashboard TH1.
Kết quả AI có khóa `(article_id, model_name, prompt_version)` và input hash
để tránh gọi lại dữ liệu đã phân tích. Bản phân tích gần nhất được đưa vào view;
dashboard có thể gồm nhiều phiên bản model nếu đổi cấu hình, cần phân nhóm
theo model khi so sánh chất lượng.

## 2. Triển khai Gemini

- Model cấu hình: `{ai.get('model','unknown')}`; prompt: `news-v1`.
- Trạng thái chạy thực tế: **{ai['status']}**.
- Tổng bài trong kho: **{db['articles']}**; có kết quả AI: **{db['analyzed']}**;
  chờ phân tích: **{db['pending']}**; bao phủ: **{db['coverage_percent']}%**.
- Lần này đã chọn {ai.get('articles_selected',0)} bài, phân tích {ai.get('articles_analyzed',0)} bài,
  gửi {ai.get('requests_made',0)} request; input/output tokens: {ai.get('input_tokens',0)}/{ai.get('output_tokens',0)}.

Python gửi tiêu đề, mô tả và đoạn nội dung do NewsAPI cung cấp tới Gemini qua
HTTPS, khóa nằm trong header `x-goog-api-key`. Gemini trả JSON theo schema:
id bài, sentiment, score, confidence, topic, summary_vi, rationale_vi, language.
Hệ thống kiểm tra nhãn, khoảng số, độ dài, đủ id và không lặp id trước khi ghi
toàn batch vào database. Nội dung bài báo được đánh dấu là dữ liệu không tin cậy;
không cho mô hình thực thi SQL, mở URL hoặc điều khiển MCP.

Worker mặc định xử lý tối đa 20 bài/lần, 5 bài/request, ngân sách 20 request/ngày UTC,
không tự retry 429. Gọi lại các lỗi có thể dùng quota nên chỉ chạy lại sau khi sửa.
Khóa advisory PostgreSQL ngăn hai worker AI gửi cùng lúc. Khi quota hết, các batch
đã lưu được giữ lại. Khi thiếu key, ghi `waiting_key`, gửi 0 request và giữ bảng
`article_ai` trống; không dùng kết quả giả để điền dashboard.

## 3. Apache Superset MCP

Đây là MCP server dùng Python SDK chính thức, ghim nhánh 1.x để API ổn định;
giao tiếp **stdio**, thực hiện handshake initialize, list_tools và call_tool.
Server là adapter cho Superset 5 đang có, không phải tính năng MCP native của
phiên bản Superset này và không yêu cầu đổi sang CRM hoặc nâng cấp Superset.

Các tools: `get_analysis_status`, `list_dashboards`, `list_datasets`,
`ensure_ai_dashboard`, `get_chart_data`. Tool tạo dashboard chỉ được tạo/cập nhật
10 biểu đồ và các dataset TH2 định sẵn; tool đọc dữ liệu chart chỉ nhận chart
thuộc dashboard TH2. Không cung cấp công cụ thực thi SQL tùy ý hay gọi Gemini.

**Bằng chứng runtime:** {mcp_status}

Tệp `mcp_config.example.json` dành cho MCP host hỗ trợ cấu hình `mcpServers`.
Chưa tự thêm server vào cấu hình ứng dụng của người học. Client kiểm chứng
`analytics.verify_mcp` đã bao gồm khả năng kết nối server mà không cần host bên ngoài.
Gemini worker và MCP là hai thành phần độc lập: worker phân tích, MCP quản lý
và kiểm tra trực quan hóa, không tuyên bố Gemini đang tự gọi MCP nếu chưa triển khai agent.

## 4. Dashboard TH2

URL: http://localhost:8088/superset/dashboard/tin-tuc-ai-th2/

10 biểu đồ: số bài đã phân tích, tỷ lệ bao phủ, cơ cấu cảm xúc, số bài theo chủ đề,
điểm cảm xúc theo ngày, số bài tiêu cực theo nguồn, lịch sử và dự báo lượng bài,
bảng MAE/sMAPE của các mô hình dự báo, chi tiết phân tích Gemini, nhật ký AI.

Dashboard chỉ đọc SQL views; refresh 5 phút không gọi Gemini. Đóng web không
dừng container. Worker AI định kỳ chỉ hoạt động khi bật bằng lệnh riêng hoặc
`start-ai.ps1 -Schedule`; mặc định chạy một lần để giới hạn tài nguyên và API.
Dashboard TH1 và thông tin đăng nhập hiện có được giữ lại.

## 5. Đánh giá hiệu quả và giới hạn

### Gemini

Trạng thái đánh giá: **{evaluation['status']}**. Số nhãn người đã xác nhận:
{evaluation['reviewed_labels']}; số có dự đoán tương ứng: {evaluation['matched_predictions']}.

Chưa có API key hoặc nhãn đối chứng thì **chưa thể kết luận accuracy/F1**.
`confidence` là tự đánh giá của mô hình, không được dùng thay accuracy. Khi có
nhãn, hệ thống tính accuracy, precision/recall/F1 từng lớp, confusion matrix và
macro-F1 trên lớp có nhãn thật. Cần một tập kiểm tra độc lập, nhiều ngôn ngữ và
đủ lớp; nên gán nhãn mù với hai người và giải quyết bất đồng. Tóm tắt cần kiểm
tra thủ công tính đúng sự kiện, độ đầy đủ, ngôn ngữ và khả năng bịa thông tin.
Các unit test dùng response mô phỏng để kiểm tra logic, không phải số đo chất lượng Gemini.

### Dự báo số bài đã thu thập

Trạng thái: **{forecast['status']}**. Có {forecast['n_observations']} ngày quan sát để huấn luyện;
train end: {forecast.get('train_end','chưa đủ dữ liệu')}; độ trễ dữ liệu:
{forecast.get('data_lag_days','N/A')} ngày; mô hình chọn theo MAE backtest:
**{forecast.get('selected_model','chưa chọn')}**.

| Mô hình | MAE (bài) | sMAPE | Số ngày kiểm tra |
|---|---:|---:|---:|
{rows if rows else '| Chưa đủ dữ liệu | — | — | — |'}

MAE = trung bình |thực tế − dự báo|. sMAPE = trung bình
200 × |thực tế − dự báo| / (|thực tế| + |dự báo|), bằng 0 khi cả hai bằng 0.
Backtest rolling-origin dùng tối thiểu 7 điểm quá khứ, tối đa 5 ngày kiểm tra;
không dùng dữ liệu tương lai khi huấn luyện từng bước. Chọn mô hình theo MAE
trên chính tập backtest có thể lạc quan, cần thêm holdout độc lập khi đủ lịch sử.
Không có khoảng tin cậy đã hiệu chỉnh; đây là ước lượng điểm phục vụ bài học.

{forecast['note']}

Nếu dữ liệu chậm quá 3 ngày, ghi `stale_data` và không sinh dự báo mới.
Dữ liệu lịch sử ít, khác biệt coverage theo ngày và giới hạn 100 bài/request
làm kết quả thiên lệch. Mô hình dự báo **lượng thu thập**, không dự báo tổng tin
thực tế, xu hướng xã hội hay giá trị kinh tế. Nội dung NewsAPI rút gọn và từ
khóa Vietnam có thể xuất hiện thoáng qua; không đồng nghĩa mọi bài đều chuyên về Việt Nam.

## 6. Đề xuất nhiều mô hình và hướng sáng tạo

| Phương án | Ứng dụng | Cách kiểm chứng / giới hạn |
|---|---|---|
| Gemini Flash-Lite (đã triển khai) | Cảm xúc, chủ đề, tóm tắt đa ngôn ngữ | Accuracy/F1 với nhãn người, kiểm tra tóm tắt; phụ thuộc key/quota |
| Naive / trung bình 7 quan sát (đã triển khai) | Baseline dự báo lượng thu thập | MAE/sMAPE rolling-origin; không nhầm thiếu dữ liệu với 0 |
| Hồi quy tuyến tính theo ngày (đã triển khai) | Xu hướng lượng bài đã lưu | So với baseline; dễ lệch với dữ liệu ít hoặc thay quota |
| XLM-RoBERTa hoặc mô hình sentiment huấn luyện sẵn | Phân tích cục bộ đa ngôn ngữ | Cần đánh giá miền tin tức; tốn dung lượng model và RAM |
| Embedding + clustering | Gom bài cùng sự kiện, giảm trùng nội dung khác URL | Đánh giá cặp bài trùng do người xác nhận; có thể dùng pgvector |
| RAG có trích dẫn URL | Hỏi đáp tin đã thu thập với bằng chứng | Đo đúng nguồn, chống prompt injection và kiểm chứng từng khẳng định |
| Phát hiện bùng nổ chủ đề / đổi phân phối | Cảnh báo sự kiện và biến động coverage | Tách biến động do quota/máy tắt khỏi biến động tin thực tế |

## Đối chiếu checklist

1. Kiến trúc: đã thiết kế và migration vào kho PostgreSQL có sẵn.
2. AI: mã Gemini đã triển khai; trạng thái chạy thật `{ai['status']}`, chỉ hoàn tất kiểm chứng Gemini sau khi có key.
3. Superset MCP: xem bằng chứng runtime ở mục 3 và `mcp_checks.json`.
4. Dashboard: đã định nghĩa 10 biểu đồ; kết quả AI xuất hiện khi worker có dự đoán thật.
5. Báo cáo và đánh giá: báo cáo này, backtest thật; đánh giá chất lượng Gemini chờ nhãn và dự đoán.
6. Nhiều mô hình: đã so sánh 3 baseline dự báo và đề xuất 4 hướng AI mở rộng.

## Mã nguồn và bằng chứng

- `sql/002_ai.sql`: schema và views.
- `analytics/gemini.py`, `pipeline.py`: phân tích Gemini, cache, quota, lịch.
- `analytics/forecast.py`, `evaluation.py`: dự báo và đánh giá.
- `analytics/mcp_server.py`, `dashboard.py`, `verify_mcp.py`: MCP và trực quan hóa.
- `output/th2/pipeline_status.json`, `forecast_evaluation.json`, `gemini_evaluation.json`, `mcp_checks.json`.
- `output/th2/labeling_template.jsonl`: mẫu gán nhãn người, chưa có nhãn mặc định.

Tài liệu chính thức:
[Gemini models](https://ai.google.dev/gemini-api/docs/models),
[Gemini structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output),
[MCP Python SDK v1](https://py.sdk.modelcontextprotocol.io/v1/),
[Superset API](https://superset.apache.org/docs/api/).
'''
    (OUTPUT/'BAO_CAO_KY_THUAT.md').write_text(report,encoding='utf-8')
    return report
