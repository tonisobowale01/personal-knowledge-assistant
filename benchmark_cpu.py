"""CPU decode experiment: fixed short prompt, 8192 context, 64 output-token cap."""
import json
from pathlib import Path
from statistics import median
from time import perf_counter
import ollama
ROOT=Path(__file__).resolve().parent
client=ollama.Client(timeout=180)
prompt='Explain CPU scheduling in detail. Compare FCFS, SJF, and Round Robin, including advantages, disadvantages, fairness, and examples. Write several paragraphs.'
report={'cpu':'Intel Core i7-10510U, 4 cores / 8 logical processors','context':8192,'runs':[],
 'limitations':'Short synthetic prompt, warm repeated-prompt cache; measures decode throughput, not retrieval or long-prompt performance. Two repetitions per setting, no reversed-order run. Output capped at 64 tokens intentionally; not an answer-quality test. Thread settings are requested through Ollama; actual worker count is not independently observed.'}
def save(): (ROOT/'cpu_report.json').write_text(json.dumps(report,indent=2))
for threads in [0,4,8]:
 options={'num_ctx':8192,'temperature':0,'seed':42,'num_predict':1}
 if threads: options['num_thread']=threads
 print(f'Warming thread setting {threads or "automatic"}',flush=True)
 client.chat(model='llama3.2:3b',messages=[{'role':'user','content':prompt}],options=options,keep_alive='5m')
 for repeat in [1,2]:
  options['num_predict']=64
  started=perf_counter();r=client.chat(model='llama3.2:3b',messages=[{'role':'user','content':prompt}],options=options,keep_alive='5m')
  seconds=r['eval_duration']/1e9
  row={'threads':threads,'repeat':repeat,'wall_seconds':perf_counter()-started,'prompt_tokens':r['prompt_eval_count'],
       'prompt_eval_seconds':r['prompt_eval_duration']/1e9,'output_tokens':r['eval_count'],'eval_seconds':seconds,
       'tokens_per_second':r['eval_count']/seconds,'done_reason':r.get('done_reason')}
  report['runs'].append(row);save();print(json.dumps(row),flush=True)
report['summary']=[{'threads':threads,'median_tokens_per_second':median(r['tokens_per_second'] for r in report['runs'] if r['threads']==threads)} for threads in [0,4,8]]
save();print(json.dumps(report['summary']),flush=True)
