"""Đánh giá Gemini với nhãn người kiểm tra, không dùng nhãn mô hình làm ground truth."""
import json
from pathlib import Path
from analytics.common import OUTPUT,connect_db,write_json
from analytics.gemini import SENTIMENTS,TOPICS


def classification_metrics(truth,prediction,classes):
    if not truth or len(truth)!=len(prediction):
        raise ValueError('invalid_evaluation_pairs')
    matrix = {actual:{predicted:0 for predicted in classes} for actual in classes}
    for actual,predicted in zip(truth,prediction):
        if actual not in classes or predicted not in classes:
            raise ValueError('unknown_label')
        matrix[actual][predicted]+=1
    details = {}
    for label in classes:
        tp = matrix[label][label]
        support = sum(matrix[label].values())
        predicted_count = sum(matrix[actual][label] for actual in classes)
        precision = tp/predicted_count if predicted_count else 0
        recall = tp/support if support else 0
        f1 = 2*precision*recall/(precision+recall) if precision+recall else 0
        details[label]={'precision':precision,'recall':recall,'f1':f1,'support':support}
    supported = [row['f1'] for row in details.values() if row['support']>0]
    return {'n':len(truth),'accuracy':sum(a==b for a,b in zip(truth,prediction))/len(truth),
        'macro_f1_supported_classes':sum(supported)/len(supported),
        'per_class':details,'confusion_matrix':matrix,
        'note':'Macro-F1 tính trên các lớp có nhãn thật; lớp chưa có mẫu không chứng minh hiệu quả.'}


def evaluate(labels_path='/app/evaluation/labels.jsonl'):
    OUTPUT.mkdir(parents=True,exist_ok=True)
    with connect_db() as conn,conn.cursor() as cur:
        cur.execute('''SELECT id,title,description,sentiment,topic,model_name
                       FROM v_ai_articles ORDER BY (analysis_status='analyzed') DESC,published_at DESC,id DESC LIMIT 50''')
        rows = cur.fetchall()
        template = [{'article_id':r[0],'title':r[1],'description':r[2],
                     'sentiment':None,'topic':None,'reviewer':'','reviewed':False} for r in rows]
        # Tên template riêng; không ghi đè labels.jsonl mà người học đã gán nhãn.
        (OUTPUT/'labeling_template.jsonl').write_text(
            '\n'.join(json.dumps(row,ensure_ascii=False) for row in template)+'\n',encoding='utf-8')
        labels = []
        path = Path(labels_path)
        if path.exists():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                if line.strip():
                    label = json.loads(line)
                    if label.get('reviewed') is True and str(label.get('reviewer','')).strip():
                        labels.append(label)
        ids = [label['article_id'] for label in labels]
        if len(set(ids))!=len(ids):
            raise ValueError('duplicate_human_labels')
        cur.execute('SELECT id,sentiment,topic,model_name FROM v_ai_analyzed WHERE id=ANY(%s)',(ids,))
        predictions = {row[0]:row for row in cur.fetchall()}
    matched = [label for label in labels if label['article_id'] in predictions]
    result = {'status':'pending_human_labels' if not labels else 'pending_predictions',
              'reviewed_labels':len(labels),'matched_predictions':len(matched),
              'sentiment':None,'topic':None,
              'note':'Chỉ đánh giá trên nhãn được người kiểm tra xác nhận; chưa có nhãn thì không công bố accuracy/F1.'}
    if matched:
        result['status']='evaluated'
        result['sentiment']=classification_metrics([r['sentiment'] for r in matched],
            [predictions[r['article_id']][1] for r in matched],SENTIMENTS)
        result['topic']=classification_metrics([r['topic'] for r in matched],
            [predictions[r['article_id']][2] for r in matched],TOPICS)
        result['models']=sorted({predictions[r['article_id']][3] for r in matched})
        result['note']+=' Nếu tập mẫu nhỏ hoặc nhiều mô hình trộn lẫn, chưa đủ cơ sở kết luận mô hình nào tốt hơn.'
    write_json('gemini_evaluation.json',result)
    return result
