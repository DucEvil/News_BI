# TH2 — Phân tích tin tức với Gemini và Apache Superset MCP

Bài này mở rộng News BI hiện có. Giữ dashboard TH1 và dữ liệu PostgreSQL;
tạo dashboard thứ hai **TH2 · Phân tích tin tức với Gemini AI** trên cùng Superset.

## Chạy trên Windows

1. Mở Docker Desktop.
2. Mở `.env`, điền **khóa Gemini** vào `GEMINI_API_KEY=`. Khóa NewsAPI vẫn ở
   `NEWSAPI_KEY`; hai khóa phục vụ hai API khác nhau.
3. Trong PowerShell:

   ```powershell
   cd E:\News_BI
   powershell -ExecutionPolicy Bypass -File .\scripts\start-ai.ps1
   ```

4. Mở [dashboard TH2](http://localhost:8088/superset/dashboard/tin-tuc-ai-th2/).
   Tên đăng nhập và mật khẩu Superset giữ nguyên (`SUPERSET_ADMIN_USERNAME`,
   `SUPERSET_ADMIN_PASSWORD` trong `.env`).

Không có Gemini key vẫn chạy được migration, dự báo và MCP. Worker ghi
`waiting_key`, gửi 0 request Gemini; các biểu đồ cảm xúc/chủ đề chưa có dữ liệu.
Sau khi điền key và lưu `.env`, chạy lại lệnh trên. Không cần tạo lại database.
Mặc định chỉ phân tích tối đa 20 bài/lần; không tự gửi toàn bộ kho tin lên API.
`GEMINI_MODEL` có thể đổi sang model tài khoản của bạn được phép sử dụng.

### Lỗi đăng nhập Superset 401

Tài khoản Superset được lưu trong database. Sửa `SUPERSET_ADMIN_PASSWORD`
trong `.env` không tự đổi mật khẩu tài khoản đã tạo. Script kiểm tra đăng nhập
trước khi gọi Gemini để tránh tốn quota khi mật khẩu Superset đang lệch.

Bạn có thể đặt `.env` về đúng mật khẩu đăng nhập hiện tại. Nếu muốn dùng
mật khẩu mới đang ghi trong `.env`, đồng bộ tường minh:

```powershell
cd E:\News_BI
powershell -ExecutionPolicy Bypass -File .\scripts\start-ai.ps1 -SyncAdminPassword
```

Cờ này cập nhật mật khẩu tài khoản Superset hiện có theo `.env`, giữ nguyên
database bài báo, quyền và dashboard. Dùng mật khẩu đó cho lần đăng nhập web
tiếp theo. Các lần chạy thông thường không tự đổi mật khẩu. Trong WSL, dùng
`bash scripts/start-ai.sh --sync-admin-password`.

## Tự động và hạn mức

```powershell
cd E:\News_BI
powershell -ExecutionPolicy Bypass -File .\scripts\start-ai.ps1 -Schedule
```

Worker AI chạy ngay khi khởi động rồi lặp theo `AI_INTERVAL_SECONDS` (mặc định
6 giờ). Tối đa 20 bài/lần, 5 bài/request, ngân sách 20 request/ngày UTC; tính
cả request lỗi, không tự retry để tránh dùng quota ngoài dự kiến. Ngân sách
chỉ biết các request từ dự án, không theo dõi ứng dụng khác dùng cùng key.
Nếu đang có worker định kỳ thì chạy thủ công có thể báo `already_running`;
chờ worker xong trước khi chạy lại. Các bài đã phân tích với cùng input, model
và phiên bản prompt được bỏ qua.

Tạm dừng AI, vẫn xem được dashboard:

```powershell
cd E:\News_BI
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" compose --profile ai stop ai-worker
```

Để AI tiếp nhận **bài mới**, collector NewsAPI phải được bật riêng theo README
TH1. Chạy AI không tự gọi NewsAPI. Đóng trình duyệt không dừng container.
Máy ngủ/tắt hoặc Docker dừng sẽ tạm ngừng lịch chạy.

## Sáu checklist và bằng chứng

| Checklist | Thành phần | Cách xác nhận |
|---|---|---|
| 1. Kiến trúc kết nối dữ liệu trung tâm | PostgreSQL `articles`, `article_ai`, `ai_runs`, `forecast_runs`, SQL views | Sơ đồ Mermaid trong báo cáo; `sql/002_ai.sql` |
| 2. Mô hình AI | Gemini sentiment/topic/summary, ba mô hình dự báo | `analytics/gemini.py`, `forecast.py`; `pipeline_status.json` |
| 3. Superset MCP | MCP stdio dùng SDK chính thức, gọi Superset REST | `analytics/verify_mcp.py` thực hiện initialize/list_tools/call_tool; `mcp_checks.json` |
| 4. Tích hợp AI vào dashboard | Dashboard riêng gồm 10 biểu đồ | Chưa có key: KPI AI 0 và nhật ký waiting_key; có key: dữ liệu dự đoán thật |
| 5. Báo cáo và đánh giá | Báo cáo kỹ thuật tự sinh, backtest dự báo, đánh giá phân loại bằng nhãn người | `output/th2/BAO_CAO_KY_THUAT.md`, các tệp JSON đánh giá |
| 6. Đa dạng mô hình/sáng tạo | Naive, moving average, linear trend đã triển khai; XLM-R, clustering, RAG và phát hiện burst đề xuất | Mục 6 báo cáo |

Không đánh dấu hoàn thành **kiểm chứng Gemini thực tế** khi chưa có key.
Không công bố accuracy/F1 khi chưa có nhãn người; confidence của Gemini
không phải độ chính xác đã đo. Dự báo là lượng bài **đã thu thập**, có thiên
lệch từ quota và khoảng thời gian máy không chạy.

## Đánh giá có nhãn người

1. Chạy pipeline để tạo `output/th2/labeling_template.jsonl`.
2. Gán nhãn sentiment/topic độc lập từ tiêu đề/mô tả, điền reviewer và reviewed.
3. Lưu vào `evaluation/labels.jsonl`; xem `evaluation/README.md`.
4. Chạy lại `start-ai.ps1`. Tệp `gemini_evaluation.json` ghi confusion matrix,
   accuracy và macro-F1 trên các lớp có nhãn thật cho các bài đã có dự đoán.

Nên gán nhãn ít nhất 50–100 mẫu đa dạng, có đủ các lớp, giữ một holdout riêng;
đây là gợi ý thiết kế kiểm thử, không đảm bảo đủ để kết luận trong mọi miền.
Thay model/prompt cần đánh giá lại. Không dùng dự đoán của Gemini làm nhãn thật.

## MCP host

`mcp_config.example.json` chứa lệnh khởi chạy MCP server bằng Docker, không
chứa API key hay mật khẩu. Có thể thêm cấu hình đó vào host hỗ trợ
`mcpServers` sau khi đã chạy `start-ai.ps1`. Đây là adapter MCP tự xây cho
Superset 5, không phải module MCP native cài sẵn trong Superset.

Các công cụ:

- `get_analysis_status`: số bài, bao phủ và lần chạy AI gần nhất.
- `list_dashboards`, `list_datasets`: xác nhận tài sản trong Superset.
- `ensure_ai_dashboard`: tạo/cập nhật đúng dashboard TH2 và 10 charts định sẵn.
- `get_chart_data`: đọc dữ liệu một chart thuộc TH2.

Không cần cấu hình host để kiểm chứng: `start-ai.ps1` tự chạy MCP client và
lưu `output/th2/mcp_checks.json`. Không có endpoint HTTP MCP vì dùng stdio;
không phải mở thêm cổng. Worker Gemini không tự gọi tools MCP; hai thành phần
tích hợp qua database và Superset để luồng phân tích có thể kiểm chứng rõ ràng.

## Chạy bằng Ubuntu WSL

```bash
cd /mnt/e/News_BI
bash scripts/start-ai.sh
# Tùy chọn bật lịch sau khi đã kiểm tra chạy một lần:
docker compose --profile ai up -d ai-worker
```

## Các lệnh kiểm chứng riêng

```bash
docker compose --profile ai run --rm analytics python -m analytics.pipeline --limit 5
docker compose --profile ai run --rm analytics python -m analytics.verify_mcp
python -m unittest discover -s tests -v
```

PowerShell nếu `docker` chưa có trong PATH thì dùng đường dẫn trong script.
Không dùng `docker compose down -v` để thử lỗi: thao tác này xóa dữ liệu.
Các lỗi Gemini chỉ ghi mã an toàn như `gemini_http_403`, `gemini_http_429`,
`invalid_model_name`; kiểm tra key, quyền model hoặc quota trước khi chạy lại.

## Tệp dùng khi quay video

- `sql/002_ai.sql`: cấu trúc lưu AI và dự báo.
- `analytics/gemini.py`: prompt, API request, schema và validation.
- `analytics/pipeline.py`: cache, quota, nhật ký và lịch.
- `analytics/forecast.py`: ba mô hình và backtest theo thời gian.
- `analytics/mcp_server.py`: các MCP tools.
- Dashboard TH2, trạng thái waiting_key hoặc kết quả AI thật.
- `output/th2/BAO_CAO_KY_THUAT.md`, `mcp_checks.json`, các tệp đánh giá.

Không quay `.env` hoặc trường mật khẩu trong cấu hình kết nối.
