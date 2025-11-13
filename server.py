import asyncio
import websockets
import json
import os
import http.server
import socketserver
import threading

# -----------------------------
# HTTP SERVER (serve client.html)
# -----------------------------

PORT = int(os.environ.get("PORT", 10000))   # Render sets $PORT dynamically

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        return  # hide http logs

def start_http_server():
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"🌐 HTTP server serving on port {PORT}")
        httpd.serve_forever()

# Start HTTP server on separate thread
threading.Thread(target=start_http_server, daemon=True).start()


# -----------------------------
# WEBSOCKET SERVER
# -----------------------------

connected_users = {}
chat_rooms = {"global": set()}

async def broadcast(room, data):
    for ws in chat_rooms.get(room, []):
        try:
            await ws.send(json.dumps(data))
        except:
            pass

async def handle_client(websocket):
    try:
        username = await websocket.recv()

        if username in connected_users.values():
            await websocket.send(json.dumps({"type": "error", "message": "Username already exists"}))
            await websocket.close()
            return

        connected_users[websocket] = username
        chat_rooms["global"].add(websocket)

        await broadcast("global", {"type": "system", "message": f"👋 {username} joined"})
        
        while True:
            msg = json.loads(await websocket.recv())
            mtype = msg.get("type")
            text = msg.get("message")

            sender = connected_users[websocket]

            # Global
            if mtype == "global":
                await broadcast("global", {"type": "chat", "sender": sender, "room": "global", "message": text})

            # Private
            elif mtype == "private":
                target = msg["target"]
                room = "_".join(sorted([sender, target]))
                chat_rooms.setdefault(room, set())

                for ws, nm in connected_users.items():
                    if nm in [sender, target]:
                        chat_rooms[room].add(ws)

                await broadcast(room, {"type": "chat", "room": room, "sender": sender, "message": text})

            # Group
            elif mtype == "group":
                room = msg["room"]
                chat_rooms.setdefault(room, set()).add(websocket)
                await broadcast(room, {"type": "chat", "room": room, "sender": sender, "message": text})

    except:
        pass

async def main():
    async with websockets.serve(
        handle_client,
        "0.0.0.0",
        PORT,
        ping_interval=None,
    ):
        print(f"🔌 WebSocket server running on port {PORT}")
        await asyncio.Future()

asyncio.run(main())