from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter

parser = PDFReader()

documents = SimpleDirectoryReader(input_files=["data/notes/networking summary.pdf"], file_extractor={".pdf": parser}).load_data()

splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
nodes = splitter.get_nodes_from_documents(documents)

print("Number of nodes:", len(nodes))
for i, node in enumerate(nodes[:3]):
    print(f"NODE {i}")
    print(node.text[:300])
    print(node.metadata)
    print("-----")


print("Number of documents:", len(documents))
# print(documents[0].text[:1000])
# for i, doc in enumerate(documents):
#     print(f"DOCUMENT {i}")
#     print(doc.metadata)
#     print("-----")

