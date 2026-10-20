"""Repeat only long-history live cases after the final history-only patch."""
import hashlib
import json
from pathlib import Path
from time import perf_counter
import httpx

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'.run/v1_acceptance.json'
report=json.loads(path.read_text(encoding='utf-8'))
archive=ROOT/'.run/v1_acceptance_first.json'
if not archive.exists():archive.write_text(json.dumps(report,indent=2),encoding='utf-8')
for row in report['answers']:
    if row['id'] not in ['long_round_robin_followup','long_star_followup']:continue
    started=perf_counter();first=None;parts=[];events=[];final=None
    with httpx.stream('POST','http://127.0.0.1:8000/ask/stream',json=row['request'],timeout=240) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.strip():continue
            event=json.loads(line);events.append(event['type'])
            if event['type']=='error':raise RuntimeError(event['message'])
            if event['type']=='delta':
                if first is None:first=perf_counter()-started
                parts.append(event['text'])
            if event['type']=='done':
                assert final is None
                final=event
    assert final and ''.join(parts)==final['answer']
    row.update(answer=final['answer'],sources=final['sources'],timings=final.get('timings',{}),
        first_text_seconds=first,wall_seconds=perf_counter()-started,delta_count=len(parts),events=events,
        quality_review=None,revision='Final: original current question plus missing topic in conversation context only')
    report['final_code_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['app/rag.py','app/retrieval.py']}
    report['revision_note']='Core flows and short/standalone prompts unchanged. Long-history answers rerun after final history-only patch; first attempt archived in v1_acceptance_first.json.'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(row['id'],round(row['wall_seconds'],1),json.dumps(row['answer']),flush=True)
