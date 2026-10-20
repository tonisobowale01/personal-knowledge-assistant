"""Paired live-model test of one general answer instruction; no production writes."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
INSTRUCTION = '''Answer all parts of the question using only the context. Explain the relevant meaning, mechanism, or reason; do not just expand a name. Keep each fact attached to the subject it describes; do not borrow properties from other subjects or add unstated comparisons. If a part is unsupported, say "I could not find that in the notes." for that part. Be concise.

'''


def candidate_prompt(prompt):
    if prompt is None:
        return None
    before, marker, after = prompt.partition('    Context:\n')
    if not marker or 'Answer the question using only the context below.' not in before:
        raise RuntimeError('Baseline prompt changed; review experiment before continuing')
    return INSTRUCTION + marker + after


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=ROOT/'answer_prompt_trial.json')
    p.add_argument('--ids', nargs='+')
    p.add_argument('--repeats', type=int, default=1)
    args = p.parse_args()
    from app import rag
    import ollama
    frozen = json.loads((ROOT/'top_k_comparison.json').read_text(encoding='utf-8'))
    cases = frozen['cases']
    if args.ids:
        if set(args.ids) - {c['id'] for c in cases}: p.error('Unknown case IDs')
        cases = [c for c in cases if c['id'] in args.ids]
    corpus = rag.collection.get(include=['documents', 'metadatas'])
    corpus_rows = sorted(zip(corpus['ids'], corpus['documents'], corpus['metadatas']))
    digest = lambda value: hashlib.sha256(value).hexdigest()
    fingerprint = dict(corpus_sha256=digest(json.dumps(corpus_rows, sort_keys=True).encode()),
        code_sha256={name:digest((ROOT/name).read_bytes()) for name in ['app/rag.py','app/retrieval.py']},
        instruction=INSTRUCTION, cases_sha256=digest(json.dumps(cases,sort_keys=True).encode()),
        model=dict(name=rag.llm.model, context_window=rag.llm.context_window,
                   temperature=rag.llm.temperature, system_prompt=rag.llm.system_prompt),
        runtime=json.load(urlopen('http://127.0.0.1:11434/api/version')),
        models=ollama.Client().list().model_dump(mode='json'), repeats=args.repeats)
    report = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else dict(
        fingerprint=fingerprint, cases=cases, reference_corpus=corpus_rows, rows=[],
        protocol='Paired baseline/candidate with alternating order per case/repeat. Only answer instructions differ. '
        'Same live retrieval (five passages), corpus, history, model defaults and streaming code. '
        'Before every measured answer unload generation model and warm with unrelated OK prompt; '
        'loading/warmup excluded. No fixed seed. Manual review against notes required. '
        'No saved chat or production source writes.')
    if report['fingerprint'] != fingerprint: raise RuntimeError('Inputs changed; choose new output')
    trace = []
    original = rag.prepare_evidence
    mode = 'baseline'
    def prepare(*a, **kw):
        result = list(original(*a, **kw))
        if mode == 'candidate': result[0] = candidate_prompt(result[0])
        trace.append(dict(prompt=result[0], passages=result[3]))
        return tuple(result)
    rag.prepare_evidence = prepare
    done = {(r['case']['id'],r['mode'],r['repeat']) for r in report['rows']}
    for repeat in range(args.repeats):
        for index, case in enumerate(cases):
            modes = ['baseline','candidate'] if (index+repeat)%2 == 0 else ['candidate','baseline']
            for mode in modes:
                if (case['id'],mode,repeat+1) in done: continue
                ollama.generate(model=rag.llm.model, prompt='', keep_alive=0)
                rag.llm.complete('Reply with OK.')
                trace.clear()
                started = perf_counter(); first = None; parts = []; final = None
                row = dict(case=case, mode=mode, repeat=repeat+1, quality_review=None)
                try:
                    for event in rag.stream_question(case['question'],course=case['course'],
                            history=[SimpleNamespace(**m) for m in case['history']]):
                        if event['type'] == 'delta':
                            if first is None: first = perf_counter()-started
                            parts.append(event['text'])
                        if event['type'] == 'done': final = event
                    if final is None: raise RuntimeError('No completed answer')
                    row.update(status='completed',answer=final['answer'],timings=final.get('timings',{}))
                except Exception as exc:
                    row.update(status='error',answer=''.join(parts),error=str(exc))
                row.update(wall_seconds=perf_counter()-started,first_text_seconds=first,context_trace=list(trace))
                report['rows'].append(row)
                args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
                print(case['id'], mode, repeat+1, row['status'], round(row['wall_seconds'],1),flush=True)


if __name__ == '__main__': main()
