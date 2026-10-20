"""Publish the assistant's manual review of the frozen 22-case comparison."""
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]
# These judgments refer to the recorded answers, not keyword-based scoring.
FLAGS = {
    5: {
        'q05': ('pass', 'fail', 'Mixes tree root/branch structure into star and adds unsupported complexity comparison.'),
        'q10': ('partial', 'pass', 'High availability stated; monitored-node takeover/restart omitted.'),
        'q12': ('partial', 'fail', 'Covers three topics but omits explicit takeover/restart and adds general efficiency over single-processor systems.'),
        'q14': ('partial', 'pass', 'Names FCFS and non-preemption, but omits arrival/FIFO order.'),
        'q15': ('pass', 'fail', 'Correct indefinite-waiting statement followed by unsupported relative-waiting-time explanation.'),
        'sjf_all': ('partial', 'pass', 'Expands acronym but does not explain shortest-burst selection/non-preemption.')},
    3: {
        'q03': ('fail', 'fail', 'Describes hierarchical tree as star topology.'),
        'q05': ('partial', 'fail', 'Bus device-failure and scalability claims unsupported; omits shared-cable failure.'),
        'q08': ('partial', 'pass', 'Omits hardware management.'),
        'q10': ('partial', 'pass', 'Omits node monitoring and takeover/restart.'),
        'q12': ('partial', 'pass', 'Omits multicore and gives contradictory refusals before partial definitions.'),
        'q13': ('partial', 'pass', 'Gives active/standby distinction but omits standby monitoring; claims comparison is not explicit.'),
        'q15': ('partial', 'pass', 'Names starvation but does not explain indefinite waiting for long jobs.'),
        'sjf_all': ('partial', 'pass', 'Only expands the acronym.')},
    1: {
        'q01': ('fail', 'pass', 'False refusal: bus definition is outside the first retrieved chunk.'),
        'q05': ('fail', 'pass', 'Refuses comparison; only tree passage supplied.'),
        'q10': ('partial', 'pass', 'Omits node monitoring and takeover/restart.'),
        'q12': ('fail', 'pass', 'Refuses three-topic question; only virtualization passage supplied.'),
        'q13': ('partial', 'fail', 'Does not describe asymmetric roles; symmetric description is not supported by the single supplied passage.'),
        'q15': ('partial', 'pass', 'Names starvation without explaining indefinite waiting.'),
        'q17': ('fail', 'pass', 'Repeats traffic routing instead of explaining central-device failure.'),
        'sjf_all': ('partial', 'pass', 'Only expands the acronym.')},
}


