from aiohttp import web
import json
import os

connected_users = {}
chat_rooms = {"global": set()}

# -----------------------
# Send user list
# -----------------------
async def send_user_list():
    users = [info["name"] for info in connected_users.values()]
    payload = json.dumps({"type": "user_list", "users": users})

    for ws in list(connected_users.keys()):
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

    # รับ JSON จาก client: { "username": "...", "avatar": "..." }
    info = json.loads(await ws.receive_str())
    username = info["username"]
    avatar = info["avatar"]

    # กันชื่อซ้ำ
    if username in [u["name"] for u in connected_users.values()]:
        await ws.send_str(json.dumps({"type": "error", "message": "Username already exists"}))
        await ws.close()
        return ws

    # เก็บข้อมูล user
    connected_users[ws] = {"name": username, "avatar": avatar}
    chat_rooms["global"].add(ws)

    # อัพเดทรายชื่อ + ส่งข้อความ system
    await send_user_list()
    await broadcast("global", {
        "type": "system",
        "message": f"👋 {username} joined"
    })

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                data = json.loads(msg.data)
                msg_type = data.get("type")
                text = data.get("message")

                name = connected_users[ws]["name"]
                avatar_url = connected_users[ws]["avatar"]

                # GLOBAL
                if msg_type == "global":
                    await broadcast("global", {
                        "type": "chat",
                        "sender": name,
                        "sender_avatar": avatar_url,
                        "room": "global",
                        "message": text
                    })

                # PRIVATE
                elif msg_type == "private":
                    target = data["target"]
                    room = "_".join(sorted([name, target]))
                    chat_rooms.setdefault(room, set())

                    for w, info_user in connected_users.items():
                        if info_user["name"] in [name, target]:
                            chat_rooms[room].add(w)

                    await broadcast(room, {
                        "type": "chat",
                        "sender": name,
                        "sender_avatar": avatar_url,
                        "room": room,
                        "message": text
                    })

                # GROUP
                elif msg_type == "group":
                    room = data["room"]
                    chat_rooms.setdefault(room, set()).add(ws)

                    await broadcast(room, {
                        "type": "chat",
                        "sender": name,
                        "sender_avatar": avatar_url,
                        "room": room,
                        "message": text
                    })

    except:
        pass

    finally:
        # ลบ user ออกจากระบบเมื่อหลุด
        user_info = connected_users.pop(ws, None)

        for members in chat_rooms.values():
            members.discard(ws)

        if user_info:
            await send_user_list()
            await broadcast("global", {
                "type": "system",
                "message": f"❌ {user_info['name']} left"
            })

        return ws

# -----------------------
# Broadcast
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
# HTTP
# -----------------------
async def index(request):
    return web.FileResponse("client.html")

async def js_file(request):
    return web.FileResponse("client.js")

app = web.Application()
app.router.add_get("/", index)
app.router.add_get("/client.js", js_file)
app.router.add_get("/ws", websocket_handler)

PORT = int(os.environ.get("PORT", 8080))
web.run_app(app, host="0.0.0.0", port=PORT)
