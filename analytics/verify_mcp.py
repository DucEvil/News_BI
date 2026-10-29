"""Khởi chạy MCP qua stdio, initialize/list_tools/call_tool và kiểm tra mọi chart thật."""
import asyncio
import json
import os
import sys
from datetime import datetime,timezone
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from analytics.common import write_json
from analytics.errors import failure_message
from analytics.dashboard import definitions


def unpack(result):
    if result.isError:
        raise RuntimeError('mcp_tool_failed: '+''.join(c.text for c in result.content if c.type=='text')[:300])
    if result.structuredContent:
        data=result.structuredContent
        return data.get('result',data)
    return json.loads(''.join(c.text for c in result.content if c.type=='text'))


async def verify():
    # SDK không tự kế thừa toàn bộ environment của tiến trình cha.
    parameters=StdioServerParameters(command=sys.executable,args=['-m','analytics.mcp_server'],env=os.environ.copy())
    async with stdio_client(parameters) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            listed=await session.list_tools()
            tools=[tool.name for tool in listed.tools]
            assert set(tools)=={'get_analysis_status','list_dashboards','list_datasets','ensure_ai_dashboard','get_chart_data'}
            dashboard=unpack(await session.call_tool('ensure_ai_dashboard',{}))
            assert len(dashboard['charts'])==len(definitions()),'Thiếu biểu đồ trong kết quả MCP'
            repeated=unpack(await session.call_tool('ensure_ai_dashboard',{}))
            assert repeated==dashboard,'Chạy lại MCP phải giữ nguyên id dashboard/dataset/chart'
            datasets=unpack(await session.call_tool('list_datasets',{}))
            assert set(dashboard['datasets'].values()) <= {row['id'] for row in datasets}
            status=unpack(await session.call_tool('get_analysis_status',{}))
            dashboards=unpack(await session.call_tool('list_dashboards',{}))
            assert any(d.get('slug')=='tin-tuc-viet-nam' for d in dashboards),'Dashboard TH1 bị thiếu'
            assert any(d.get('slug')=='tin-tuc-ai-th2' for d in dashboards),'Dashboard TH2 bị thiếu'
            results=[]
            for chart in dashboard['charts']:
                data=unpack(await session.call_tool('get_chart_data',{'chart_id':chart['id']}))
                assert data and all(row.get('status')=='success' for row in data), chart['title']
                results.append({'id':chart['id'],'title':chart['title'],'status':'success',
                                'rows':len(data[0]['data'])})
            denied=await session.call_tool('get_chart_data',{'chart_id':0})
            assert denied.isError,'MCP must reject invalid chart ids'
            report={'generated_at_utc':datetime.now(timezone.utc).isoformat(),
                    'transport':'stdio','initialize':'success','tools':tools,
                    'dashboard':dashboard,'analysis':status,'charts':results,'invalid_chart_rejected':True,
                    'note':'0 dòng cảm xúc khi chưa có Gemini key là đúng; không có kết quả mô phỏng trong DB.'}
            write_json('mcp_checks.json',report)
            from analytics.common import OUTPUT
            from analytics.report import export_report
            status_path=OUTPUT/'pipeline_status.json'
            if status_path.exists():
                export_report(json.loads(status_path.read_text(encoding='utf-8')))
            print(json.dumps(report,ensure_ascii=False,default=str))


if __name__=='__main__':
    try:
        asyncio.run(verify())
    except Exception as exc:
        print('MCP verification failed: '+failure_message(exc),file=sys.stderr)
        raise SystemExit(1) from None
