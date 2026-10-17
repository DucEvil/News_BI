# Nhãn kiểm chứng do người học gán

Pipeline xuất `output/th2/labeling_template.jsonl` chứa tối đa 50 bài thật,
chưa có nhãn. Đọc tiêu đề/mô tả của mỗi bài, điền `sentiment`, `topic`,
`reviewer` và đặt `reviewed: true`; lưu bản đã gán nhãn vào `evaluation/labels.jsonl`.
Không sao chép dự đoán Gemini làm nhãn thật. Khi chưa có nhãn hoặc dự đoán,
báo cáo không công bố accuracy/F1.

Sentiment: `positive`, `neutral`, `negative`, `mixed`.
Topic: `kinh_te`, `chinh_tri`, `cong_nghe`, `van_hoa`, `xa_hoi`, `y_te`,
`giao_duc`, `the_thao`, `moi_truong`, `khac`.

Nên gán nhãn độc lập trước khi xem kết quả AI, có đủ mẫu cho các lớp; nếu có
hai người kiểm tra thì giải quyết bất đồng trước khi đánh giá. Giữ tập kiểm tra
riêng khi thay prompt/mô hình. Không dùng chỉ số trên tập nhỏ để tuyên bố
hiệu quả cho mọi ngôn ngữ hay mọi loại tin.
