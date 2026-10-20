"""Split at explicit document structure; retain complete headings and table headers."""
import re

OUTLINE = re.compile(r'(?m)^(?:#{1,6}[ \t]+[^\n]+|(?:\d+\. )?[A-Z][A-Z0-9 ,()/?-]{3,}\r?\n[-=]{3,})')
PROSE = re.compile(r'(?m)^(?:The|In the) [A-Z][\w-]*(?: [A-Z][\w-]*)*')
LABEL = re.compile(r'(?m)^[ \t]*(?:o|[\u2022\uf0b7])[ \t]+[\w()-]+(?:[ \t]+[\w()-]+)+:')
TABLE = re.compile(r'(?m)^[ \t]*\|.*\|[ \t]*\r?$')


def sections(text):
    outlines = list(OUTLINE.finditer(text))
    # Numbered outlines own their nested bullets and explanations.
    headings = outlines or sorted([*PROSE.finditer(text), *LABEL.finditer(text)], key=lambda m:m.start())
    if not headings:
        return [('', '', text)]
    prefix = text[:headings[0].start()].strip()
    result = []
    if prefix and (len(prefix.split()) > 24 or re.search(r'[.!?]', prefix)):
        result.append(('', '', prefix))
        prefix = ''
    for i, heading in enumerate(headings):
        end = headings[i+1].start() if i+1 < len(headings) else len(text)
        title = heading.group().strip()
        body = text[heading.end():end].strip()
        if not body:
            prefix = '\n'.join(x for x in [prefix,title] if x)
        else:
            result.append((prefix, title, body))
    if not result:
        return [('', '', text)]
    return result


def chunk_document(document, chunk_size=512, overlap=50):
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.core.schema import MetadataMode, TextNode
    from llama_index.core.utils import get_tokenizer
    tokenize = get_tokenizer()
    metadata = max((document.get_metadata_str(mode=mode) for mode in [MetadataMode.EMBED,MetadataMode.LLM]), key=lambda s:len(tokenize(s)))
    nodes = []
    for prefix, title, body in sections(document.text):
        heading = '\n'.join(x for x in [prefix,title] if x)
        reserve = len(tokenize(metadata)) + len(tokenize(heading)) + 8
        budget = chunk_size - reserve
        if budget <= 0:
            raise ValueError('Document heading and metadata exceed the chunk budget')
        splitter = SentenceSplitter(chunk_size=budget,chunk_overlap=min(overlap,budget//4))
        lines = body.splitlines()
        parts = []
        i = 0
        while i < len(lines):
            if not TABLE.match(lines[i]):
                end = i+1
                while end < len(lines) and not TABLE.match(lines[end]): end += 1
                parts.extend(splitter.split_text('\n'.join(lines[i:end])))
                i = end
                continue
            end = i+1
            while end < len(lines) and TABLE.match(lines[end]): end += 1
            table = lines[i:end]
            # Repeat the actual header and separator in every continued table chunk.
            header = table[:2] if len(table)>1 and re.match(r'^\s*\|[\s:|\-]+\|\s*$',table[1]) else []
            current = list(header)
            for row in table[len(header):]:
                if len(tokenize('\n'.join(current+[row]))) > budget:
                    if len(current) == len(header):
                        raise ValueError('A table row exceeds the chunk budget; row cannot be split safely')
                    parts.append('\n'.join(current))
                    current = list(header)
                    if len(tokenize('\n'.join(current+[row]))) > budget:
                        raise ValueError('A table row exceeds the chunk budget')
                current.append(row)
            if current: parts.append('\n'.join(current))
            i = end
        for part in parts:
            text = '\n'.join(x for x in [heading,part.strip()] if x)
            nodes.append(TextNode(text=text, metadata=dict(document.metadata)))
    return nodes
