const fs = require("fs");
const vm = require("vm");
const assert = require("assert/strict");
class Element {
  constructor() {
    this.children = [];
    this.options = [];
    this.value = "";
    this.style = {};
    this.dataset = {};
    this.listeners = {};
    this.attributes = {};
    this.innerText = "";
  }
  set innerHTML(value) {
    this.children = [];
    this.options = [];
  }
  appendChild(item) {
    this.children.push(item);
    this.options.push(item);
  }
  addEventListener(type, fn) {
    (this.listeners[type] ??= []).push(fn);
  }
  async dispatch(type, event = {}) {
    for (const fn of this.listeners[type] ?? []) await fn(event);
  }
  setAttribute(key, value) {
    this.attributes[key] = value;
  }
  focus() {
    this.focused = true;
  }
  click() {
    return this.dispatch("click");
  }
}
const elements = {};
const document = {
  getElementById: (id) => (elements[id] ??= new Element()),
  createElement: () => new Element(),
  addEventListener() {},
};
const context = vm.createContext({
  document,
  window: { innerWidth: 390, addEventListener() {} },
  MutationObserver: class {
    observe() {}
  },
  fetch: async () => ({ ok: true, json: async () => ({ courses: [], chats: [], documents: [] }) }),
  TextDecoder,
  console,
  XMLHttpRequest: class {},
  FormData: class {},
});
const html = fs.readFileSync(require("path").join(__dirname, "../frontend/index.html"), "utf8");
assert.match(html, /<script\s+src="app\.js"\s+defer><\/script>/);
assert.match(html, /href="styles\.css"/);
const source = fs.readFileSync(require("path").join(__dirname, "../frontend/app.js"), "utf8");
vm.runInContext(source, context);
(async () => {
  await new Promise(setImmediate);
  await elements.menuButton.click();
  assert.equal(elements.app.dataset.sidebar, "open");
  assert.equal(elements.menuButton.attributes["aria-expanded"], "true");
  await elements.closeSidebar.click();
  assert.equal(elements.app.dataset.sidebar, "closed");
  await elements.documentsTab.click();
  assert.equal(elements.app.dataset.view, "documents");
  assert.equal(elements.documentsTab.attributes["aria-selected"], "true");
  await elements.newChatButton.click();
  assert.equal(elements.app.dataset.view, "chat");
  assert.equal(elements.chatTab.attributes["aria-selected"], "true");
  assert.equal(elements.question.focused, true);
  await elements.noteFile.dispatch("change");
  assert.equal(elements.uploadOptions.open, true);
  let prevented = false;
  await elements.question.dispatch("keydown", {
    key: "Enter",
    isComposing: false,
    preventDefault() {
      prevented = true;
    },
  });
  assert.equal(prevented, true);
  assert.equal(elements.answer.innerText, "Please enter a question.");
  console.log(
    "Navigation passed: mobile sidebar, panel switching, new-chat return, upload expansion, Enter submission.",
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
