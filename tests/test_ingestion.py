import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import llama_index.core as llama_core
import llama_index.readers.file


class Ingestion(unittest.TestCase):
    def load(self):
        c=Mock(); c.get.return_value={'ids':['notes.pdf-page-1-chunk-0','notes.pdf-page-2-chunk-1']}
        embed=Mock(return_value={'embeddings':[[1.0,2.0]]})
        chroma=SimpleNamespace(PersistentClient=Mock(return_value=SimpleNamespace(get_or_create_collection=Mock(return_value=c))))
        reader=Mock(return_value=SimpleNamespace(load_data=Mock(return_value=[Mock()])))
        with patch.dict(sys.modules,{'chromadb':chroma,'ollama':SimpleNamespace(embed=embed)}), patch.object(llama_core,'SimpleDirectoryReader',reader):
            spec=importlib.util.spec_from_file_location('tested_ingestion',Path(__file__).resolve().parents[1]/'ingest_notes.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        module.chunk_document=Mock(return_value=[SimpleNamespace(text='Complete definition.',metadata={'page_label':'1','file_name':'notes.pdf'})])
        return module,c,embed

    def test_reingestion_removes_only_obsolete_ids_after_upsert(self):
        m,c,embed=self.load()
        self.assertEqual(m.ingest_file('notes.pdf','Course'),1)
        c.get.assert_called_once_with(where={'file_name':'notes.pdf'},include=[])
        c.delete.assert_called_once_with(ids=['notes.pdf-page-2-chunk-1'])
        meta=c.upsert.call_args.kwargs['metadatas'][0]
        self.assertEqual(meta['page_label'],'1')
        self.assertEqual(meta['course'],'Course')
        self.assertEqual(meta['chunk_policy'],'structure_v2')
        self.assertEqual([call[0] for call in c.method_calls],['get','upsert','delete'])

    def test_embedding_failure_does_not_modify_existing_index(self):
        m,c,embed=self.load()
        m.chunk_document.return_value*=2
        embed.side_effect=[{'embeddings':[[1.0,2.0]]},RuntimeError('Embedding failed')]
        with self.assertRaises(RuntimeError):m.ingest_file('notes.pdf','Course')
        c.upsert.assert_not_called();c.delete.assert_not_called()

    def test_empty_document_does_not_modify_existing_index(self):
        m,c,embed=self.load();m.chunk_document.return_value=[]
        with self.assertRaisesRegex(ValueError,'No extractable text'):m.ingest_file('notes.pdf','Course')
        c.upsert.assert_not_called();c.delete.assert_not_called();embed.assert_not_called()

    def test_upsert_failure_does_not_delete_existing_chunks(self):
        m,c,embed=self.load();c.upsert.side_effect=RuntimeError('Storage failed')
        with self.assertRaises(RuntimeError):m.ingest_file('notes.pdf','Course')
        c.delete.assert_not_called()


if __name__=='__main__':unittest.main()
