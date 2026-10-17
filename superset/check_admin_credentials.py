"""Kiểm tra mật khẩu .env với tài khoản hiện có; chỉ đồng bộ khi có cờ tường minh."""
import argparse
import os


def main():
    parser=argparse.ArgumentParser(description='Check local Superset admin credentials without printing secrets')
    parser.add_argument('--sync-password',action='store_true',
                        help='Set the existing account password to SUPERSET_ADMIN_PASSWORD from the environment')
    args=parser.parse_args()
    username=os.environ.get('SUPERSET_ADMIN_USERNAME','admin')
    password=os.environ.get('SUPERSET_ADMIN_PASSWORD','')
    if not password:
        print('SUPERSET_ADMIN_PASSWORD is empty. Set it in .env.')
        return 2
    from superset.app import create_app
    from superset import security_manager
    from werkzeug.security import check_password_hash
    app=create_app()
    with app.app_context():
        user=security_manager.find_user(username=username)
        if not user:
            print('Configured Superset account does not exist. Check SUPERSET_ADMIN_USERNAME in .env.')
            return 2
        if not user.active:
            print('Configured Superset account is inactive. No account changes were made.')
            return 2
        if check_password_hash(user.password,password):
            print('Superset credentials match .env. No password changes needed.')
            return 0
        if not args.sync_password:
            print('Superset password does not match .env. Updating .env does not update an existing account.')
            print('Use your existing login password in .env, or explicitly run start-ai.ps1 -SyncAdminPassword.')
            return 2
        security_manager.reset_password(user.id,password)
        if not check_password_hash(user.password,password):
            print('Password synchronization did not pass verification.')
            return 2
        print('Existing Superset account password synchronized with .env. Dashboards and news data preserved.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
