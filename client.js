let ws;
let username;
const messagesDiv = document.getElementById("messages");
const input = document.getElementById("msgInput");
const loginArea = document.getElementById("loginArea");
const chatArea = document.getElementById("chatArea");
const usernameInput = document.getElementById("usernameInput");
const userListDiv = document.getElementById("userList");

function joinChat() {
  username = usernameInput.value.trim();
  if (!username) {
    alert("Please enter your name");
    return;
  }

  ws = new WebSocket("ws://localhost:5000");

  ws.onopen = () => {
    ws.send(username); // ส่งชื่อให้ server
  };

  ws.onmessage = (event) => {
    const msgText = event.data;

    // ✅ ตรวจว่าข้อมูลที่ได้เป็น JSON หรือข้อความปกติ
    try {
      const data = JSON.parse(msgText);
      if (data.type === "user_list") {
        updateUserList(data.users);
        return;
      }
    } catch {
      // ถ้า parse ไม่ได้ แปลว่าเป็นข้อความแชทธรรมดา
    }

    // ตรวจ username ซ้ำ
    if (msgText.startsWith("❌ Username already exists")) {
      alert("This username is already taken. Please choose another name.");
      ws.close();
      chatArea.style.display = "none";
      loginArea.style.display = "block";
      usernameInput.value = "";
      messagesDiv.innerHTML = "";
      return;
    }

    // แสดงพื้นที่แชทหลังเชื่อมต่อสำเร็จ
    if (loginArea.style.display !== "none") {
      loginArea.style.display = "none";
      chatArea.style.display = "block";
    }

    // เพิ่มข้อความในห้องแชท
    const msg = document.createElement("div");
    msg.textContent = msgText;
    messagesDiv.appendChild(msg);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  };

  ws.onclose = () => {
    const msg = document.createElement("div");
    msg.textContent = "❌ Disconnected from server";
    msg.style.color = "red";
    messagesDiv.appendChild(msg);
  };
}

function sendMessage() {
  const text = input.value.trim();
  if (text && ws.readyState === WebSocket.OPEN) {
    ws.send(text);
    const msg = document.createElement("div");
    msg.textContent = `🧍‍♂️ You: ${text}`;
    msg.style.fontWeight = "bold";
    messagesDiv.appendChild(msg);
    input.value = "";
  }
}

// ✅ ฟังก์ชันอัปเดตรายชื่อผู้ใช้งาน
function updateUserList(users) {
  userListDiv.innerHTML = "<strong>Online Users</strong><hr />";
  users.forEach((u) => {
    const userDiv = document.createElement("div");
    userDiv.textContent = (u === username ? `⭐ ${u}` : u);
    userListDiv.appendChild(userDiv);
  });
}
