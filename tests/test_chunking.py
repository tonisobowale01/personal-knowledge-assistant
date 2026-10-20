import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.chunking import sections, chunk_document
from llama_index.core import Document


class Chunking(unittest.TestCase):
    def test_untitled_leading_definition_retains_page_context(self):
        text='All units share one link, called the alpha link. Its failure stops service.\nThe Beta Structure uses a separate arrangement.'
        chunks=chunk_document(Document(text=text))
        self.assertEqual(len(chunks),1)
        self.assertEqual(chunks[0].text,text)

    def test_definitions_have_separate_bodies_and_same_source(self):
        doc=Document(text='Chapter\no Alpha system: Uses separate units with local memory.\no Beta system: Uses units on one package for efficient communication.',metadata={'file_name':'notes.pdf','page_label':'7','course':'Test'})
        chunks=chunk_document(doc)
        self.assertEqual(len(chunks),2)
        self.assertNotIn('Beta system',chunks[0].text)
        self.assertNotIn('Alpha system',chunks[1].text)
        for chunk in chunks:
            self.assertEqual(chunk.metadata,doc.metadata)
            self.assertIn('Chapter',chunk.text)

    def test_numbered_section_keeps_nested_limitations(self):
        text='TOPICS\n======\n1. ALPHA\n--------\nAlpha does work.\n- Disadvantages:\n  • Long tasks may wait indefinitely.\n2. BETA\n-------\nBeta does different work.'
        chunks=chunk_document(Document(text=text))
        self.assertEqual(len(chunks),2)
        self.assertIn('Long tasks may wait indefinitely.',chunks[0].text)
        self.assertNotIn('2. BETA',chunks[0].text)
        self.assertTrue(all('TOPICS' in c.text for c in chunks))

    def test_continued_tables_repeat_headers_without_losing_rows(self):
        header='| Name | Meaning |\n|------|---------|'
        rows=[f'| entry{i} | Description of entry {i} with some extra information |' for i in range(30)]
        chunks=chunk_document(Document(text=header+'\n'+'\n'.join(rows)),chunk_size=100,overlap=10)
        self.assertGreater(len(chunks),1)
        for chunk in chunks:self.assertTrue(chunk.text.startswith(header))
        for row in rows:self.assertEqual(sum(row in c.text.splitlines() for c in chunks),1)

    def test_topology_style_definitions_preserve_each_complete_section(self):
        text='The Alpha Structure uses a shared link.\nIts failure stops service.\nThe Beta Structure uses separate links.\nA single link failure affects one unit.'
        chunks=chunk_document(Document(text=text))
        self.assertEqual(len(chunks),2)
        self.assertIn('Its failure stops service.',chunks[0].text)
        self.assertNotIn('separate links',chunks[0].text)
        self.assertIn('A single link failure affects one unit.',chunks[1].text)


if __name__=='__main__':unittest.main()
