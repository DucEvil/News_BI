"""Định nghĩa dashboard TH2; được triển khai QUA công cụ MCP ensure_ai_dashboard."""
import json

SLUG='tin-tuc-ai-th2'
TITLE='TH2 · Phân tích tin tức với Gemini AI'


def metric(sql,label):
    return {'expressionType':'SQL','sqlExpression':sql,'label':label,
            'optionName':'metric_'+label,'hasCustomLabel':True}


def definitions():
    count=metric('COUNT(*)','Số bài')
    return [
        ('TH2 · Bài đã phân tích','big_number_total','v_ai_articles',
         {'metric':metric("SUM(CASE WHEN analysis_status='analyzed' THEN 1 ELSE 0 END)",'Đã phân tích'),
          'subheader':'Kết quả Gemini đã lưu, không gồm bài chờ'}),
        ('TH2 · Tỷ lệ bao phủ AI (%)','big_number_total','v_ai_articles',
         {'metric':metric("100.0*COUNT(*) FILTER (WHERE analysis_status='analyzed')/NULLIF(COUNT(*),0)",'Bao phủ (%)'),
          'y_axis_format':'.1f','subheader':'% bài đã có kết quả Gemini'}),
        ('TH2 · Cơ cấu cảm xúc','pie','v_ai_analyzed',
         {'metric':count,'groupby':['sentiment'],'donut':True,'show_labels':True,'label_type':'key_percent'}),
        ('TH2 · Chủ đề tin tức','echarts_timeseries_bar','v_ai_analyzed',
         {'metrics':[count],'x_axis':'topic','groupby':[],'orientation':'horizontal',
          'x_axis_sort':'Số bài','x_axis_sort_asc':True,'show_value':True,'row_limit':10}),
        ('TH2 · Điểm cảm xúc theo ngày','echarts_timeseries_line','v_ai_analyzed',
         {'metrics':[metric('AVG(sentiment_score)','Điểm cảm xúc trung bình')],
          'x_axis':'published_date_vn','groupby':[],'time_grain_sqla':'P1D','markerEnabled':True,
          'y_axis_bounds':[-1,1],'y_axis_title':'Âm: tiêu cực · Dương: tích cực'}),
        ('TH2 · Bài tiêu cực theo nguồn','echarts_timeseries_bar','v_ai_analyzed',
         {'metrics':[metric("COUNT(*) FILTER (WHERE sentiment='negative')",'Bài tiêu cực')],
          'x_axis':'source_name','groupby':[],'row_limit':10,'orientation':'horizontal',
          'x_axis_sort':'Bài tiêu cực','x_axis_sort_asc':True,'show_value':True}),
        ('TH2 · Dự báo lượng bài đã thu thập','echarts_timeseries_line','v_forecast_series',
         {'metrics':[metric('MAX(observed_count)','Đã thu thập'),metric('MAX(predicted_count)','Dự báo')],
          'x_axis':'news_date','groupby':[],'show_legend':True,'time_grain_sqla':'P1D','markerEnabled':True,
          'y_axis_title':'Số bài đã lưu / ước lượng','forecastEnabled':False}),
        ('TH2 · Kiểm định dự báo theo thời gian','table','v_forecast_metrics',
         {'query_mode':'raw','all_columns':['model_name','mae','smape','test_days','n_observations','train_end'],
          'order_by_cols':[json.dumps(['mae',True])],'page_length':10}),
        ('TH2 · Chi tiết phân tích Gemini','table','v_ai_analyzed',
         {'query_mode':'raw','all_columns':['published_at','title','source_name','sentiment','topic','summary_vi',
                                          'confidence','model_name','url'],
          'order_by_cols':[json.dumps(['published_at',False])],'page_length':10,'include_search':True}),
        ('TH2 · Nhật ký phân tích AI','table','ai_runs',
         {'query_mode':'raw','all_columns':['id','started_at','status','model_name','articles_analyzed',
                                          'requests_made','latency_seconds','error_code'],
          'order_by_cols':[json.dumps(['id',False])],'page_length':10}),
    ]


def build_context(dataset_id,params):
    viz=params['viz_type']
    query={'time_range':'No filter','filters':[],'columns':[],'metrics':[],
           'orderby':[],'row_limit':params['row_limit'],'extras':{'where':'','having':''},'post_processing':[]}
    if viz=='table':
        query['columns']=params['all_columns']
        query['orderby']=[json.loads(order) for order in params.get('order_by_cols',[])]
    elif viz=='big_number_total':
        query['metrics']=[params['metric']]
    elif viz=='pie':
        query['columns']=params['groupby']
        query['metrics']=[params['metric']]
        query['orderby']=[[params['metric'],False]]
    else:
        query['columns']=[params['x_axis']]
        query['metrics']=params['metrics']
        if viz=='echarts_timeseries_bar':
            query['orderby']=[[params['metrics'][0],False]]
            query['post_processing']=[{'operation':'sort','options':{'by':params['metrics'][0]['label'],'ascending':True}}]
        else:
            query['orderby']=[[params['x_axis'],True]]
    return {'datasource':{'id':dataset_id,'type':'table'},'queries':[query],'form_data':params,
            'force':False,'result_format':'json','result_type':'full'}


