"""Promote the reviewed index only after backing up and verifying the baseline."""
import hashlib,json,sys
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import chromadb


def fingerprint(data):
    rows=sorted(zip(data['ids'],data['documents'],data['metadatas']),key=lambda row:row[0])
    return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()


def main():
    client=chromadb.PersistentClient(path=str(ROOT/'chroma_db'))
    active=client.get_collection('test_notes')
    baseline=json.loads((ROOT/'baseline_full.json').read_text(encoding='utf-8'))
    before=active.get(include=['documents','metadatas','embeddings'])
    if fingerprint(before)!=baseline['corpus_sha256']:
        raise RuntimeError('Live corpus changed since the baseline; promotion stopped')
    manifest=json.loads((ROOT/'chunking_trial_v2_manifest.json').read_text(encoding='utf-8'))
    if hashlib.sha256((ROOT/'app/chunking.py').read_bytes()).hexdigest()!=manifest['chunker_sha256']:
        raise RuntimeError('Chunking policy changed since the trial')
    for item in manifest['files']:
        if hashlib.sha256((ROOT/'data/notes'/item['file']).read_bytes()).hexdigest()!=item['sha256']:
            raise RuntimeError('Source document changed: '+item['file'])
    for name,expected in baseline['code_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Retrieval or answer code changed: '+name)
    trial=chromadb.PersistentClient(path=str(ROOT/'chunking_trial_db_v2')).get_collection('test_notes')
    candidate=trial.get(include=['documents','metadatas','embeddings'])
    report=json.loads((ROOT/'chunking_trial_v2.json').read_text(encoding='utf-8'))
    if fingerprint(candidate)!=report['corpus_sha256']:
        raise RuntimeError('Trial index changed since evaluation')
    backup_name='test_notes_baseline_20261014'
    backup=client.get_or_create_collection(backup_name)
    if not backup.count():
        backup.add(ids=before['ids'],documents=before['documents'],metadatas=before['metadatas'],embeddings=before['embeddings'].tolist())
    if fingerprint(backup.get(include=['documents','metadatas']))!=baseline['corpus_sha256']:
        raise RuntimeError('Backup does not match the frozen baseline')
    metadata=[{**m,'chunk_policy':'structure_v2'} for m in candidate['metadatas']]
    active.upsert(ids=candidate['ids'],documents=candidate['documents'],metadatas=metadata,embeddings=candidate['embeddings'].tolist())
    obsolete=sorted(set(before['ids'])-set(candidate['ids']))
    if obsolete:active.delete(ids=obsolete)
    after=active.get(include=['documents','metadatas','embeddings'])
    by_id={id:(text,meta,vector.tolist()) for id,text,meta,vector in zip(after['ids'],after['documents'],after['metadatas'],after['embeddings'])}
    assert len(by_id)==len(candidate['ids'])
    for id,text,meta,vector in zip(candidate['ids'],candidate['documents'],candidate['metadatas'],candidate['embeddings']):
        assert by_id[id]==(text,{**meta,'chunk_policy':'structure_v2'},vector.tolist())
    rollout={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'backup_collection':backup_name,'baseline_sha256':baseline['corpus_sha256'],'trial_sha256':report['corpus_sha256'],'live_sha256':fingerprint(after),'old_chunks':len(before['ids']),'new_chunks':len(after['ids']),'old_obsolete_ids_removed':len(obsolete),'source_files_unchanged':True,'retrieval_and_prompt_unchanged':True,'trial_text_metadata_and_vectors_verified':True}
    (ROOT/'chunking_rollout.json').write_text(json.dumps(rollout,indent=2),encoding='utf-8')
    print('Backed up',len(before['ids']),'chunks; promoted',len(after['ids']),'verified chunks.')


if __name__=='__main__':main()
