"""Archived experiment; not the active baseline. Controlled local context-size experiment. Does not change app configuration or notes."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from types import SimpleNamespace
import chromadb
import ollama
from experiments.previous_retrieval import retrieve, history_text

ROOT = Path(__file__).resolve().parent
MODEL = 'llama3.2:3b'

def answer_prompt(question, history, passages):
    context = '\n\n'.join(f"[Source: {p['metadata'].get('file_name', 'unknown')}, page {p['metadata'].get('page_label', 'unknown')}]\n{p['text']}" for p in passages)
    return f'''Answer the current question using the retrieved notes as the factual source of truth.
Use the recent conversation only to understand context and references.
Do not rely on the conversation history for factual claims if the retrieved notes do not support them.
If the answer is not supported by the retrieved notes, say:
"I could not find that in the notes."
Recent conversation:
{history_text(history)}
Retrieved notes:
{context}
Current question:
{question}'''

def run_prompt(client, prompt, context_size, output_limit):
    started=perf_counter(); first=None; parts=[]; final=None
    for chunk in client.chat(model=MODEL, messages=[{'role':'user','content':prompt}], stream=True,
                             options={'num_ctx':context_size,'temperature':0,'seed':42,'num_predict':output_limit}, keep_alive='5m'):
        content=chunk['message'].get('content','')
        if content:
            if first is None: first=perf_counter()-started
            parts.append(content)
        if chunk.get('done'): final=chunk
    if final is None: raise RuntimeError('Ollama stream did not complete')
    if not parts: raise RuntimeError('Ollama returned no answer text')
    result={'wall_seconds':perf_counter()-started,'first_text_seconds':first,'answer':''.join(parts),
            'prompt_tokens':final.get('prompt_eval_count'),'output_tokens':final.get('eval_count'),
            'done_reason':final.get('done_reason')}
    for field in ['load_duration','prompt_eval_duration','eval_duration']:
        result[field.replace('_duration','_seconds')]=(final.get(field) or 0)/1e9
    result['output_tokens_per_second']=(result['output_tokens'] or 0)/result['eval_seconds'] if result['eval_seconds'] else None
    result['budget_ok']=result['prompt_tokens'] is not None and result['prompt_tokens']+output_limit <= context_size
    result['output_hit_limit']=result['done_reason']=='length' or (result['output_tokens'] or 0)>=output_limit
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,default=ROOT/'chroma_db')
    parser.add_argument('--output',type=Path,default=ROOT/'context_report.json')
    parser.add_argument('--contexts',type=int,nargs='+',default=[131072,8192])
    parser.add_argument('--repeats',type=int,default=2)
    parser.add_argument('--output-limit',type=int,default=256)
    args=parser.parse_args()
    if args.repeats<1 or args.output_limit<1 or any(ctx<=args.output_limit for ctx in args.contexts):
        parser.error('Positive repeats and output limit required; contexts must exceed output limit')
    client=ollama.Client(timeout=180)
    collection=chromadb.PersistentClient(path=str(args.db)).get_collection('test_notes')
    if (collection.configuration.get('hnsw') or {}).get('space')!='l2':
        raise RuntimeError('This project retrieval cutoff requires the existing L2 collection')
    cases=[
        {'question':'What is FCFS?', 'course':'Operating Systems','history':[], 'review_points':['Processes execute in arrival order','Non-preemptive']},
        {'question':'Compare bus and star topologies.', 'course':'Networking','history':[], 'review_points':['Bus uses a shared main cable','Star uses a central hub or switch','Failure behavior is explained correctly']},
        {'question':'What happens if its time quantum is too large?', 'course':'Operating Systems',
         'history':[{'role':'user','content':'Explain Round Robin scheduling.'},{'role':'assistant','content':'Round Robin gives each process a time quantum.'}],
         'review_points':['Resolves its to Round Robin','A very large quantum behaves like FCFS']},
    ]
    prepared=[]
    print('Retrieving once and freezing the same prompts for both context sizes.',flush=True)
    for case in cases:
        history=[SimpleNamespace(**m) for m in case['history']]
        result=retrieve(case['question'],case['course'],history,collection,
            lambda q:client.embed(model='nomic-embed-text',input=q)['embeddings'][0],
            lambda p:SimpleNamespace(text=client.chat(model=MODEL,messages=[{'role':'user','content':p}],options={'num_ctx':8192,'temperature':0,'seed':42})['message']['content']))
        if not result['passages']: raise RuntimeError(f"No evidence for {case['question']}")
        prompt=answer_prompt(case['question'],history,result['passages'])
        prepared.append({**case,'prompt':prompt,'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
                         'retrieval_seconds':result['seconds'], 'queries':result['queries'],
                         'sources':[p['metadata'] for p in result['passages']]})
    report={'model':MODEL,'options':{'temperature':0,'seed':42,'output_limit':args.output_limit},'prepared':prepared,'runs':[],
            'limitations':'Small controlled generation test, not an end-to-end benchmark. Retrieval and rewriting are frozen outside the timed answer stage. Prompts follow app instructions but whitespace differs. Memory is model allocation from Ollama, not whole-program RAM. Warm-up and repeated-prompt caching can affect results. Answer quality requires reviewing the recorded answers and review points. Test does not cover prompts near the 8192-token limit.'}
    def save(): args.output.write_text(json.dumps(report,indent=2))
    save()
    for size in args.contexts:
        print(f'Loading/warming context {size} (excluded from measured questions).',flush=True)
        warm=run_prompt(client,'Reply with OK.',size,8)
        ps=client.ps()['models']; loaded=next((m for m in ps if m['name'].startswith(MODEL)),None)
        allocation={k:loaded.get(k) for k in ['size','size_vram','context_length']} if loaded else None
        if allocation is None or allocation['context_length'] != size:
            raise RuntimeError(f'Could not verify requested context {size}: {allocation}')
        block={'requested_context':size,'allocation':allocation,'warmup':warm,'answers':[]}
        report['runs'].append(block);save()
        for repeat in range(args.repeats):
            for case in prepared:
                result=run_prompt(client,case['prompt'],size,args.output_limit)
                block['answers'].append({'question':case['question'],'repeat':repeat+1,'prompt_sha256':case['prompt_sha256'],**result})
                save()
                print(f"context={size} repeat={repeat+1} {case['question']}: {result['wall_seconds']:.2f}s, first text {result['first_text_seconds']:.2f}s, prompt {result['prompt_tokens']} tokens",flush=True)
    report['summary']=[{'context':b['requested_context'],'allocation':b['allocation'],
        'median_wall_seconds':median(a['wall_seconds'] for a in b['answers']),
        'median_first_text_seconds':median(a['first_text_seconds'] for a in b['answers']),
        'all_budgets_ok':all(a['budget_ok'] for a in b['answers']),
        'any_output_hit_limit':any(a['output_hit_limit'] for a in b['answers'])} for b in report['runs']]
    counts={}
    for block in report['runs']:
        for answer in block['answers']: counts.setdefault(answer['prompt_sha256'],set()).add(answer['prompt_tokens'])
    report['matching_prompt_counts_across_runs']=all(len(values)==1 for values in counts.values())
    save();print(json.dumps(report['summary'],indent=2),flush=True)

if __name__=='__main__': main()
