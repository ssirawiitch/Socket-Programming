// client.js

// สร้างการเชื่อมต่อ WebSocket ไปยัง server (port 5000)
const ws = new WebSocket("ws://localhost:5000");

// ดึง element ในหน้า HTML
const messagesDiv = document.getElementById("messages");
const input = document.getElementById("msgInput");

// เมื่อเชื่อมต่อสำเร็จ
ws.onopen = () => {
  const msg = document.createElement("div");
  msg.textContent = "✅ Connected to server";
  msg.style.color = "green";
  messagesDiv.appendChild(msg);
};

// เมื่อได้รับข้อความใหม่จาก server
ws.onmessage = (event) => {
  const msg = document.createElement("div");
  msg.textContent = "👤 " + event.data;
  messagesDiv.appendChild(msg);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
};

// ฟังก์ชันส่งข้อความ
function sendMessage() {
  const text = input.value.trim();
  if (text) {
    ws.send(text);
    const msg = document.createElement("div");
    msg.textContent = "🧍‍♂️ You: " + text;
    msg.style.fontWeight = "bold";
    messagesDiv.appendChild(msg);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    input.value = "";
  }
}

// เมื่อการเชื่อมต่อถูกปิด
ws.onclose = () => {
  const msg = document.createElement("div");
  msg.textContent = "❌ Disconnected from server";
  msg.style.color = "red";
  messagesDiv.appendChild(msg);
};
