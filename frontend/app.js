function feedback(id, state, text) {
  const element = document.getElementById(id);
  element.className = `feedback ${state}`;
  element.innerText = text;
}
async function readAnswerStream(response, onEvent) {
  if (!response.body) throw new Error("Streaming is unavailable");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let newline;
      while ((newline = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, newline);
        buffer = buffer.slice(newline + 1);
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (completed) throw new Error("Unexpected event after completion");
        if (event.type === "error") throw new Error(event.message);
        onEvent(event);
        if (event.type === "done") completed = true;
      }
      if (done) break;
    }
    if (buffer.trim() || !completed) throw new Error("The answer stream ended unexpectedly");
  } finally {
    try {
      await reader.cancel();
    } catch (_) {}
    reader.releaseLock();
  }
}

function sourceLabel(source) {
  return source.page && source.page !== "unknown"
    ? `${source.file} - page ${source.page}`
    : source.file;
}

function previewLink(file, page, label = "Preview") {
  const link = document.createElement("a");
  const pageNumber = Number(page);
  const fragment =
    /\.pdf$/i.test(file) && Number.isInteger(pageNumber) && pageNumber > 0
      ? `#page=${pageNumber}`
      : "";
  link.href = `http://127.0.0.1:8000/documents/${encodeURIComponent(file)}/preview${fragment}`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.innerText = label;
  return link;
}

let currentChatId = null;
let busy = false;
function renderSearchScope() {
  if (typeof window === "undefined") return;
  const select = document.getElementById("course");
  const summary = document.getElementById("scopeSummary");
  summary.innerText = `Search scope: ${select.value || "All courses"}`;
  summary.setAttribute("aria-disabled", String(select.disabled));
  const list = document.getElementById("scopeOptions");
  list.innerHTML = "";
  for (const option of Array.from(select.options)) {
    const button = document.createElement("button");
    button.type = "button";
    button.innerText = option.value || "All courses";
    button.disabled = select.disabled;
    button.setAttribute("aria-pressed", String(option.value === select.value));
    button.addEventListener("click", () => {
      if (busy) return;
      select.value = option.value;
      document.getElementById("mobileScope").open = false;
      renderSearchScope();
      summary.focus();
    });
    list.appendChild(button);
  }
}
function setBusy(value) {
  busy = value;
  if (!value && document.getElementById("answer").className === "feedback working")
    document.getElementById("answer").className = "feedback notice";
  for (const id of ["askButton", "newChatButton", "course"]) {
    document.getElementById(id).disabled = value;
  }
  for (const item of document.getElementById("chatList").children) item.disabled = value;
  if (value) document.getElementById("mobileScope").open = false;
  renderSearchScope();
}
function renderHistory() {
  document.getElementById("chat").innerHTML = "";
  for (const message of conversationHistory) {
    addMessage(message.role === "user" ? "You" : "Assistant", message.content);
  }
}
document.getElementById("newChatButton").addEventListener("click", () => {
  if (busy) return;
  currentChatId = null;
  conversationHistory.length = 0;
  renderHistory();
  document.getElementById("answer").innerText = "";
  document.getElementById("sources").innerHTML = "";
  document.getElementById("question").value = "";
});

