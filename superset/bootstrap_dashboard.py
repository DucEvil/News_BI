"""Tạo tài sản Superset 5.0.0; chạy sau superset init, bên trong container."""
import json
import os
from sqlalchemy.engine import URL
from superset.app import create_app
from superset import db, security_manager


def metric(sql, label):
    return {'expressionType': 'SQL', 'sqlExpression': sql, 'label': label,
            'optionName': 'metric_' + label, 'hasCustomLabel': True}


def query_context(dataset_id, params):
    """Lưu truy vấn để API dữ liệu biểu đồ hoạt động ngay sau bootstrap."""
    viz = params['viz_type']
    query = {'time_range': 'No filter', 'filters': [], 'columns': [],
             'metrics': [], 'orderby': [], 'row_limit': params['row_limit'],
             'extras': {'where': '', 'having': ''}, 'post_processing': []}
    if viz == 'table':
        query['columns'] = params['all_columns']
        query['orderby'] = [['published_at', False]]
    elif viz == 'big_number_total':
        query['metrics'] = [params['metric']]
    elif viz == 'pie':
        query['columns'] = params['groupby']
        query['metrics'] = [params['metric']]
        query['orderby'] = [[params['metric'], False]]
    else:
        query['columns'] = [params['x_axis']]
        query['metrics'] = params['metrics']
        query['orderby'] = ([[params['metrics'][0], False]]
                            if viz == 'echarts_timeseries_bar' else [[params['x_axis'], True]])
        if viz == 'echarts_timeseries_bar':
            # Trục danh mục nằm bên trái: số lớn nhất ở trên cùng.
            query['post_processing'] = [{'operation': 'sort', 'options': {
                'by': params['metrics'][0]['label'], 'ascending': True}}]
    return {'datasource': {'id': dataset_id, 'type': 'table'}, 'queries': [query],
            'form_data': params, 'result_format': 'json', 'result_type': 'full', 'force': False}


