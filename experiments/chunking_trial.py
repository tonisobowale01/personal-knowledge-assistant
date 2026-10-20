"""Build and evaluate a separate structural-chunk index; never mutate the live index."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--build',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'chunking_trial_answers.json')
    parser.add_argument('--ids',nargs='*')
    parser.add_argument('--db',type=Path,default=ROOT/'chunking_trial_db')
    parser.add_argument('--cases',type=Path,default=ROOT/'tests/answer_cases.json')
    parser.add_argument('--collection',default='test_notes')
    args=parser.parse_args()
    import chromadb,ollama
    from llama_index.core import SimpleDirectoryReader
    from llama_index.readers.file import PDFReader
    from app.chunking import chunk_document
    from app import rag
    from evaluate_answers import main as evaluate
    target=chromadb.PersistentClient(path=str(args.db))
    candidate=target.get_or_create_collection(args.collection) if args.build else target.get_collection(args.collection)
    baseline=rag.collection.get(include=['documents','metadatas'])
    if args.build:
        if candidate.count():raise RuntimeError('Trial index already populated; use existing index instead of overwriting it')
        files={}
        for meta in baseline['metadatas']:
            name=meta['file_name']
            course=meta.get('course')
            if name in files and files[name]!=course:raise RuntimeError('Ambiguous course for '+name)
            files[name]=course
        manifest={'policy':'explicit structure, 512 token budget, 50 overlap; retain untitled leading page context and table headers','chunker_sha256':hashlib.sha256((ROOT/'app/chunking.py').read_bytes()).hexdigest(),'files':[]}
        for name,course in sorted(files.items()):
            path=ROOT/'data/notes'/name
            docs=SimpleDirectoryReader(input_files=[str(path)],file_extractor={'.pdf':PDFReader()}).load_data()
            nodes=[]
            for doc in docs:
                # Keep original page metadata and its tokenizer cost for the comparison.
                original=next((m for m in baseline['metadatas'] if m['file_name']==name and m.get('page_label')==doc.metadata.get('page_label')),None)
                if original:
                    doc.metadata={k:v for k,v in original.items() if k not in {'course','chunk_policy'}}
                nodes.extend(chunk_document(doc))
            texts=[n.text for n in nodes]
            embeddings=[]
            for start in range(0,len(texts),8):
                embeddings.extend(ollama.embed(model='nomic-embed-text',input=texts[start:start+8])['embeddings'])
            metas=[{**n.metadata,'course':course} for n in nodes]
            ids=[f"{name}-page-{n.metadata.get('page_label','unknown')}-chunk-{i}" for i,n in enumerate(nodes)]
            candidate.add(ids=ids,documents=texts,metadatas=metas,embeddings=embeddings)
            manifest['files'].append({'file':name,'course':course,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'chunks':len(nodes),'characters':sum(map(len,texts))})
            print(name,len(nodes),'trial chunks',flush=True)
        manifest['baseline_chunks']=len(baseline['ids'])
        manifest['trial_chunks']=candidate.count()
        args.output.with_name(args.output.stem+'_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    rag.collection=candidate
    # Reuse exactly the same retrieval, prompt, stream, model, cases, and timing code.
    sys.argv=['evaluate_answers.py','--output',str(args.output),'--cases',str(args.cases)]
    if args.ids:sys.argv+=['--ids',*args.ids]
    evaluate()


if __name__=='__main__':main()