// History of messages in the chat section
const conversationHistory = [];
// Ask button and query submission
// Handle query submission
const button = document.getElementById("askButton");
button.addEventListener("click", async () => {
  if (busy) return;
  const question = document.getElementById("question").value.trim();
  const course = document.getElementById("course").value;

  // Validate the question before sending it to the API
  if (!question.trim()) {
    document.getElementById("answer").innerText = "Please enter a question.";
    return;
  }

  const historyForRequest = [...conversationHistory];

  addMessage("You", question);
  setBusy(true);

  feedback("answer", "working", "Getting your question ready…");
  document.getElementById("sources").innerHTML = "";

  try {
    if (currentChatId === null) {
      await createChat(question, course);
      // A list refresh failure must not abort a successfully created chat.
      await loadChats().catch(() => {});
    }
    const response = await fetch("http://127.0.0.1:8000/ask/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        question,
        course: course || null,
        history: historyForRequest,
        chat_id: currentChatId,
      }),
    });

    if (!response.ok) {
      throw new Error("API request failed");
    }
    let data;
    let assistantMessage = null;
    let streamedAnswer = "";
    await readAnswerStream(response, (event) => {
      if (event.type === "status") {
        feedback("answer", "working", event.message);
      } else if (event.type === "delta") {
        if (!assistantMessage) assistantMessage = addMessage("Assistant", "");
        streamedAnswer += event.text;
        assistantMessage.innerText = `Assistant: ${streamedAnswer}`;
        feedback("answer", "working", "Writing your answer… You can read it as it arrives.");
      } else if (event.type === "done") {
        data = event;
      }
    });
    if (!assistantMessage) assistantMessage = addMessage("Assistant", data.answer);
    assistantMessage.innerText = `Assistant: ${data.answer}`;

    // Display the answer and sources from the API response
    conversationHistory.push(
      { role: "user", content: question },
      { role: "assistant", content: data.answer },
    );
    document.getElementById("answer").innerText = "";
    document.getElementById("question").value = "";
    const selectedCourse = document.getElementById("course").value || "All courses";
    const seenSources = new Set();
    const sources = data.sources.filter((source) => {
      const key = sourceLabel(source);
      if (seenSources.has(key)) return false;
      seenSources.add(key);
      return true;
    });
    if (sources.length > 0) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.innerText = `Show sources (${sources.length})`;
      details.appendChild(summary);
      const scope = document.createElement("p");
      scope.innerText = `Search scope: ${selectedCourse}`;
      details.appendChild(scope);
      for (const source of sources) {
        const item = document.createElement("p");
        if (source.file)
          item.appendChild(previewLink(source.file, source.page, sourceLabel(source)));
        details.appendChild(item);
      }
      document.getElementById("chat").appendChild(details);
    }
  } catch (error) {
    renderHistory();
    // Reload SQLite after an uncertain network failure before allowing a retry.
    if (currentChatId !== null) {
      try {
        const response = await fetch(`http://127.0.0.1:8000/chats/${currentChatId}/messages`);
        if (!response.ok) throw new Error("Reload failed");
        const data = await response.json();
        conversationHistory.splice(
          0,
          conversationHistory.length,
          ...data.messages.map(({ role, content }) => ({ role, content })),
        );
        renderHistory();
      } catch (_) {}
    }
    feedback(
      "answer",
      "error",
      "Could not complete the request. Check the saved chat before retrying.",
    );
  } finally {
    setBusy(false);
  }
});

// Handle upload course selection and new course input visibility
const uploadCourse = document.getElementById("uploadCourse");
const newCourseInput = document.getElementById("newCourse");

uploadCourse.addEventListener("change", () => {
  if (uploadCourse.value === "__new__") {
    newCourseInput.style.display = "block";
  } else {
    newCourseInput.style.display = "none";
  }
});

