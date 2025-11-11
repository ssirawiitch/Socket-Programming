# 💬 Real-Time Chat Application (Socket Programming)

A simple **real-time chat application** built using **Python** (WebSocket server) and **HTML/CSS/JavaScript** (client side).  
This project demonstrates the core concept of **Client–Server communication** through **TCP sockets** using the WebSocket protocol.

---

## 🧠 1. Project Summary

This project was developed for the **Computer Network Term Project – Socket Programming**.  
It demonstrates how a **Client–Server architecture** can be implemented to allow multiple users to chat with each other in **real time**.

- 🖥️ **Server:** Python with `asyncio` and `websockets`  
- 💬 **Client:** HTML, CSS, JavaScript (no frameworks)  
- 🔁 **Protocol:** WebSocket over TCP  
- ⚡ **Feature:** Real-time bidirectional messaging between multiple clients  

---

## ⚙️ 2. How It Works (Concept Overview)

1. The **Server** starts and listens on a TCP port (`5000`) for WebSocket connections.  
2. **Clients** (browsers) connect to the server using the WebSocket API.  
3. When one client sends a message:
   - The **Server** receives it and **broadcasts** it to all other connected clients.  
4. Every connected client receives and displays the message immediately — **no refresh required!**

💡 This mimics how modern real-time apps (e.g., **LINE**, **Discord**, **Slack**) communicate under the hood, but in a simplified educational setup.

---

## 🚀 3. How to Run the Project

### 🧩 Step 1: Create project folder
```bash
mkdir chat_project
cd chat_project
```

### 🧩 Step 2: Create 3 files inside this folder

- server.py
- clent.js
- client.html

### 🧩 Step 3: Install dependencies

Make sure you have Python 3.8+ installed, then run:

```
pip install websockets
```

### 🧩 Step 4: Run the server

```
python server.py
```
You should see:

```
🚀 Server started on ws://localhost:5000
```

### 🧩 Step 5: Run the client

เปิดอีกหน้าต่างใหม่แล้วรัน:

```bash
python -m http.server 8000
```

### 🧩 Step 6: ทดสอบการทำงาน

เปิด client.html ขึ้นมา 2 แท็บ (หรือ 2 เครื่องใน Wi-Fi เดียวกัน)
พิมพ์ข้อความในแท็บหนึ่ง → อีกแท็บจะเห็นข้อความแบบ Real-Time 💬
ถ้าจะหยุด server → กด Ctrl + C ใน terminal

