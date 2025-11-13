let socket;
let username = "";
let currentMode = "global";
let targetUser = "";
let currentGroup = "";
let avatar = "";

function selectAvatar(src) {
  avatar = src;
  document.querySelectorAll(".avatar-option")
    .forEach(img => img.classList.remove("avatar-selected"));
  event.target.classList.add("avatar-selected");
}

function connect() {
  username = document.getElementById("username").value.trim();
  if (!username) return alert("Please enter your name!");
  if (!avatar) return alert("Please select an avatar!");

  //socket = new WebSocket("ws://localhost:8080/ws");
  const socketURL = location.hostname === "localhost"
  ? "ws://localhost:8080/ws"
  : "wss://socket-programming-2.onrender.com/ws";
  socket = new WebSocket(socketURL);

  socket.onopen = () => {
    socket.send(JSON.stringify({
        username: username,
        avatar: avatar
    }));
  };

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
      addMessage(data.message);
      return;
    }

    if (data.type === "chat") {
      const mine = data.sender === username;
      const msgBox = document.getElementById("messages");

      const div = document.createElement("div");
      div.className = `message ${mine ? "mine" : "other"}`;

      div.innerHTML = `
          <div style="display:flex; gap:10px; align-items:flex-start;">
              <img src="${data.sender_avatar}" style="width:40px; height:40px; border-radius:50%">
              <div>
                  <b>${mine ? "You" : data.sender}</b><br>
                  ${data.message}
              </div>
          </div>
      `;

      msgBox.appendChild(div);
      msgBox.scrollTop = msgBox.scrollHeight;
    }
  };

  socket.onclose = () => addMessage("Disconnected");

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
  addMessage(`Now chatting privately with ${u}`);
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

function addMessage(text) {
  const msgBox = document.getElementById("messages");
  const div = document.createElement("div");
  div.className = "message system";
  div.textContent = text;
  msgBox.appendChild(div);
  msgBox.scrollTop = msgBox.scrollHeight;
}
