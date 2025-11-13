let socket;
let username = "";
let currentMode = "global";
let targetUser = "";
let currentGroup = "";

function connect() {
  username = document.getElementById("username").value.trim();
  if (!username) return alert("Please enter your name!");

  socket = new WebSocket("wss://socket-programming-2.onrender.com/ws");
  socket.onopen = () => socket.send(username);

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "error") {
      alert(data.message);
      socket.close();
      return;
    }

    if (data.type === "user_list") {
      updateUserList(data.users);
      return;
    }

    if (data.type === "system") {
      addMessage(data.message, "system");
      return;
    }

    if (data.type === "chat") {
      const mine = data.sender === username;
      addMessage(`${mine ? "You" : data.sender}: ${data.message}`, mine ? "mine" : "other");
    }
  };

  socket.onclose = () => addMessage("Disconnected", "system");

  // show chat UI
  document.getElementById("login-screen").style.display = "none";
  document.getElementById("chat-screen").style.display = "flex";
}

function updateUserList(users) {
  const list = document.getElementById("user-list");
  list.innerHTML = "";
  users.forEach((u) => {
    if (u === username) return;
    const div = document.createElement("div");
    div.className = "user-item";
    div.textContent = u;
    div.onclick = () => openPrivateChat(u);
    list.appendChild(div);
  });
}

function openPrivateChat(u) {
  currentMode = "private";
  targetUser = u;
  document.getElementById("chat-header").textContent = `👤 Chat with ${u}`;
  addMessage(`Now chatting privately with ${u}`, "system");
}

function switchMode(mode) {
  currentMode = mode;
  targetUser = "";
  document.getElementById("group-name").style.display = mode === "group" ? "block" : "none";
  document.getElementById("chat-header").textContent =
    mode === "global" ? "🌍 Global Chat" : "👥 Group Chat";
}

function sendMessage() {
  const text = document.getElementById("message").value.trim();
  if (!text) return;

  let payload = { type: currentMode, message: text };

  if (currentMode === "private") {
    if (!targetUser) return alert("Select a user to chat privately");
    payload.target = targetUser;
  }

  if (currentMode === "group") {
    const groupName = document.getElementById("group-name").value.trim();
    payload.room = groupName || "default_group";
    document.getElementById("chat-header").textContent = `👥 Group: ${payload.room}`;
  }

  socket.send(JSON.stringify(payload));
  document.getElementById("message").value = "";
}

function addMessage(text, cls) {
  const msgBox = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = `message ${cls}`;
  div.textContent = text;
  msgBox.appendChild(div);
  msgBox.scrollTop = msgBox.scrollHeight;
}