// Handle note upload
const uploadButton = document.getElementById("uploadButton");
let uploading = false;
if (typeof window !== "undefined")
  window.addEventListener("beforeunload", (event) => {
    if (uploading) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
function uploadFile(formData, status) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", "http://127.0.0.1:8000/upload");
    request.upload.onprogress = (event) => {
      status.className = "feedback working";
      status.innerText = event.lengthComputable
        ? `Sending file: ${Math.round((event.loaded / event.total) * 100)}%. Processing follows; keep this page open.`
        : "Sending file. Processing follows; keep this page open.";
    };
    request.upload.onload = () => {
      status.className = "feedback working";
      status.innerText =
        "File sent. Reading notes and preparing search data… Please keep this page open.";
    };
    request.onload = () => {
      if (request.status < 200 || request.status >= 300) {
        reject(new Error("Upload failed"));
        return;
      }
      try {
        resolve(JSON.parse(request.responseText));
      } catch (error) {
        reject(error);
      }
    };
    request.onerror = () => reject(new Error("Connection lost"));
    request.onabort = () => reject(new Error("Upload interrupted"));
    request.send(formData);
  });
}
uploadButton.addEventListener("click", async () => {
  if (uploading) return;
  const fileInput = document.getElementById("noteFile");
  let course = uploadCourse.value;

  if (course === "__new__") {
    course = newCourseInput.value.trim();
  }

  const status = document.getElementById("uploadStatus");

  const file = fileInput.files[0];

  if (!file) {
    feedback("uploadStatus", "notice", "Please choose a file.");
    return;
  }

  if (!course) {
    feedback("uploadStatus", "notice", "Please enter a course name.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("course", course);

  uploading = true;
  const uploadControls = [uploadButton, fileInput, uploadCourse, newCourseInput];
  uploadControls.forEach((control) => {
    control.disabled = true;
  });
  feedback(
    "uploadStatus",
    "working",
    "Sending file… Keep this page open while your notes are processed.",
  );

  try {
    const data = await uploadFile(formData, status);
    feedback(
      "uploadStatus",
      "success",
      `Ready: ${data.filename} was processed and is available for questions.`,
    );
    const refresh = await Promise.allSettled([loadCourses(), loadDocuments()]);
    if (refresh.some((result) => result.status === "rejected"))
      status.innerText +=
        " Saved successfully, but the lists could not refresh. Refresh them before uploading again.";
  } catch (error) {
    feedback(
      "uploadStatus",
      "error",
      "Could not confirm processing finished. Check the document list and backend before retrying; the server may still be processing.",
    );
  } finally {
    uploading = false;
    uploadControls.forEach((control) => {
      control.disabled = false;
    });
  }
});

async function loadCourses() {
  const response = await fetch("http://127.0.0.1:8000/courses");
  const data = await response.json();

  const askCourse = document.getElementById("course");
  const selectedCourse = askCourse.value;
  const uploadCourse = document.getElementById("uploadCourse");

  askCourse.innerHTML = '<option value="">All courses</option>';

  uploadCourse.innerHTML = `
    <option value="">Select courses</option>
    <option value="__new__">+ Add new courses</option>`;

  for (const course of data.courses) {
    const askOption = document.createElement("option");
    askOption.value = course;
    askOption.innerText = course;
    askCourse.appendChild(askOption);

    const uploadOption = document.createElement("option");
    uploadOption.value = course;
    uploadOption.innerText = course;
    uploadCourse.appendChild(uploadOption);
  }
  if (Array.from(askCourse.options).some((option) => option.value === selectedCourse))
    askCourse.value = selectedCourse;
  renderSearchScope();
}

async function loadDocuments() {
  const status = document.getElementById("documentsStatus");
  status.className = "list-status working";
  status.innerText = "Loading your documents…";
  try {
    const response = await fetch("http://127.0.0.1:8000/documents");
    if (!response.ok) throw new Error("Could not load documents");
    const data = await response.json();

    const documentsList = document.getElementById("documentsList");
    documentsList.innerHTML = "";

    for (const doc of data.documents) {
      const item = document.createElement("div");

      const label = document.createElement("span");
      label.innerText = `${doc.file} - ${doc.course}`;

      const deleteButton = document.createElement("button");
      deleteButton.innerText = "Delete";
      deleteButton.addEventListener("click", async () => {
        const confirmed = confirm(`Delete ${doc.file}?`);

        if (!confirmed) return;

        const response = await fetch(
          `http://127.0.0.1:8000/documents/${encodeURIComponent(doc.file)}`,
          {
            method: "DELETE",
          },
        );

        if (!response.ok) {
          alert("Failed to delete the document.");
          return;
        }
        await loadDocuments();
        await loadCourses();
      });

      item.appendChild(label);
      if (/\.(pdf|txt)$/i.test(doc.file)) {
        item.appendChild(document.createTextNode(" "));
        item.appendChild(previewLink(doc.file));
        item.appendChild(document.createTextNode(" "));
      }
      item.appendChild(deleteButton);

      documentsList.appendChild(item);
    }
    status.className = "list-status";
    status.innerText = data.documents.length
      ? ""
      : "No documents yet. Upload a PDF or text file from the sidebar to get started.";
  } catch (error) {
    status.className = "list-status";
    status.innerText = "Could not load your documents. Check the backend, then choose Refresh.";
    throw error;
  }
}

async function createChat(title, course) {
  const response = await fetch("http://127.0.0.1:8000/chats", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      title: title,
      course: course || null,
    }),
  });

  if (!response.ok) {
    throw new Error("Could not create chat");
  }

  const data = await response.json();

  currentChatId = data.id;

  return data;
}

