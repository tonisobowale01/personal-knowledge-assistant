"""Trial: prefer query-matching headings within a semantic candidate pool."""
import re

STOP = set('a an the what which who whom whose is are was were be been being do does did can could would should will may might to of for in on at by from with and or if then than that this these those how when where why it its he his she her they their we our you your'.split())

def terms(text):
    words=re.findall(r'[^\W\d_]+',text.casefold())
    return {w[:-1] if len(w)>4 and w.endswith('s') and not w.endswith('ss') else w for w in words if w not in STOP}

def heading_score(text,query):
    lines=[line for line in text.splitlines() if re.search(r'[^\W\d_]',line)]
    return len(terms('\n'.join(lines[:2])) & terms(query))

class HeadingCollection:
    def __init__(self,base,query): self.base=base;self.query_text=query
    def query(self,**kwargs):
        kwargs['n_results']=20
        result=self.base.query(**kwargs)
        distances=result['distances'][0]
        if distances and distances[0]<=1.1:
            order=sorted(range(len(distances)),key=lambda i:(-heading_score(result['documents'][0][i],self.query_text),distances[i]))[:5]
        else:order=list(range(min(5,len(distances))))
        return {key:[[values[0][i] for i in order]] for key,values in result.items() if key in ['documents','metadatas','distances','ids']}
