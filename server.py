from aiohttp import web
import json
import os

connected_users = {}
chat_rooms = {"global": set()}

# -----------------------
# Send user list to all clients
# -----------------------
async def send_user_list():
    users = list(connected_users.values())
    payload = json.dumps({"type": "user_list", "users": users})

    for ws in connected_users:
        try:
            await ws.send_str(payload)
        except:
            pass

# -----------------------
# WebSocket Handler
# -----------------------
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Receive username
    username = await ws.receive_str()
    if username in connected_users.values():
        await ws.send_str(json.dumps({"type": "error", "message": "Username already exists"}))
        await ws.close()
        return ws

    # Register user
    connected_users[ws] = username
    chat_rooms["global"].add(ws)

    # Notify everyone
    await send_user_list()
    await broadcast("global", {"type": "system", "message": f"👋 {username} joined"})

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                msg_type = data.get("type")
                text = data.get("message")
                sender = connected_users[ws]

                # Global Chat
                if msg_type == "global":
                    await broadcast("global", {"type": "chat", "sender": sender, "room": "global", "message": text})

                # Private Chat
                elif msg_type == "private":
                    target = data["target"]
                    room = "_".join(sorted([sender, target]))
                    chat_rooms.setdefault(room, set())

                    for w, name in connected_users.items():
                        if name in [sender, target]:
                            chat_rooms[room].add(w)

                    await broadcast(room, {"type": "chat", "sender": sender, "room": room, "message": text})

                # Group Chat
                elif msg_type == "group":
                    room = data["room"]
                    chat_rooms.setdefault(room, set()).add(ws)

                    await broadcast(room, {"type": "chat", "sender": sender, "room": room, "message": text})

    except:
        pass

    finally:
        # Cleanup on disconnect
        username = connected_users.pop(ws, None)

        # Remove from all rooms
        for members in chat_rooms.values():
            members.discard(ws)

        # Notify everyone
        if username:
            await send_user_list()
            await broadcast("global", {"type": "system", "message": f"❌ {username} left"})

        return ws


# -----------------------
# Broadcast helper
# -----------------------
async def broadcast(room, data):
    remove = []
    for ws in chat_rooms.get(room, []):
        try:
            await ws.send_str(json.dumps(data))
        except:
            remove.append(ws)
    for ws in remove:
        chat_rooms[room].discard(ws)


# -----------------------
# HTTP server (serve client.html)
# -----------------------
async def index(request):
    return web.FileResponse("client.html")

async def js_file(request):
    return web.FileResponse("client.js")


# -----------------------
# Create App
# -----------------------
app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/client.js", js_file)
app.router.add_get("/ws", websocket_handler)

PORT = int(os.environ.get("PORT", 8080))
web.run_app(app, host="0.0.0.0", port=PORT)