async function loadChats() {
  const status = document.getElementById("chatListStatus");
  status.className = "list-status working";
  status.innerText = "Loading your chats…";
  try {
    const response = await fetch("http://127.0.0.1:8000/chats");
    if (!response.ok) throw new Error("Could not load chats");
    const data = await response.json();

    const chatList = document.getElementById("chatList");
    chatList.innerHTML = "";

    for (const chat of data.chats) {
      const button = document.createElement("button");

      button.innerText = chat.title;

      button.disabled = busy;
      button.addEventListener("click", async () => {
        if (busy) return;
        setBusy(true);
        feedback("answer", "working", "Opening your saved conversation…");
        try {
          const response = await fetch(`http://127.0.0.1:8000/chats/${chat.id}/messages`);
          if (!response.ok) throw new Error("Could not load chat");
          const data = await response.json();
          currentChatId = chat.id;
          conversationHistory.splice(
            0,
            conversationHistory.length,
            ...data.messages.map(({ role, content }) => ({ role, content })),
          );
          const courseSelect = document.getElementById("course");
          if (
            chat.course &&
            !Array.from(courseSelect.options).some((option) => option.value === chat.course)
          ) {
            const option = document.createElement("option");
            option.value = chat.course;
            option.innerText = chat.course;
            courseSelect.appendChild(option);
          }
          courseSelect.value = chat.course || "";
          renderHistory();
          document.getElementById("sources").innerHTML = "";
          document.getElementById("answer").innerText = "";
        } catch (error) {
          document.getElementById("answer").innerText =
            "Could not load chat. Your current conversation is still selected.";
        } finally {
          setBusy(false);
        }
      });

      chatList.appendChild(button);
      let renameControl, deleteControl;
      for (const action of ["Rename", "Delete"]) {
        const control = document.createElement("button");
        control.innerText = action;
        control.title = `${action} chat`;
        control.disabled = busy;
        control.addEventListener("click", async () => {
          if (busy) return;
          let title;
          if (action === "Rename") {
            title = prompt("New chat title:", chat.title);
            if (title === null) return;
            title = title.trim();
            if (!title) {
              document.getElementById("answer").innerText = "Please enter a chat title.";
              return;
            }
          } else if (
            !confirm(`Delete "${chat.title}" and all its messages? This cannot be undone.`)
          ) {
            return;
          }
          setBusy(true);
          try {
            const response = await fetch(`http://127.0.0.1:8000/chats/${chat.id}`, {
              method: action === "Rename" ? "PATCH" : "DELETE",
              ...(action === "Rename"
                ? {
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ title }),
                  }
                : {}),
            });
            if (!response.ok) throw new Error("Chat update failed");
            if (action === "Rename") {
              chat.title = title;
              button.innerText = title;
            } else {
              // Remove the confirmed deletion even if refreshing the list fails.
              button.remove();
              renameControl.remove();
              deleteControl.remove();
              if (currentChatId === chat.id) {
                currentChatId = null;
                conversationHistory.length = 0;
                renderHistory();
                document.getElementById("question").value = "";
                document.getElementById("sources").innerHTML = "";
              }
            }
            document.getElementById("answer").innerText =
              action === "Rename" ? "Chat renamed." : "Chat deleted.";
            try {
              await loadChats();
            } catch (_) {
              document.getElementById("answer").innerText +=
                " Could not refresh the chat list. Refresh the page to reload it.";
            }
          } catch (error) {
            document.getElementById("answer").innerText =
              `Could not ${action.toLowerCase()} the chat. Refresh the chat list before retrying.`;
          } finally {
            setBusy(false);
          }
        });
        chatList.appendChild(control);
        if (action === "Rename") renameControl = control;
        else deleteControl = control;
      }
    }
    status.className = "list-status";
    status.innerText = data.chats.length
      ? ""
      : "No saved chats yet. Your first question starts a conversation.";
  } catch (error) {
    status.className = "list-status";
    status.innerText = "Could not load saved chats. Check the backend and refresh the page.";
    throw error;
  }
}
document
  .getElementById("refreshDocuments")
  .addEventListener("click", () => loadDocuments().catch(() => {}));

