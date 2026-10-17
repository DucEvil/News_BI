"""Tạo .env một lần; không in khóa NewsAPI ra màn hình."""
import argparse
import getpass
import secrets
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

root = Path(__file__).resolve().parents[1]
target = root / '.env'
parser = argparse.ArgumentParser(description='Cấu hình NewsAPI và Superset trên máy cá nhân')
parser.add_argument('--prepare', action='store_true',
                    help='Sinh mật khẩu, để trống khóa API để điền trong trình soạn thảo')
parser.add_argument('--add-ai', action='store_true', help='Bổ sung biến Gemini/AI còn thiếu vào .env, giữ nguyên bí mật hiện có')
args = parser.parse_args()
if args.add_ai:
    if not target.exists():
        raise SystemExit('Tạo .env trước bằng --prepare.')
    existing = target.read_text(encoding='utf-8-sig')
    names = {line.split('=',1)[0].strip() for line in existing.splitlines() if '=' in line and not line.lstrip().startswith('#')}
    additions = [line for line in (root / '.env.example').read_text(encoding='utf-8').splitlines()
                 if line.startswith(('GEMINI_', 'AI_')) and line.split('=',1)[0] not in names]
    if additions:
        with target.open('a',encoding='utf-8') as handle:
            handle.write('\n# TH2 Gemini AI\n'+'\n'.join(additions)+'\n')
    print('Đã kiểm tra biến TH2; giữ nguyên khóa API và mật khẩu hiện có. Điền GEMINI_API_KEY trong .env khi sẵn sàng.')
    raise SystemExit(0)
if target.exists():
    raise SystemExit('Đã có .env. Mở tệp để sửa; tệp hiện tại được giữ nguyên.')
key = '' if args.prepare else getpass.getpass('Dán khóa NewsAPI rồi Enter (không hiện ký tự): ').strip()
if not args.prepare and (not key or not key.isalnum()):
    raise SystemExit('Khóa phải là chuỗi chữ/số, không được để trống.')
password = secrets.token_urlsafe(18) if args.prepare else getpass.getpass('Đặt mật khẩu đăng nhập Superset (ít nhất 8 ký tự): ')
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
if args.prepare:
    print('Đã tạo .env. Điền NEWSAPI_KEY rồi lưu tệp. Tài khoản: admin; mật khẩu ở SUPERSET_ADMIN_PASSWORD.')
else:
    print('Đã tạo .env. Tài khoản Superset: admin. Mật khẩu là mật khẩu bạn vừa đặt.')