app = create_app()
with app.app_context():
    # Các models Superset cần application context ngay khi import.
    from superset.models.core import Database
    from superset.connectors.sqla.models import SqlaTable
    from superset.models.slice import Slice
    from superset.models.dashboard import Dashboard

    admin = security_manager.find_user(username=os.environ.get('SUPERSET_ADMIN_USERNAME', 'admin'))
    database = db.session.query(Database).filter_by(database_name='Tin tức Việt Nam').one_or_none()
    if database is None:
        database = Database(database_name='Tin tức Việt Nam', expose_in_sqllab=True)
        db.session.add(database)
    database.set_sqlalchemy_uri(URL.create(
        'postgresql+psycopg2', username='news', password=os.environ['POSTGRES_PASSWORD'],
        host='postgres', port=5432, database='news_db',
    ).render_as_string(hide_password=False))
    db.session.flush()
    datasets = {}
    for table, time_col in [('v_articles', 'published_date_vn'), ('v_daily_news_complete', 'news_date')]:
        ds = db.session.query(SqlaTable).filter_by(database_id=database.id, schema='public', table_name=table).one_or_none()
        if ds is None:
            ds = SqlaTable(table_name=table, schema='public', database=database, owners=[admin])
            db.session.add(ds)
            db.session.flush()
        ds.fetch_metadata()
        ds.main_dttm_col = time_col
        datasets[table] = ds
    db.session.commit()
    count = metric('COUNT(*)', 'Số bài báo')
    sources = metric('COUNT(DISTINCT source_name)', 'Số nguồn tin')
    total_per_day = metric('SUM(article_count)', 'Số bài theo ngày')
    definitions = [
        ('Tổng số bài đã lưu', 'big_number_total', 'v_articles', {'metric': count, 'subheader': 'Bài báo không trùng URL'}),
        ('Số nguồn tin', 'big_number_total', 'v_articles', {'metric': sources, 'subheader': 'Nguồn có bài đã lưu'}),
        ('Số bài theo ngày (giờ Việt Nam)', 'echarts_timeseries_line', 'v_daily_news_complete', {
            'x_axis': 'news_date', 'granularity_sqla': 'news_date', 'time_grain_sqla': 'P1D',
            'metrics': [total_per_day], 'groupby': [], 'show_legend': False,
            'rich_tooltip': True, 'x_axis_title': 'Ngày xuất bản', 'y_axis_title': 'Số bài đã lưu',
            'markerEnabled': True, 'forecastEnabled': False}),
        ('10 nguồn có nhiều bài nhất', 'echarts_timeseries_bar', 'v_articles', {
            'metrics': [count], 'x_axis': 'source_name', 'groupby': [],
            'row_limit': 10, 'order_desc': True, 'show_legend': False,
            'show_value': True, 'orientation': 'horizontal', 'x_axis_force_categorical': True,
            'x_axis_title': '', 'y_axis_title': 'Số bài',
            'x_axis_sort': count['label'], 'x_axis_sort_asc': True}),
        ('Tỷ trọng bài theo nguồn (toàn bộ nguồn)', 'pie', 'v_articles', {
            'metric': count, 'groupby': ['source_name'], 'row_limit': 10000,
            'donut': True, 'show_legend': True, 'show_labels': False,
            'legend_type': 'scroll', 'legend_orientation': 'right',
            'label_type': 'key_percent', 'sort_by_metric': True}),
        ('Danh sách bài báo', 'table', 'v_articles', {
            'query_mode': 'raw', 'all_columns': ['published_at', 'title', 'source_name', 'description', 'url'],
            'order_by_cols': [json.dumps(['published_at', False])],
            'row_limit': 200, 'page_length': 10, 'include_search': True}),
    ]
    charts = []
    for title, viz, table, options in definitions:
        ds = datasets[table]
        chart = db.session.query(Slice).filter_by(slice_name=title, datasource_id=ds.id, datasource_type='table').one_or_none()
        if chart is None:
            chart = Slice(slice_name=title, datasource_id=ds.id, datasource_type='table', owners=[admin])
            db.session.add(chart)
        chart.viz_type = viz
        params = {'viz_type': viz, 'datasource': f'{ds.id}__table', 'time_range': 'No filter',
                  'adhoc_filters': [], 'row_limit': 10000, 'color_scheme': 'supersetColors', **options}
        chart.params = json.dumps(params, ensure_ascii=False)
        db.session.flush()
        params['slice_id'] = chart.id
        chart.params = json.dumps(params, ensure_ascii=False)
        chart.query_context = json.dumps(query_context(ds.id, params), ensure_ascii=False)
        charts.append(chart)
    dashboard = db.session.query(Dashboard).filter_by(slug='tin-tuc-viet-nam').one_or_none()
    if dashboard is None:
        dashboard = Dashboard(slug='tin-tuc-viet-nam', owners=[admin])
        db.session.add(dashboard)
    dashboard.dashboard_title = 'Theo dõi và phân tích tin tức Việt Nam'
    dashboard.published = True
    dashboard.slices = charts
    dashboard.description = 'Dữ liệu NewsAPI, truy vấn Vietnam. Các chỉ số chỉ phản ánh bài đã thu thập.'
    layout = {
        'DASHBOARD_VERSION_KEY': 'v2',
        'ROOT_ID': {'id': 'ROOT_ID', 'type': 'ROOT', 'children': ['GRID_ID']},
        'GRID_ID': {'id': 'GRID_ID', 'type': 'GRID', 'children': [], 'parents': ['ROOT_ID']},
        'HEADER_ID': {'id': 'HEADER_ID', 'type': 'HEADER', 'meta': {'text': dashboard.dashboard_title}},
    }
    for index, group in enumerate([(charts[:2], 6, 18), ([charts[2]], 12, 45),
                                   ([charts[3]], 12, 50), ([charts[4]], 12, 45),
                                   ([charts[5]], 12, 50)]):
        items, width, height = group
        row_id = f'ROW-{index}'
        layout['GRID_ID']['children'].append(row_id)
        layout[row_id] = {'id': row_id, 'type': 'ROW', 'children': [], 'parents': ['ROOT_ID', 'GRID_ID'], 'meta': {'background': 'BACKGROUND_TRANSPARENT'}}
        for chart in items:
            node = f'CHART-{chart.id}'
            layout[row_id]['children'].append(node)
            layout[node] = {'id': node, 'type': 'CHART', 'children': [],
                            'parents': ['ROOT_ID', 'GRID_ID', row_id],
                            'meta': {'chartId': chart.id, 'sliceName': chart.slice_name,
                                     'width': width, 'height': height}}
    note = ('### Phạm vi dữ liệu\n'
            'Truy vấn **Vietnam**, mọi ngôn ngữ mặc định; có thể gồm tin quốc tế nói về Việt Nam.\n'
            'Các chỉ số là số bài **đã lưu**, không phải tổng số tin tức thực tế. '
            'Gói Developer có độ trễ; giới hạn trang có thể làm thiếu dữ liệu. '
            'Ngày bằng 0 chỉ nghĩa là chưa lưu được bài trong ngày đó. '
            'Nguồn có nhiều bài chưa đồng nghĩa có nhiều độc giả hay đáng tin cậy hơn. '
            'Nội dung là phần rút gọn do API cung cấp.')
    layout['GRID_ID']['children'].append('ROW-NOTE')
    layout['ROW-NOTE'] = {'id': 'ROW-NOTE', 'type': 'ROW', 'children': ['NOTE'], 'parents': ['ROOT_ID', 'GRID_ID'], 'meta': {'background': 'BACKGROUND_TRANSPARENT'}}
    layout['NOTE'] = {'id': 'NOTE', 'type': 'MARKDOWN', 'children': [], 'parents': ['ROOT_ID', 'GRID_ID', 'ROW-NOTE'], 'meta': {'code': note, 'width': 12, 'height': 28}}
    dashboard.position_json = json.dumps(layout, ensure_ascii=False)
    dashboard.json_metadata = json.dumps({'refresh_frequency': 300, 'color_scheme': 'supersetColors', 'timed_refresh_immune_slices': [], 'expanded_slices': {}}, ensure_ascii=False)
    db.session.commit()
    print('Đã tạo/cập nhật 2 datasets, 6 charts và dashboard /superset/dashboard/tin-tuc-viet-nam/.')
