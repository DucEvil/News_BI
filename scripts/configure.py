"""Tạo .env một lần; không in khóa NewsAPI ra màn hình."""
import getpass
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / '.env'
if target.exists():
    raise SystemExit('Đã có .env. Dùng nano .env để sửa, tệp hiện tại được giữ nguyên.')
key = getpass.getpass('Dán khóa NewsAPI rồi Enter (không hiện ký tự): ').strip()
if not key or not key.isalnum():
    raise SystemExit('Khóa phải là chuỗi chữ/số, không được để trống.')
password = getpass.getpass('Đặt mật khẩu đăng nhập Superset (ít nhất 8 ký tự): ')
if len(password) < 8 or any(c in password for c in ['\n', '\r', "'"]):
    raise SystemExit('Mật khẩu cần ít nhất 8 ký tự, không có dấu nháy đơn hoặc xuống dòng.')
values = {
    'NEWSAPI_KEY': key,
    'POSTGRES_PASSWORD': secrets.token_hex(20),
    'SUPERSET_SECRET_KEY': secrets.token_hex(48),
    'SUPERSET_ADMIN_PASSWORD': "'" + password + "'",
}
content = (root / '.env.example').read_text(encoding='utf-8')
for name, value in values.items():
    content = content.replace(name + '=\n', name + '=' + value + '\n')
target.write_text(content, encoding='utf-8')
target.chmod(0o600)
print('Đã tạo .env. Tài khoản Superset: admin. Mật khẩu là mật khẩu bạn vừa đặt.')
