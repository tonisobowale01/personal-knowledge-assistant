const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
class Element {
 constructor() { this.children=[]; this.value=''; this.innerText=''; this.disabled=false; this.listeners={}; this.style={}; this.options=[]; }
 set innerHTML(value) { this.children=[]; }
 appendChild(item) { this.children.push(item); this.options.push(item); item.parent=this; }
 remove() { this.parent.children=this.parent.children.filter(item=>item!==this); }
 addEventListener(name, callback) { this.listeners[name]=callback; }
}
const elements = {};
const document = { getElementById: id => elements[id] ||= new Element(), createElement: tag => Object.assign(new Element(), {tagName:tag.toUpperCase()}), createTextNode: text => Object.assign(new Element(), {innerText:text}) };
const uploads=[];
class FakeXHR {
 constructor(){this.upload={};}
 open(method,url){this.method=method;this.url=url;}
 send(body){this.body=body;uploads.push(this);}
}
class FakeFormData { constructor(){this.fields=[];} append(...pair){this.fields.push(pair);} }
let chats=[], messages={}, nextId=1, failCreate=false, failLoad=false, failAsk=false;
let holdAsk;
let renameInput=null, confirmed=false, failMutation=false, failList=false;
const requests=[];
const fetchPaths=[];
const fetch = async (url, options={}) => {
 const path=url.replace('http://127.0.0.1:8000','');
 fetchPaths.push(path);
 const body=options.body ? JSON.parse(options.body) : null;
 if(path==='/courses') return response({courses:['OS']});
 if(path==='/documents') return response({documents:[{file:'Notes with spaces.pdf',course:'OS'},{file:'sample.txt',course:'OS'}]});
 if(path==='/chats' && options.method==='POST') {
  if(failCreate) return response({}, false);
  const chat={id:nextId++,...body}; chats.push(chat); messages[chat.id]=[]; return response(chat);
 }
 if(path==='/chats') return response({chats}, !failList);
 if(path.startsWith('/chats/') && ['PATCH','DELETE'].includes(options.method)) {
  if(failMutation) return response({}, false);
  const id=Number(path.split('/')[2]);
  if(options.method==='PATCH') chats.find(chat=>chat.id===id).title=body.title;
  else { chats=chats.filter(chat=>chat.id!==id); delete messages[id]; }
  return response({});
 }
 if(path.startsWith('/chats/')) return response({messages:messages[path.split('/')[2]]}, !failLoad);
 if(path==='/ask/stream') {
  requests.push(body);
  if(holdAsk) await holdAsk;
  if(failAsk) return streamResponse([{type:'delta',text:'Partial'},{type:'error',message:'Model failed'}]);
  messages[body.chat_id].push({role:'user',content:body.question},{role:'assistant',content:'Answer'});
  return streamResponse([{type:'status',message:'Searching'},{type:'delta',text:'An'},{type:'delta',text:'swer'},{type:'done',answer:'Answer',sources:[{file:'Notes with spaces.pdf',page:'7'},{file:'Notes with spaces.pdf',page:'7'},{file:'sample.txt',page:null},{file:'sample.txt',page:null}]}]);
 }
 throw new Error(path);
};
function streamResponse(events) {
 const bytes=new TextEncoder().encode(events.map(event=>JSON.stringify(event)+'\n').join(''));
 let offset=0;
 return {ok:true,body:{getReader:()=>({read:async()=> {
  if(offset>=bytes.length) return {done:true};
  const value=bytes.slice(offset,offset+7);offset+=7;return {value,done:false};
 },cancel:async()=>{},releaseLock:()=>{}})}};
}
function response(data,ok=true) {return {ok,json:async()=>data};}
const context=vm.createContext({document,fetch,console,TextDecoder,XMLHttpRequest:FakeXHR,FormData:FakeFormData,prompt:()=>renameInput,confirm:()=>confirmed,alert:()=>{}});
const html=fs.readFileSync(require('path').join(__dirname, '../frontend/index.html'),'utf8');
assert.match(html,/<body\b[^>]*\bdata-server-no-reload(?:\s|>)/);
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],context);
const state=()=>vm.runInContext('({currentChatId,history:conversationHistory.slice(),busy})',context);
const click=id=>elements[id].listeners.click();
(async()=>{
 await new Promise(setImmediate);
 const preview=elements.documentsList.children[0].children.find(item=>item.innerText==='Preview');
 assert.equal(preview.href,'http://127.0.0.1:8000/documents/Notes%20with%20spaces.pdf/preview');
 assert.equal(preview.target,'_blank'); assert.equal(preview.rel,'noopener noreferrer');
 assert.equal(fetchPaths.some(path=>path.includes('/preview')),false);
 const badPage=vm.runInContext("previewLink('notes.pdf', 'unknown').href",context);
 assert.equal(badPage.endsWith('/preview'),true);
 document.getElementById('noteFile').files=[{name:'sample.txt'}]; elements.uploadCourse.value='OS';
 const uploading=click('uploadButton');
 assert.equal(elements.uploadButton.disabled,true); assert.equal(elements.noteFile.disabled,true);
 await click('uploadButton'); assert.equal(uploads.length,1);
 uploads[0].upload.onprogress({lengthComputable:true,loaded:5,total:10});
 assert.match(elements.uploadStatus.innerText,/50%/);
 uploads[0].upload.onload();
 assert.match(elements.uploadStatus.innerText,/File sent.*Reading notes/);
 assert.equal(elements.uploadButton.disabled,true);
 uploads[0].status=200;uploads[0].responseText=JSON.stringify({filename:'sample.txt',chunks_stored:3});uploads[0].onload();await uploading;
 assert.match(elements.uploadStatus.innerText,/Ready: sample.txt/);assert.equal(elements.uploadButton.disabled,false);
 elements.uploadCourse.value='OS';const failedUpload=click('uploadButton');uploads[1].onerror();await failedUpload;
 assert.match(elements.uploadStatus.innerText,/may still be processing/);assert.equal(elements.noteFile.disabled,false);
 elements.uploadCourse.value='OS';failList=false;
 document.getElementById('course').value='OS'; document.getElementById('question').value='First';
 let release; holdAsk=new Promise(resolve=>release=resolve);
 const pending=click('askButton'); await new Promise(setImmediate);
 assert.equal(state().busy,true);
 await click('askButton'); await click('newChatButton');
 assert.equal(state().currentChatId,1);
 release(); await pending; holdAsk=null;
 assert.equal(chats.length,1); assert.equal(requests.length,1);
 assert.equal(elements.chatList.children.length,3);
 assert.equal(state().history.length,2);
 const sourceDetails=elements.chat.children.find(e=>e.tagName==='DETAILS');
 assert.equal(sourceDetails.open===true,false);
 assert.equal(sourceDetails.children[0].innerText,'Show sources (2)');
 assert.equal(sourceDetails.children[2].children[0].href,'http://127.0.0.1:8000/documents/Notes%20with%20spaces.pdf/preview#page=7');
 assert.equal(sourceDetails.children[3].children[0].innerText,'sample.txt');
 assert.equal(elements.sources.children.length,0);
 assert.equal(elements.chat.children.some(e=>e.innerText.startsWith('Sources:')),false);
 assert.equal(elements.chat.children.some(e=>e.innerText.includes('page null')),false);
 elements.question.value='Follow-up'; await click('askButton');
 assert.equal(requests[1].chat_id,1); assert.equal(requests[1].history.length,2);
 await click('newChatButton'); assert.equal(state().currentChatId,null); assert.equal(state().history.length,0);
 elements.question.value='Second'; await click('askButton'); assert.equal(chats.length,2);
 await elements.chatList.children[0].listeners.click(); assert.equal(state().currentChatId,1); assert.equal(state().history.length,4); assert.equal(elements.course.value,'OS');
 failLoad=true; await elements.chatList.children[3].listeners.click(); assert.equal(state().currentChatId,1); assert.equal(state().history.length,4); failLoad=false;
 failAsk=true; elements.question.value='Failed'; await click('askButton'); assert.equal(state().history.length,4); assert.equal(state().busy,false); failAsk=false;
 await click('newChatButton'); failCreate=true; elements.question.value='Create failure'; await click('askButton'); assert.equal(state().currentChatId,null); assert.equal(state().history.length,0); assert.equal(state().busy,false);
 failCreate=false;
 await elements.chatList.children[0].listeners.click();
 renameInput='   '; await elements.chatList.children[1].listeners.click(); assert.equal(chats[0].title,'First');
 renameInput=null; await elements.chatList.children[1].listeners.click(); assert.equal(chats[0].title,'First');
 renameInput=' Renamed '; await elements.chatList.children[1].listeners.click(); assert.equal(chats[0].title,'Renamed'); assert.equal(state().currentChatId,1); assert.equal(state().history.length,4);
 confirmed=false; await elements.chatList.children[2].listeners.click(); assert.equal(chats.length,2);
 confirmed=true; failMutation=true; await elements.chatList.children[2].listeners.click(); assert.equal(chats.length,2); assert.equal(state().currentChatId,1); assert.equal(state().busy,false); failMutation=false;
 await elements.chatList.children[5].listeners.click(); assert.equal(chats.length,1); assert.equal(state().currentChatId,1); assert.equal(state().history.length,4);
 failList=true; await elements.chatList.children[2].listeners.click(); assert.equal(chats.length,0); assert.equal(elements.chatList.children.length,0); assert.equal(state().currentChatId,null); assert.equal(state().history.length,0); assert.equal(state().busy,false);
 const received=[];
 context.testResponse=streamResponse([{type:'delta',text:'Hello \u{1F30D}'},{type:'done',answer:'Hello \u{1F30D}',sources:[]}]);
 context.collect=event=>received.push(event);
 await vm.runInContext('readAnswerStream(testResponse, collect)',context);
 assert.equal(received[0].text,'Hello \u{1F30D}');
 context.testResponse=streamResponse([{type:'delta',text:'Partial'}]);
 await assert.rejects(vm.runInContext('readAnswerStream(testResponse, collect)',context),/ended unexpectedly/);
 let allowFinish;
 const waiting=new Promise(resolve=>allowFinish=resolve);
 context.testResponse={body:{getReader:()=>{
  let index=0;return {read:async()=>{
   if(index++===0) return {done:false,value:new TextEncoder().encode(JSON.stringify({type:'delta',text:'First words'})+'\n')};
   if(index===2) {await waiting;return {done:false,value:new TextEncoder().encode(JSON.stringify({type:'done',answer:'First words',sources:[]})+'\n')};}
   return {done:true};
  },cancel:async()=>{},releaseLock:()=>{}};
 }}};
 const before=received.length;
 const reading=vm.runInContext('readAnswerStream(testResponse, collect)',context);
 await new Promise(setImmediate);
 assert.equal(received.length,before+1);assert.equal(received.at(-1).text,'First words');
 allowFinish();await reading;
 console.log('Streaming passed: fragmented UTF-8, incremental delivery, missing completion, model errors, history recovery.');
 console.log('Upload passed: sending/processing/completion states, duplicate prevention, disabled controls, connection-failure recovery.');
 console.log('Sources passed: collapsed per-answer details, deduplicated preview links, no repeated source text.');
 console.log('Preview links passed: no eager document fetches, encoded filenames, source page links, separate tab.');
 console.log('Rename/delete flows passed: validation, cancellation, persistence updates, active/inactive deletion, failure recovery.');
 console.log('Frontend flow passed: creation, list refresh, continuation, switching, reset, duplicate clicks, load/create/ask failures.');
})().catch(error=>{console.error(error);process.exitCode=1;});