def layout(charts):
    value={'DASHBOARD_VERSION_KEY':'v2',
        'ROOT_ID':{'id':'ROOT_ID','type':'ROOT','children':['GRID_ID']},
        'GRID_ID':{'id':'GRID_ID','type':'GRID','parents':['ROOT_ID'],'children':[]},
        'HEADER_ID':{'id':'HEADER_ID','type':'HEADER','meta':{'text':TITLE}}}
    groups=[(charts[:2],6,18),(charts[2:4],6,42),([charts[4]],12,40),([charts[5]],12,45),
            ([charts[6]],12,45),([charts[7]],12,35),([charts[8]],12,50),([charts[9]],12,35)]
    note=('### TH2: phạm vi và cách đọc\n'
          '**Chưa điền GEMINI_API_KEY thì biểu đồ cảm xúc/chủ đề để trống, KPI AI bằng 0; xem nhật ký waiting_key.** '
          'Sau khi điền khóa và chạy worker, Superset tự đọc kết quả đã lưu. '
          'Chỉ phân tích phần tiêu đề/mô tả/nội dung rút gọn NewsAPI; không phải toàn văn. '
          'confidence do mô hình tự ước lượng, không phải accuracy đã kiểm định. '
          'Dự báo áp dụng cho **số bài đã thu thập**, có thiên lệch quota và ngày máy không chạy; '
          'MAE/sMAPE là backtest trên số ít ngày, chưa đủ kết luận khả năng tổng quát. '
          'Không dùng số lượng tin tiêu cực để kết luận uy tín nguồn. '
          'Xem output/th2/BAO_CAO_KY_THUAT.md để biết trạng thái kiểm chứng và đánh giá nhãn người.')
    value['GRID_ID']['children'].append('ROW-TH2-NOTE')
    value['ROW-TH2-NOTE']={'id':'ROW-TH2-NOTE','type':'ROW','children':['TH2-NOTE'],
        'parents':['ROOT_ID','GRID_ID'],'meta':{'background':'BACKGROUND_TRANSPARENT'}}
    value['TH2-NOTE']={'id':'TH2-NOTE','type':'MARKDOWN','children':[],
        'parents':['ROOT_ID','GRID_ID','ROW-TH2-NOTE'],'meta':{'code':note,'width':12,'height':35}}
    for index,(items,width,height) in enumerate(groups):
        row_id=f'ROW-TH2-{index}'
        value['GRID_ID']['children'].append(row_id)
        value[row_id]={'id':row_id,'type':'ROW','parents':['ROOT_ID','GRID_ID'],
            'children':[],'meta':{'background':'BACKGROUND_TRANSPARENT'}}
        for chart in items:
            node=f'CHART-TH2-{chart["id"]}'
            value[row_id]['children'].append(node)
            value[node]={'id':node,'type':'CHART','children':[],'parents':['ROOT_ID','GRID_ID',row_id],
                'meta':{'chartId':chart['id'],'sliceName':chart['title'],'width':width,'height':height}}
    return value


def ensure_dashboard(client):
    database=next((r for r in client.resources('database') if r['database_name']=='Tin tức Việt Nam'),None)
    if not database:
        raise ValueError('news_database_connection_missing_run_th1_init_first')
    all_datasets=client.resources('dataset')
    datasets={}
    times={'v_ai_articles':'published_date_vn','v_ai_analyzed':'published_date_vn',
           'v_forecast_series':'news_date','v_forecast_metrics':'generated_at','ai_runs':'started_at'}
    for name,time_col in times.items():
        existing=next((r for r in all_datasets if r['table_name']==name and r.get('schema')=='public'
                       and (r.get('database') or {}).get('id')==database['id']),None)
        if existing:
            identity=existing['id']
        else:
            identity=client.upsert('dataset',None,{'database':database['id'],'schema':'public','table_name':name})
        client.request('PUT',f'/api/v1/dataset/{identity}',{'main_dttm_col':time_col})
        datasets[name]=identity
    existing_dashboard=next((r for r in client.resources('dashboard') if r.get('slug')==SLUG),None)
    dashboard_id=client.upsert('dashboard',existing_dashboard,{'dashboard_title':TITLE,'slug':SLUG,'published':True})
    existing_charts=client.resources('chart')
    charts=[]
    for title,viz,table,options in definitions():
        ds=datasets[table]
        existing=next((r for r in existing_charts if r['slice_name']==title and r.get('datasource_id')==ds),None)
        params={'viz_type':viz,'datasource':f'{ds}__table','time_range':'No filter',
                'adhoc_filters':[],'row_limit':200,'show_legend':False,'color_scheme':'supersetColors',**options}
        if viz=='pie':
            params['row_limit']=100
            params['show_legend']=True
        payload={'slice_name':title,'viz_type':viz,'datasource_id':ds,'datasource_type':'table',
                 'dashboards':[dashboard_id],'params':json.dumps(params,ensure_ascii=False),
                 'query_context':json.dumps(build_context(ds,params),ensure_ascii=False)}
        identity=client.upsert('chart',existing,payload)
        charts.append({'id':identity,'title':title})
    client.request('PUT',f'/api/v1/dashboard/{dashboard_id}',{'position_json':json.dumps(layout(charts),ensure_ascii=False),
        'json_metadata':json.dumps({'refresh_frequency':300,'color_scheme':'supersetColors',
                                  'timed_refresh_immune_slices':[],'expanded_slices':{}})})
    return {'dashboard_id':dashboard_id,'slug':SLUG,'url':f'http://localhost:8088/superset/dashboard/{SLUG}/',
            'datasets':datasets,'charts':charts}
