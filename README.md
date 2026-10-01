# Bài thực hành BI: Theo dõi và phân tích tin tức Việt Nam

Bộ mã thực hiện các bước sau khi đã có khóa NewsAPI: thu thập bài có từ khóa `Vietnam`, lưu vào PostgreSQL, khởi tạo Apache Superset và tạo dashboard. Hướng dẫn dành cho **Windows + Ubuntu WSL 2 + Docker Desktop**, chạy phục vụ bài học trên máy cá nhân.

## 1. Checklist trong đề được thực hiện như thế nào?

| Yêu cầu | Thành phần đã chuẩn bị | Cách xác nhận trên máy bạn |
|---|---|---|
| Viết Python lấy bài có từ khóa Vietnam | `collector/collect_news.py`, gọi `/v2/everything` | Nhật ký cho biết số request, số bài nhận và số bài thêm mới |
| Thiết kế và lưu tiêu đề, nội dung, nguồn, ngày xuất bản | `sql/001_init.sql`, bảng `articles` | Chạy truy vấn kiểm tra dữ liệu trong SQL Lab |
| Cài và kết nối Superset | `compose.yaml`, cấu hình và khởi tạo trong `superset/` | Mở Superset, thấy kết nối “Tin tức Việt Nam” và hai datasets |
| Dashboard thời gian và nguồn tin | Script `superset/bootstrap_dashboard.py` | Dashboard có sáu biểu đồ/bảng, dữ liệu khớp SQL |

**Trạng thái bàn giao:** mã đã được kiểm tra cú pháp và 10 tình huống kiểm thử logic thu thập đều đạt. Chưa chạy tích hợp NewsAPI, PostgreSQL và giao diện Superset vì môi trường tạo bộ mã không có Docker và không có khóa API của bạn. Chỉ đánh dấu hoàn thành thực hành khi đã chạy và có bằng chứng trên máy bạn. Bộ mã không kèm dữ liệu giả.

## 2. Chuẩn bị Windows và WSL

1. Mở **PowerShell trên Windows**, kiểm tra:

   ```powershell
   wsl -l -v
   wsl --version
   ```

   Ubuntu cần hiển thị VERSION 2. Docker khuyến nghị WSL được cập nhật, tối thiểu phiên bản WSL 2.1.5. Nếu cần cập nhật, chạy `wsl --update`.