function addMessage(role, text) {
  const chat = document.getElementById("chat");

  const message = document.createElement("div");
  message.className = `message ${role === "You" ? "user" : "assistant"}`;
  message.innerText = `${role}: ${text}`;

  chat.appendChild(message);
  return message;
}

if (typeof window !== "undefined") {
  const app = document.getElementById("app");
  document.getElementById("scopeSummary").addEventListener("click", (event) => {
    if (busy) event.preventDefault();
  });
  document.getElementById("course").addEventListener("change", renderSearchScope);
  document.addEventListener("click", (event) => {
    if (!document.getElementById("mobileScope").contains(event.target))
      document.getElementById("mobileScope").open = false;
  });
  document.getElementById("scopeSummary").addEventListener("keydown", (event) => {
    if (event.key === "Escape") document.getElementById("mobileScope").open = false;
  });
  const menu = document.getElementById("menuButton");
  const closeSidebar = () => {
    app.dataset.sidebar = "closed";
    menu.setAttribute("aria-expanded", "false");
  };
  menu.addEventListener("click", () => {
    const open = app.dataset.sidebar !== "open";
    app.dataset.sidebar = open ? "open" : "closed";
    menu.setAttribute("aria-expanded", String(open));
  });
  document.getElementById("closeSidebar").addEventListener("click", closeSidebar);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeSidebar();
      menu.focus();
    }
  });
  for (const [id, view] of [
    ["chatTab", "chat"],
    ["documentsTab", "documents"],
  ]) {
    document.getElementById(id).addEventListener("click", () => {
      app.dataset.view = view;
      closeSidebar();
      document.getElementById("chatTab").setAttribute("aria-selected", String(view === "chat"));
      document
        .getElementById("documentsTab")
        .setAttribute("aria-selected", String(view === "documents"));
      if (view === "documents" && window.innerWidth > 950)
        document.getElementById("refreshDocuments").focus();
    });
  }
  document.getElementById("noteFile").addEventListener("change", () => {
    document.getElementById("uploadOptions").open = true;
  });
  document.getElementById("question").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.isComposing) {
      event.preventDefault();
      document.getElementById("askButton").click();
    }
  });
  const showChat = () => {
    app.dataset.view = "chat";
    document.getElementById("chatTab").setAttribute("aria-selected", "true");
    document.getElementById("documentsTab").setAttribute("aria-selected", "false");
    closeSidebar();
  };
  document.getElementById("newChatButton").addEventListener("click", () => {
    if (!busy) {
      showChat();
      document.getElementById("question").focus();
    }
  });
  document.getElementById("chatList").addEventListener("click", (event) => {
    if (event.target.matches("button:nth-child(3n+1)")) showChat();
  });
  const thread = document.getElementById("thread");
  let follow = true;
  thread.addEventListener("scroll", () => {
    follow = thread.scrollHeight - thread.scrollTop - thread.clientHeight < 120;
  });
  new MutationObserver(() => {
    if (follow) thread.scrollTop = thread.scrollHeight;
  }).observe(document.getElementById("chat"), {
    childList: true,
    subtree: true,
    characterData: true,
  });
}
Promise.allSettled([loadCourses(), loadDocuments(), loadChats()]).then((results) => {
  if (results.some((result) => result.status === "rejected"))
    document.getElementById("answer").innerText =
      "Some data could not load. Check the backend and refresh.";
});
