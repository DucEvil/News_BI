import os
from superset.app import create_app
from superset import security_manager

app = create_app()
with app.app_context():
    name = os.environ.get('SUPERSET_ADMIN_USERNAME', 'admin')
    if not security_manager.find_user(username=name):
        user = security_manager.add_user(
            username=name, first_name='Sinh viên', last_name='BI',
            email='student@example.local', role=security_manager.find_role('Admin'),
            password=os.environ['SUPERSET_ADMIN_PASSWORD'],
        )
        if not user:
            raise RuntimeError('Không tạo được tài khoản quản trị Superset')
    print('Đã kiểm tra tài khoản quản trị.')
