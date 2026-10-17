"""Superset REST adapter dùng bởi MCP; các công cụ chỉ thao tác tài sản TH2 cố định."""
import http.cookiejar
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class SupersetError(Exception):
    pass


class SupersetClient:
    def __init__(self):
        self.base=os.environ.get('SUPERSET_INTERNAL_URL','http://superset:8088').rstrip('/')
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.token=None
        self.csrf=None

    def request(self,method,path,payload=None,auth=True,_retry=True):
        if auth and not self.token:
            self.login()
        headers={'Accept':'application/json'}
        if self.token and auth:
            headers['Authorization']='Bearer '+self.token
        if method not in ('GET','HEAD'):
            headers['Content-Type']='application/json'
            if self.csrf and auth:
                headers.update({'X-CSRFToken':self.csrf,'Referer':self.base+'/'})
        request=urllib.request.Request(self.base+path,
            data=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None,
            headers=headers,method=method)
        try:
            with self.opener.open(request,timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code==401 and auth and _retry:
                self.token=None
                self.csrf=None
                return self.request(method,path,payload,auth=auth,_retry=False)
            raise SupersetError(f"superset_http_{exc.code}: {method} {path.split('?')[0]}") from None
        except (urllib.error.URLError,TimeoutError,OSError,ValueError):
            raise SupersetError('superset_connection_or_json_error') from None

    def login(self):
        response=self.request('POST','/api/v1/security/login',{
            'username':os.environ.get('SUPERSET_ADMIN_USERNAME','admin'),
            'password':os.environ['SUPERSET_ADMIN_PASSWORD'],'provider':'db','refresh':False},auth=False)
        self.token=response['access_token']
        self.csrf=self.request('GET','/api/v1/security/csrf_token/')['result']

    def resources(self,name):
        rows=[]
        for page in range(20):
            q=urllib.parse.urlencode({'q':f'(page:{page},page_size:100)'})
            response=self.request('GET',f'/api/v1/{name}/?{q}')
            batch=response.get('result',[])
            rows.extend(batch)
            if len(batch)<100:
                break
        return rows

    def upsert(self,resource,existing,payload):
        if existing:
            identity=existing['id']
            self.request('PUT',f'/api/v1/{resource}/{identity}',payload)
            return identity
        response=self.request('POST',f'/api/v1/{resource}/',payload)
        return response.get('id') or response['result']['id']

    def chart_data(self,chart_id):
        if type(chart_id) is not int or chart_id<=0:
            raise ValueError('invalid_chart_id')
        # Cho phép đọc đúng hai dashboard của dự án, không cung cấp arbitrary SQL qua MCP.
        dashboard=next((d for d in self.resources('dashboard') if d.get('slug')=='tin-tuc-ai-th2'),None)
        if not dashboard:
            raise SupersetError('th2_dashboard_not_found')
        charts=self.request('GET',f"/api/v1/dashboard/{dashboard['id']}/charts")['result']
        if chart_id not in {chart['id'] for chart in charts}:
            raise ValueError('chart_not_in_th2_dashboard')
        response=self.request('GET',f'/api/v1/chart/{chart_id}/data/?force=true')
        return response['result']
