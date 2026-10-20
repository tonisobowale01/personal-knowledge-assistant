"""Read-only, interleaved comparison of the application's top-k retrieval settings."""
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'top_k_comparison.json')
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--fresh-cache', action='store_true')
    args = parser.parse_args()
    from app import rag
    import ollama

    cases = json.loads((ROOT / 'tests/answer_cases.json').read_text(encoding='utf-8'))
    sjf = json.loads((ROOT / 'tests/baseline_cases.json').read_text(encoding='utf-8'))[0]
    cases.append(sjf)
    cases.append(dict(sjf, id='sjf_followup', question='What are its advantages?',
        history=[dict(role='user', content='What is SJF?'), dict(role='assistant',
        content='SJF stands for Shortest Job First. It selects the process with the shortest estimated CPU burst.')],
        expected_points=['SJF minimizes average waiting time when CPU burst times are known.'],
        unsupported_claims_to_check=['SJF can starve long jobs; do not claim fairness or no starvation.']))
    if args.ids:
        unknown = set(args.ids) - {c['id'] for c in cases}
        if unknown: parser.error(f'Unknown cases: {unknown}')
        cases = [c for c in cases if c['id'] in args.ids]
    base = rag.collection
    corpus = base.get(include=['documents', 'metadatas'])
    corpus_rows = sorted(zip(corpus['ids'], corpus['documents'], corpus['metadatas']))
    fingerprint = dict(
        corpus_sha256=hashlib.sha256(json.dumps(corpus_rows, sort_keys=True).encode()).hexdigest(),
        code_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                     for p in ['app/rag.py', 'app/retrieval.py']},
        cases_sha256=hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest(),
        model=dict(name=rag.llm.model, context_window=rag.llm.context_window,
                   temperature=rag.llm.temperature, system_prompt=rag.llm.system_prompt),
        ollama_version=json.load(urlopen('http://127.0.0.1:11434/api/version')),
        model_inventory=ollama.Client().list().model_dump(mode='json'))
    if args.fresh_cache:
        fingerprint['fresh_cache'] = True
    report = json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else dict(
        fingerprint=fingerprint, rows=[], cases=cases, reference_corpus=corpus_rows,
        protocol=('Before each measured call unload the generation model, then warm it with an unrelated OK prompt. '
        'Warm-up and loading excluded; no reuse of earlier measured-question prefixes. ' if args.fresh_cache else '') +
        'Sequential calls; orders rotate 5/3/1, 3/1/5, 1/5/3 across cases. '
        'Only query n_results varies. Same live corpus, prompt, model defaults, history resolver. '
        'No fixed seed; single-run timings are subject to runtime variation. '
        'Without --fresh-cache, timings also include prefix-cache and warm/cold effects. '
        'Manual answer review required. No saved-chat writes or production changes.')
    if report['fingerprint'] != fingerprint:
        raise RuntimeError('Inputs changed; use a new output file')

    class TopK:
        def __init__(self, k): self.k = k
        def query(self, **kwargs):
            kwargs['n_results'] = self.k
            return base.query(**kwargs)

    trace = []
    original = rag.prepare_evidence
    def record(*a, **kw):
        result = original(*a, **kw)
        trace.append(dict(prompt_characters=len(result[0] or ''), passages=result[3]))
        return result
    rag.prepare_evidence = record
    done = {(r['case']['id'], r['k']) for r in report['rows']}
    orders = [[5, 3, 1], [3, 1, 5], [1, 5, 3]]
    for index, case in enumerate(cases):
        for k in orders[index % 3]:
            if (case['id'], k) in done: continue
            rag.collection = TopK(k)
            if args.fresh_cache:
                ollama.generate(model=rag.llm.model, prompt='', keep_alive=0)
                rag.llm.complete('Reply with OK.')
            trace.clear()
            started = perf_counter()
            first = None
            parts = []
            row = dict(case=case, k=k, quality_review=None)
            try:
                final = None
                for event in rag.stream_question(case['question'], course=case['course'],
                        history=[SimpleNamespace(**m) for m in case['history']]):
                    if event['type'] == 'delta':
                        if first is None: first = perf_counter() - started
                        parts.append(event['text'])
                    if event['type'] == 'done': final = event
                if final is None: raise RuntimeError('No completed answer')
                row.update(status='completed', answer=final['answer'], timings=final.get('timings', {}))
            except Exception as exc:
                row.update(status='error', answer=''.join(parts), error=str(exc))
            row.update(first_text_seconds=first, wall_seconds=perf_counter()-started,
                       context_trace=list(trace))
            report['rows'].append(row)
            args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(case['id'], 'k='+str(k), row['status'], round(row['wall_seconds'], 1), flush=True)


if __name__ == '__main__': main()