def main():
    path = ROOT / 'top_k_comparison.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    assert len(report['rows']) == 66
    assert all(r['status'] == 'completed' for r in report['rows'])
    report['review_method'] = ('Assistant manual review against expected points and frozen source corpus, '
        'also checking whether claims are supported by each supplied context. Not independent human review. '
        'Pass requires completeness and supported claims. Naming starvation alone is partial; '
        'standby takeover implicitly demonstrates failure monitoring. SJF advantage matches the notes\' '
        'non-preemptive optimum statement; no unsupported fairness claims in these runs.')
    lines = ['# Retrieval chunk-count comparison', '',
        'Recommendation: retain five chunks. Neither smaller setting preserves answer quality across these cases.', '',
        '22 questions, 66 completed live-model answers. Same 52-chunk index, model, prompt and history resolver. '
        'No production settings, saved chats or source documents changed.', '',
        report['review_method'], '',
        '| Chunks | Complete and supported | Median first text | Median completion |',
        '|---|---:|---:|---:|']
    summary = {}
    for k in [5, 3, 1]:
        rows = [r for r in report['rows'] if r['k'] == k]
        for row in rows:
            complete, supported, notes = FLAGS[k].get(row['case']['id'],
                ('pass', 'pass', 'Meets expected points without unsupported substantive claims.'))
            row['quality_review'] = dict(completeness=complete, supported_claims=supported,
                                         acceptable=complete == supported == 'pass', notes=notes)
        answerable = [r for r in rows if r['case']['id'] not in ['q18', 'q19', 'q20']]
        summary[k] = dict(acceptable=sum(r['quality_review']['acceptable'] for r in rows), total=len(rows),
            flagged_ids=[r['case']['id'] for r in rows if not r['quality_review']['acceptable']],
            median_first_text_seconds=median(r['first_text_seconds'] for r in answerable),
            median_completion_seconds=median(r['wall_seconds'] for r in answerable))
        s = summary[k]
        lines.append(f"| {k} | {s['acceptable']}/22 | {s['median_first_text_seconds']:.1f}s | {s['median_completion_seconds']:.1f}s |")
    report['review_summary'] = summary
    lines += ['', 'Timing medians exclude the three refusal/empty-course cases. These are observations, '
        'not isolated chunk-count speedups: nested contexts reuse Ollama prefix caches. Rotated order '
        'does not eliminate this effect. No fixed seed, one answer per case/setting, small development set. '
        'Fresh-cache checks are stored separately in top_k_fresh_cache.json.', '',
        'Evidence: bus definition ranks third; multicore evidence ranks fourth for the combined question. '
        'Standalone SJF retrieves the full definition first at every setting but answers only the acronym. '
        'This distinguishes missing retrieved evidence from failure to use available evidence.', '',
        'The Oct 14 historical baseline is not a same-runtime control: this comparison reruns five chunks '
        'on the current corpus/runtime. No historical ratings or timings were substituted.', '']
    fresh_path = ROOT / 'top_k_fresh_cache.json'
    if fresh_path.exists():
        fresh = json.loads(fresh_path.read_text(encoding='utf-8'))
        assert len(fresh['rows']) == 9
        fresh['review_method'] = report['review_method']
        fresh_notes = {
            ('q01', 5): ('pass', 'Bus definition correct; quotes an incorrect page-number fragment (8).'),
            ('q01', 3): ('pass', 'Correct bus definition.'),
            ('q01', 1): ('fail', 'False refusal; relevant passage excluded.'),
            ('q12', 5): ('flag', 'Covers all topics, but adds efficient processing beyond the communication benefit stated in notes.'),
            ('q12', 3): ('fail', 'Multicore evidence absent; does not explain multicore.'),
            ('q12', 1): ('fail', 'False refusal on three-topic question.'),
            ('sjf_followup', 5): ('fail', 'Incorrectly borrows fairness/no-starvation from FCFS or RR.'),
            ('sjf_followup', 3): ('pass', 'Correct minimum-average-waiting advantage.'),
            ('sjf_followup', 1): ('flag', 'Correct advantage followed by dangling bullet and unfinished commentary.')}
        lines += ['## Fresh-cache checks', '',
            'Nine additional answers, three representative questions. Generation model unloaded and warmed '
            'with an unrelated prompt before every measurement; loading/warm-up excluded. These checks '
            'do not reuse a preceding measured-question prefix. No fixed seed; not statistical proof.', '',
            '| Question | Chunks | First text | Completion | Review |', '|---|---:|---:|---:|---|']
        for row in fresh['rows']:
            rating, notes = fresh_notes[(row['case']['id'], row['k'])]
            row['quality_review'] = dict(rating=rating, notes=notes)
            lines.append(f"| {row['case']['id']} | {row['k']} | {row['first_text_seconds']:.1f}s | {row['wall_seconds']:.1f}s | {notes} |")
        fresh_path.write_text(json.dumps(fresh, indent=2), encoding='utf-8')
        lines += ['', 'Important: SJF follow-up was correct for all settings in the main pass but '
            'the five-chunk repeat invented no-starvation/fairness. The main-pass 16/22 is a descriptive '
            'manual result, not a guarantee of future answers. Smaller contexts can omit evidence; '
            'larger contexts can mix facts from adjacent subjects. Next experiment: a single general '
            'answer-instruction change, tested against the unchanged five-chunk baseline. No topic-specific safeguards.', '']
    for case in report['cases']:
        lines += [f"## {case['id']}: {case['question']}", '', 'Expected: ' + '; '.join(case['expected_points']), '']
        for row in sorted([r for r in report['rows'] if r['case']['id'] == case['id']], key=lambda r:-r['k']):
            q = row['quality_review']
            lines += [f"### {row['k']} chunks", '', row['answer'], '',
                f"Complete: {q['completeness']}; supported: {q['supported_claims']}. {q['notes']}", '',
                f"First text {row['first_text_seconds']:.1f}s; completed {row['wall_seconds']:.1f}s.", '']
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    (ROOT / 'TOP_K_COMPARISON.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main()
