"""Publish manual judgments for the frozen first general-prompt experiment."""
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
FLAGS = {
    'baseline': {
        'q05': ('pass', 'fail', 'Covers expected structure/failure points, but adds an unstated directional-transmission comparison.'),
        'q10': ('partial', 'pass', 'States high availability but omits monitoring and takeover/restart mechanism.'),
        'q12': ('pass', 'fail', 'All three definitions present; adds unsupported general efficiency over traditional multiprocessors.')},
    'candidate': {
        'q05': ('partial', 'fail', 'Invents connection-oriented topology claim and omits single-device failure isolation in star.'),
        'q08': ('partial', 'pass', 'Covers hardware/user mediation and resource management but omits application-program support.')},
}


def main():
    path = ROOT/'answer_prompt_trial.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    assert len(report['rows']) == 44
    assert len({(r['case']['id'],r['mode']) for r in report['rows']}) == 44
    assert all(r['status']=='completed' for r in report['rows'])
    pairs = {c['id']:{r['mode']:r for r in report['rows'] if r['case']['id']==c['id']}
             for c in report['cases']}
    for pair in pairs.values():
        a,b = [pair[mode]['context_trace'][0] for mode in ['baseline','candidate']]
        assert a['passages'] == b['passages']
        if a['prompt'] is None:
            assert b['prompt'] is None
        else:
            # Evidence, question and conversation must remain byte-identical.
            assert a['prompt'].partition('    Context:\n')[2] == b['prompt'].partition('    Context:\n')[2]
    report['review_method'] = ('Assistant manual review of all 44 recorded answers against expected points, '
        'frozen reference notes and the exact supplied passages. Not independent human ratings. '
        'Acceptable requires complete core answer and no unsupported substantive claims. '
        'Equivalent wording counts: baseline q08 describes resources (process/memory/file management), '
        'services to users and the position between hardware and applications, covering the core roles. '
        'Candidate q08 does not mention application support. Baseline q15 correctly explains indefinite '
        'waiting but mislabels the location of its quotation as the comparison table; this locator defect '
        'is noted separately from substantive correctness. SJF need not explain SRTF if ordinary '
        'non-preemptive shortest-burst selection is correctly explained.')
    summary = {}
    for mode in ['baseline','candidate']:
        rows = [r for r in report['rows'] if r['mode']==mode]
        for row in rows:
            complete,supported,notes = FLAGS[mode].get(row['case']['id'],
                ('pass','pass','Meets the expected core points without unsupported substantive claims.'))
            if mode=='baseline' and row['case']['id']=='q08':
                notes = 'Resource-management examples, services to users and software between hardware/applications cover the core roles.'
            if mode=='baseline' and row['case']['id']=='q15':
                notes = 'Correct indefinite-waiting explanation; quotation appears in SJF section, not the comparison table as claimed.'
            row['quality_review'] = dict(completeness=complete,supported_claims=supported,
                acceptable=complete==supported=='pass',notes=notes)
        answerable = [r for r in rows if r['case']['id'] not in ['q18','q19','q20']]
        summary[mode] = dict(acceptable=sum(r['quality_review']['acceptable'] for r in rows),total=len(rows),
            flagged_ids=[r['case']['id'] for r in rows if not r['quality_review']['acceptable']],
            median_first_text_seconds=median(r['first_text_seconds'] for r in answerable),
            median_completion_seconds=median(r['wall_seconds'] for r in answerable))
    report['review_summary'] = summary
    report['decision'] = ('Do not promote. Descriptive 19/22 to 20/22 gain includes two wins (q10,q12) '
        'and one regression (q08), with a persistent invented claim on q05. Median answerable-case '
        'completion increases from 25.3s to 27.8s and first text from 19.3s to 21.3s. '
        'One stochastic run per pair does not establish a reliable accuracy gain. '
        'This candidate has not met the project requirement to improve actual answers while preserving speed. '
        'Leave production prompt and five-chunk retrieval unchanged.')
    lines = ['# General answer-prompt experiment', '', '**Decision: keep the current application prompt.**', '',
        report['decision'], '', '## Method', '', report['protocol'], '',
        '22 questions, 44 completed live answers. Every pair received identical evidence, question and '
        'history; assertions verify that only the instruction prefix differs. Same 52-chunk corpus, '
        'five-chunk retrieval, llama3.2:3b defaults and 8192 context window. No saved-chat writes.', '',
        'Candidate instruction:', '', '> '+report['fingerprint']['instruction'].strip(), '',
        '## Results', '', '| Prompt | Complete and supported | Median first text | Median completion |',
        '|---|---:|---:|---:|']
    for mode,s in summary.items():
        lines.append(f"| {mode} | {s['acceptable']}/22 | {s['median_first_text_seconds']:.1f}s | {s['median_completion_seconds']:.1f}s |")
    lines += ['', 'Timing medians exclude three refusal/empty-course cases; the quality counts include all '
        '22 questions. Model loading and neutral warm-up are excluded from measured latency. '
        'These are controlled-prefix-cache observations, not guarantees of interactive speed. '
        'One answer per case and mode, no fixed seed, small development set. '
        'No independent human review or confidence interval. Historical run scores are not substituted '
        'for this same-runtime control.', '', report['review_method'], '',
        'The gain is better explanation/grounding in q10 and q12; the regression is omitted application '
        'support in q08. Both modes correctly handled the two existing history follow-ups, the added '
        'SJF follow-up and all refusal cases. Both gave a full standalone SJF definition this time, '
        'unlike the earlier chunk-count experiment: sampling variability remains material.', '',
        'Only experiment scripts and reports were added. Application source, live index, '
        'chat history, streaming and timing behavior were not changed.', '']
    for case in report['cases']:
        lines += [f"## {case['id']}: {case['question']}", '',
            'Expected: '+'; '.join(case['expected_points']), '']
        for mode in ['baseline','candidate']:
            row=pairs[case['id']][mode]; q=row['quality_review']
            lines += [f'### {mode}', '', row['answer'], '',
                f"Completeness: {q['completeness']}; support: {q['supported_claims']}. {q['notes']}", '',
                f"First text: {row['first_text_seconds']:.1f}s; completion: {row['wall_seconds']:.1f}s.", '']
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    (ROOT/'ANSWER_PROMPT_TRIAL.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