2. Nếu chưa có, tải và cài [Docker Desktop cho Windows](https://docs.docker.com/desktop/setup/install/windows-install/). Nếu đã có Docker Desktop thì mở ứng dụng.
3. Trong Docker Desktop, chọn **Settings → General → Use WSL 2 based engine** nếu mục này xuất hiện.
4. Chọn **Settings → Resources → WSL Integration**, bật Ubuntu bạn đang sử dụng, chọn Apply. Dùng chế độ Linux containers. Không cài thêm Docker Engine trong Ubuntu khi đang dùng cách này.
5. Mở **terminal Ubuntu WSL**, kiểm tra:

   ```bash
   docker --version
   docker compose version
   docker info
   python3 --version
   ```

Từ đây, mọi lệnh Bash/Python/Docker trong hướng dẫn đều chạy trong **Ubuntu WSL**, không chạy trong PowerShell. Mở trang Superset bằng trình duyệt trên Windows. Docker Desktop phải hoạt động trong lúc làm bài.

## 3. Giải nén bộ mã vào Ubuntu

Tải `Vietnam_News_BI_WSL.zip` vào thư mục Downloads trên Windows. Trong Ubuntu:

```bash
sudo apt update
sudo apt install -y unzip python3 nano
mkdir -p ~/bi-news
unzip "/mnt/c/Users/TEN_WINDOWS/Downloads/Vietnam_News_BI_WSL.zip" -d ~/bi-news
cd ~/bi-news/news-bi
```

Thay `TEN_WINDOWS` bằng tên thư mục tài khoản Windows của bạn. Nếu lưu ZIP ở nơi khác, sửa đường dẫn tương ứng. Có thể xem tên các thư mục bằng `ls /mnt/c/Users`. Nếu bạn đã giải nén bằng Windows, sao chép thư mục `news-bi` vào Ubuntu và đi tới thư mục đó. Đặt mã trong `~/bi-news` giúp thao tác tệp trên WSL thuận tiện hơn.

## 4. Điền khóa NewsAPI và đặt mật khẩu Superset

```bash
python3 scripts/configure.py
```

- Khi được hỏi khóa NewsAPI, dán khóa và nhấn Enter. Terminal **không hiện ký tự** khi nhập; đây là hành vi bình thường.
- Đặt mật khẩu Superset ít nhất tám ký tự; nhớ mật khẩu này để đăng nhập.
- Script tạo `.env`, tự sinh mật khẩu PostgreSQL và khóa bí mật Superset.
- Tài khoản Superset là `admin`.
- Khi đã có `.env`, script không ghi đè. Muốn đổi khóa NewsAPI, chạy `nano .env`, sửa `NEWSAPI_KEY=...`, rồi Ctrl+O, Enter để lưu; Ctrl+X để thoát.
- Không gửi tệp `.env` trong bài nộp. Mã nguồn chỉ cần kèm `.env.example`.
- Sau khi đã khởi tạo Superset, thay mật khẩu trong `.env` không tự đổi mật khẩu tài khoản có sẵn; đổi mật khẩu trong giao diện quản trị. Giữ nguyên `POSTGRES_PASSWORD` và `SUPERSET_SECRET_KEY` để tiếp tục truy cập dữ liệu đã tạo.

## 5. Khởi chạy hệ thống và lấy dữ liệu thật lần đầu

```bash
bash scripts/start.sh
```

Lần đầu Docker cần tải các image và cài driver Python; thời gian tùy mạng và cấu hình máy. Script thực hiện theo thứ tự:

1. Kiểm tra Docker và tệp `.env`.
2. Tạo image Python thu thập dữ liệu.
3. Khởi động PostgreSQL và tạo hai cơ sở dữ liệu `news_db`, `superset_meta`.
4. Cập nhật cấu trúc Superset, tạo tài khoản quản trị, kết nối dữ liệu, datasets và dashboard.
5. Chạy Python gọi NewsAPI, làm sạch và lưu bài báo.
6. Kiểm tra tổng theo ngày/nguồn có khớp tổng bài đã lưu hay không.

Nếu thành công, truy cập:

**http://localhost:8088/superset/dashboard/tin-tuc-viet-nam/**

Đăng nhập bằng `admin` và mật khẩu ở bước 4. Nếu chuyển về trang đăng nhập, đăng nhập xong mở lại liên kết dashboard. Có thể đi qua menu Dashboards.

Các lệnh tương đương để chạy riêng từng bước:

```bash
docker compose build collector
docker compose up -d --wait superset
docker compose run --rm collector python collect_news.py
docker compose run --rm collector python verify_database.py
```

Nếu thu thập thất bại, PostgreSQL/Superset có thể vẫn hoạt động. Sửa lỗi rồi chạy lại riêng lệnh thu thập, không cần xóa cơ sở dữ liệu.

## 6. Cách Python thu thập và lưu bài báo

Script sử dụng `q=Vietnam`, sắp theo ngày xuất bản, tối đa 100 kết quả/trang. Khóa API gửi qua header `X-Api-Key`. Mặc định tìm mọi ngôn ngữ; **không đặt `language=vi`** vì danh sách ngôn ngữ hỗ trợ của NewsAPI không có mã này. Truy vấn có thể trả bài tiếng Anh hoặc các ngôn ngữ khác nhắc đến Việt Nam; không đảm bảo chỉ là báo chí Việt Nam.

Mỗi lần chạy lấy khoảng bảy ngày, kết thúc cách thời điểm chạy 25 giờ để phù hợp độ trễ gói Developer. Khoảng thời gian được chia theo ngày UTC, ưu tiên ngày gần nhất. Mỗi khoảng một trang mặc định. Khoảng bảy ngày có thể cắt qua tám ngày UTC nên tối đa khoảng tám request/lần, khoảng 32 request/ngày nếu chạy sáu giờ/lần. Request lỗi cũng được tính vào ngân sách nội bộ.

Nếu một khoảng có hơn 100 kết quả, script lưu trang được phép rồi ghi `capped_windows` và trạng thái `partial`. **Không coi dữ liệu là toàn bộ bài báo có trên NewsAPI.** Không suy diễn ngày không có bài đã lưu thành ngày không có tin tức thực tế. Không tự tăng số trang nếu chưa xác nhận gói API cho phép.

Bài thiếu tiêu đề, URL hoặc ngày hợp lệ bị bỏ qua. URL được băm SHA-256, có ràng buộc UNIQUE và `ON CONFLICT DO NOTHING` để không tạo bản ghi trùng khi chạy lại. Dấu fragment trong URL bị bỏ, query string được giữ. Hai URL khác nhau trỏ đến cùng một nội dung vẫn có thể được lưu thành hai bài; bộ mã chống trùng theo URL, không so sánh ngữ nghĩa.

| Cột | Nội dung | Kiểu PostgreSQL |
|---|---|---|
| `id` | Mã bài nội bộ | BIGSERIAL |
| `url_hash`, `url` | Khóa chống trùng và liên kết gốc | CHAR(64), TEXT |
| `title` | Tiêu đề | TEXT |
| `description` | Mô tả/tóm tắt | TEXT |
| `content` | Nội dung rút gọn API cung cấp | TEXT |
| `source_id`, `source_name` | Mã và tên nguồn; thiếu tên thì dùng tên miền | TEXT |
| `author`, `image_url` | Tác giả và ảnh nếu có | TEXT |
| `published_at` | Thời điểm xuất bản | TIMESTAMPTZ |
| `collected_at` | Thời điểm lưu | TIMESTAMPTZ |
| `query_keyword` | Từ khóa lúc thu thập | TEXT |

`collection_runs` lưu lịch sử mỗi lần chạy; `api_daily_usage` lưu số request theo ngày UTC. Ngân sách chỉ theo dõi request từ bộ mã này, không biết request mà bạn dùng cùng khóa từ ứng dụng khác. PostgreSQL dùng named volume, dữ liệu tồn tại khi container dừng.

**Về “nội dung” trong checklist:** NewsAPI không cung cấp toàn văn bài báo; trường `content` bị rút gọn tới 200 ký tự theo tài liệu. Bộ mã lưu nguyên phần API trả về cùng mô tả và URL. Khi nộp bài ghi rõ giới hạn này. Nếu giảng viên yêu cầu toàn văn, phải bổ sung nguồn/phương thức thu thập phù hợp; bộ mã hiện tại không có bước lấy toàn văn từ website báo.

## 7. Chạy tự động

Sau khi lấy dữ liệu lần đầu thành công:

```bash
docker compose --profile scheduled up -d collector
docker compose logs -f collector
```

Collector chạy ngay khi khởi động rồi lặp mỗi sáu giờ. Ctrl+C khi đang xem log chỉ thoát màn hình theo dõi, không dừng container. Dừng thu thập tự động:

```bash
docker compose stop collector
```

Thu thập thủ công lại:

```bash
docker compose run --rm collector python collect_news.py
```

Khi chạy thủ công đồng thời với collector định kỳ, khóa PostgreSQL ngăn hai lần thu thập thực hiện cùng lúc. Chờ lần hiện tại xong hoặc dừng collector rồi chạy lại.

Sửa `COLLECT_INTERVAL_SECONDS` trong `.env` để đổi chu kỳ, sau đó tạo lại container bằng lệnh `docker compose --profile scheduled up -d --force-recreate collector`. Mặc định sáu giờ; script không cho vòng lặp ngắn hơn một giờ. Máy Windows, Docker Desktop và môi trường WSL cần tiếp tục hoạt động; khi máy ngủ hoặc tắt, việc thu thập tạm ngừng. Đây là lịch chạy của dự án trên máy bạn.

Thu thập một khoảng cụ thể (đổi ngày cho nằm trong phạm vi gói API cho phép):

```bash
docker compose run --rm collector python collect_news.py --from 2026-09-20T00:00:00Z --to 2026-09-25T23:59:59Z
```

## 8. Kiểm tra kết nối và dashboard trong Superset

Trong **Settings → Database Connections**, có kết nối “Tin tức Việt Nam”. Chọn Edit, Test Connection nếu muốn kiểm tra lại. Bộ khởi tạo đã cấu hình URI tương đương:

```text
postgresql+psycopg2://news:MAT_KHAU_POSTGRES@postgres:5432/news_db
```

Lấy mật khẩu từ `.env` trên máy bạn. Bên trong Docker, hostname là `postgres`, không phải `localhost`. Không dùng mật khẩu đăng nhập Superset thay cho mật khẩu PostgreSQL. Bộ mã không mở cổng PostgreSQL ra Windows; truy vấn qua SQL Lab hoặc `docker compose exec`.

Trong **Datasets** có:

- `public.v_articles`: chi tiết bài, cột ngày Việt Nam `published_date_vn`.
- `public.v_daily_news_complete`: tổng bài theo ngày, có ngày bằng 0 giữa ngày sớm nhất và muộn nhất đã lưu.

Dashboard được tạo với:

| Thành phần | Ý nghĩa | Dữ liệu/thiết lập chính |
|---|---|---|
| Tổng số bài đã lưu | Số bản ghi không trùng URL | Big Number; `COUNT(*)` |
| Số nguồn tin | Số tên nguồn khác nhau | Big Number; `COUNT(DISTINCT source_name)` |
| Số bài theo ngày | Xu hướng lượng bài đã lưu | Line; ngày `news_date`, `SUM(article_count)`, ngày Việt Nam |
| 10 nguồn có nhiều bài nhất | Nguồn xuất hiện nhiều nhất trong dữ liệu | Bar; `source_name`, `COUNT(*)`, giảm dần, giới hạn 10 |
| Tỷ trọng bài theo nguồn | Cơ cấu bài theo nguồn | Donut; toàn bộ tên nguồn, `COUNT(*)` |
| Danh sách bài báo | Kiểm tra tiêu đề, nguồn, ngày, URL | Table; tối đa 200 bài gần nhất, 10 dòng/trang |

Biểu đồ tỷ trọng lấy tối đa 10.000 nguồn, đủ rộng cho bài thực hành; nếu thực tế vượt mức đó phải tăng giới hạn hoặc gộp nhóm “Khác”. Bảng bài báo chỉ là phần đối chiếu, không dùng số dòng bảng này làm tổng số bài. Dataset và biểu đồ mặc định không giới hạn thời gian, chỉ hiển thị dữ liệu đã lưu. Dashboard có ghi chú phạm vi để tránh hiểu nhầm số lượng nguồn là độ tin cậy hoặc lượt đọc.

Sau khi thu thập, chọn **Refresh dashboard / Force refresh** nếu thấy số liệu cũ; bộ cấu hình dùng cache 60 giây và đặt chu kỳ làm mới dashboard 300 giây. Dashboard refresh truy vấn cơ sở dữ liệu, không trực tiếp gọi NewsAPI. Thời điểm `published_at` trong bảng chi tiết được lưu theo UTC; biểu đồ ngày dùng giờ Việt Nam UTC+7.

### Nếu cần tạo/sửa biểu đồ thủ công

1. Menu Charts → + Chart → chọn dataset → chọn kiểu biểu đồ.
2. Với hai chỉ số, chọn Big Number, tạo SQL metric theo bảng trên.
3. Với đường theo ngày, chọn dataset `v_daily_news_complete`, Line Chart, X-axis `news_date`, Time grain Day, metric `SUM(article_count)`, Time range No filter.
4. Với Top 10, chọn dataset `v_articles`, Bar Chart (có thể dùng kiểu Bar/ECharts trong giao diện), dimension `source_name`, metric `COUNT(*)`, sắp giảm dần, giới hạn 10. Không đặt time grain cho trục nguồn tin.
5. Với Donut, chọn dataset `v_articles`, Pie Chart, dimension `source_name`, metric `COUNT(*)`, bật Donut, không giới hạn Top 10 nếu muốn tỷ trọng toàn bộ nguồn.
6. Save và chọn dashboard “Theo dõi và phân tích tin tức Việt Nam”. Vào Edit dashboard để đổi kích thước, vị trí; lưu lại.

Nếu bước bootstrap chưa tạo dashboard, có thể chạy lại:

```bash
docker compose run --rm superset-init
```

Lệnh này tạo/cập nhật đúng các datasets/charts/dashboard có tên trong bộ mã, có thể thay thế các chỉnh sửa bạn tự thực hiện trên những tài sản đó. Chỉ chạy lại khi muốn phục hồi cấu hình mẫu. Bộ mã ghim **Superset 5.0.0-dev** để phù hợp script khởi tạo; không đổi sang `latest` tùy tiện.

## 9. Đối chiếu số liệu và chuẩn bị bài nộp

Chạy kiểm tra dữ liệu thật:

```bash
docker compose run --rm collector python verify_database.py
```

Trong SQL Lab → SQL Editor, chọn database “Tin tức Việt Nam”, schema `public`; chạy từng truy vấn trong `sql/analysis_queries.sql`. Hoặc xem 5 bài mới nhất bằng:

```bash
docker compose exec postgres psql -U news -d news_db -c "SELECT title,source_name,published_at FROM articles ORDER BY published_at DESC LIMIT 5;"
```

Chụp các bằng chứng sau:

- Python đã gọi API, log số bài nhận và số bài thêm.
- PostgreSQL có các trường tiêu đề, nội dung rút gọn, nguồn, ngày xuất bản, URL.
- Test Connection thành công và datasets có dữ liệu.
- Dashboard đầy đủ biểu đồ ngày, Top 10 nguồn và chi tiết bài.
- Nhật ký thu thập có thời gian, trạng thái và giới hạn kết quả nếu có.
- Chạy lại cùng khoảng ngày không phát sinh bản ghi trùng URL. Tổng bài có thể tăng nếu API bổ sung bài mới; cần kiểm tra truy vấn trùng URL thay vì chỉ so tổng số.

Mẫu diễn giải khi thuyết trình (điền số liệu thực tế, không dùng số giả):

> Hệ thống gọi NewsAPI với từ khóa Vietnam, làm sạch dữ liệu và lưu vào PostgreSQL. Superset kết nối cơ sở dữ liệu để hiển thị tổng số bài, xu hướng theo ngày và các nguồn có nhiều bài nhất. Trong khoảng ... đến ..., hệ thống đã lưu ... bài từ ... nguồn. Ngày ... có số bài đã lưu cao nhất. Nguồn ... đứng đầu về số lượng bài đã thu thập. Kết quả phản ánh phạm vi dữ liệu đã lấy và giới hạn gói API; không phản ánh toàn bộ tin tức, số độc giả hay độ tin cậy của từng nguồn.

## 10. Lỗi thường gặp

| Biểu hiện/mã lỗi | Cách xử lý |
|---|---|
| `docker: command not found` trong Ubuntu | Mở Docker Desktop và bật WSL Integration đúng Ubuntu |
| Cannot connect to Docker daemon | Kiểm tra Docker Desktop đã chạy và `docker info` hoạt động |
| `apiKeyInvalid`, `apiKeyMissing`, `missing_api_key` | Kiểm tra `NEWSAPI_KEY` trong `.env`; không thêm dấu cách vào khóa |
| `rateLimited`, `apiKeyExhausted` | Kiểm tra quota NewsAPI, dừng gọi thêm và chờ chu kỳ quota theo tài khoản |
| `local_daily_budget_exhausted` | Bộ mã đã chạm ngân sách nội bộ ngày UTC; dữ liệu đã lưu được giữ nguyên |
| `maximumResultsReached` hoặc trạng thái `partial` | Gói API/giới hạn trang chặn kết quả bổ sung; ghi rõ phạm vi, không coi là dữ liệu toàn bộ |
| `parameterInvalid`, `parameterInvalidValue` | Kiểm tra ngày trong khoảng lịch sử của gói, `from` trước `to`, không đặt `language=vi` |
| `another_collector_is_running` | Một lần thu thập khác đang chạy; chờ hoặc dừng collector định kỳ |
| `network_error` | Kiểm tra mạng máy Windows/Docker; chạy lại lệnh thu thập |
| Superset-init thoát lỗi | Xem `docker compose logs --tail 100 superset-init`; giữ image đã ghim, không xóa dữ liệu để thử ngẫu nhiên |
| Không kết nối PostgreSQL trong Superset | Host `postgres`, database `news_db`, username `news`, đúng mật khẩu PostgreSQL |
| Cổng 8088 bị chiếm | Sửa trong compose thành `'127.0.0.1:8089:8088'`, chạy lại; mở localhost:8089 |
| Dashboard trống | Xem log thu thập, chạy verify_database; kiểm tra bộ lọc và làm mới dashboard |
| Chưa có nội dung toàn văn | Đây là giới hạn của NewsAPI; bộ mã lưu phần rút gọn và URL nguồn |

Xem trạng thái/log:

```bash
docker compose ps -a
docker compose logs --tail 100 superset-init
docker compose logs --tail 100 superset
docker compose logs --tail 100 collector
```

Log collector định kỳ chỉ tồn tại khi đã bật service đó. Với một lần chạy `run --rm`, đọc kết quả ngay trong terminal và bảng `collection_runs`.

## 11. Dừng, khởi động lại và sao lưu

Dừng container, giữ dữ liệu:

```bash
docker compose --profile scheduled down
```

Khởi động lại:

```bash
docker compose up -d --wait superset
docker compose --profile scheduled up -d collector
```

Không dùng `down -v` trong quy trình thông thường vì tùy chọn đó xóa volume chứa cả dữ liệu tin tức và cấu hình Superset.

Sao lưu database bài báo và cấu hình dashboard:

```bash
mkdir -p backups
docker compose exec -T postgres pg_dump -U news news_db > backups/news_db.sql
docker compose exec -T postgres pg_dump -U news superset_meta > backups/superset_meta.sql
```

Giữ `.env` riêng trên máy để tiếp tục truy cập dữ liệu đã tạo, đặc biệt `SUPERSET_SECRET_KEY` cần cho cấu hình kết nối đã mã hóa. Khi nộp nguồn, kèm `.env.example`, không kèm `.env` hay bản sao chứa bí mật.

## 12. Tài liệu chính thức

- [NewsAPI – Everything và các tham số/định dạng kết quả](https://newsapi.org/docs/endpoints/everything)
- [NewsAPI – Hạn mức, độ trễ và giới hạn nội dung](https://newsapi.org/pricing)
- [NewsAPI – Mã lỗi](https://newsapi.org/docs/errors)
- [Superset – Cài đặt Docker Compose](https://superset.apache.org/docs/installation/docker-compose/)
- [Superset – Tạo dashboard đầu tiên](https://superset.apache.org/docs/using-superset/creating-your-first-dashboard/)
- [Docker Desktop – WSL 2 và bật WSL Integration](https://docs.docker.com/desktop/features/wsl/)

Superset dùng image dev để có sẵn driver PostgreSQL theo hướng dẫn Docker Compose chính thức. Đây là bản cấu hình phục vụ thực hành; SQL Lab và dashboard dùng PostgreSQL, không tạo một trang web thay thế Superset.
