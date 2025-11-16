from aiohttp import web
import json
import os
import uuid
import random

connected_users = {}
chat_rooms = {"global": set()}
message_store = {}
group_names = set(["global"])

# ---------------------------
# Anonymous support
# ---------------------------
used_anon_ids = set()

def get_anonymous_id():
    while True:
        num = random.randint(1000, 9999)
        if num not in used_anon_ids:
            used_anon_ids.add(num)
            return num

def release_anonymous_id(num):
    used_anon_ids.discard(num)

# ---------------------------
# Send Lists
# ---------------------------
async def send_user_list():
    users = [
        {"name": info["name"], "avatar": info["avatar"]}
        for info in connected_users.values()
    ]
    payload = json.dumps({"type": "user_list", "users": users})
    for ws in list(connected_users.keys()):
        try:
            await ws.send_str(payload)
        except:
            pass

async def send_group_list():
    groups = []
    for room in sorted(group_names):
        members = chat_rooms.get(room, set())
        member_names = [
            connected_users[m]["name"]
            for m in members if m in connected_users
        ]
        groups.append({
            "name": room,
            "members": member_names,
            "kind": "group"
        })
    payload = json.dumps({"type": "group_list", "groups": groups})
    for ws in list(connected_users.keys()):
        try:
            await ws.send_str(payload)
        except:
            pass

async def broadcast(room, data):
    remove = []
    for ws in chat_rooms.get(room, []):
        try:
            await ws.send_str(json.dumps(data))
        except:
            remove.append(ws)
    for ws in remove:
        chat_rooms[room].discard(ws)

# ---------------------------
# Websocket Handler
# ---------------------------
async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    info = json.loads(await ws.receive_str())
    username = info["username"]
    avatar = info["avatar"]

    # check duplicate username
    if username in [u["name"] for u in connected_users.values()]:
        await ws.send_str(json.dumps({
            "type": "error",
            "message": "Username already exists"
        }))
        await ws.close()
        return ws

    # assign user data + anonymous id
    anon_id = get_anonymous_id()
    connected_users[ws] = {
        "name": username,
        "avatar": avatar,
        "anonymous_id": anon_id
    }

    chat_rooms["global"].add(ws)
    await send_user_list()
    await send_group_list()
    await broadcast("global", {
        "type": "system",
        "message": f"👋 {username} joined"
    })

    try:
        async for msg in ws:

            if msg.type != web.WSMsgType.TEXT:
                continue

            data = json.loads(msg.data)
            msg_type = data.get("type")
            text = data.get("message")
            name = connected_users[ws]["name"]
            avatar_url = connected_users[ws]["avatar"]

            # -----------------------
            # Global chat (with anonymous)
            # -----------------------
            if msg_type == "global":
                msg_id = uuid.uuid4().hex
                message_store[msg_id] = {"owner_ws": ws, "room": "global"}

                is_anon = data.get("anonymous", False)

                if is_anon:
                    sender_name = f"Anonymous #{connected_users[ws]['anonymous_id']}"
                    sender_avatar = "/images/anonymous.png"  # ใส่รูปเองได้
                else:
                    sender_name = name
                    sender_avatar = avatar_url

                await broadcast("global", {
                    "type": "chat",
                    "message_id": msg_id,
                    "sender": sender_name,
                    "sender_avatar": sender_avatar,
                    "original_sender": name,
                    "is_anonymous": is_anon,
                    "room": "global",
                    "message": text
                })

            # -----------------------
            # Private chat
            # -----------------------
            elif msg_type == "private":
                target = data["target"]
                room = "_".join(sorted([name, target]))
                chat_rooms.setdefault(room, set())

                for w, info_user in connected_users.items():
                    if info_user["name"] in [name, target]:
                        chat_rooms[room].add(w)

                msg_id = uuid.uuid4().hex
                message_store[msg_id] = {"owner_ws": ws, "room": room}

                await broadcast(room, {
                    "type": "chat",
                    "message_id": msg_id,
                    "sender": name,
                    "sender_avatar": avatar_url,
                    "original_sender": name,
                    "is_anonymous": False,
                    "room": room,
                    "message": text
                })

            # -----------------------
            # Group chat
            # -----------------------
            elif msg_type == "group":
                room = data.get("room")
                if not room:
                    continue
                members = chat_rooms.get(room, set())
                if ws not in members:
                    try:
                        await ws.send_str(json.dumps({
                            "type": "error",
                            "message": f"You are not a member of group '{room}'"
                        }))
                    except:
                        pass
                    continue

                msg_id = uuid.uuid4().hex
                message_store[msg_id] = {"owner_ws": ws, "room": room}

                await broadcast(room, {
                    "type": "chat",
                    "message_id": msg_id,
                    "sender": name,
                    "sender_avatar": avatar_url,
                    "original_sender": name,
                    "is_anonymous": False,
                    "room": room,
                    "message": text
                })

            # -----------------------
            # Delete / Unsend
            # -----------------------
            elif msg_type == "delete":
                message_id = data.get("message_id")
                meta = message_store.get(message_id)

                if not meta:
                    await ws.send_str(json.dumps({
                        "type": "error",
                        "message": "Message not found"
                    }))
                    continue

                if meta["owner_ws"] != ws:
                    await ws.send_str(json.dumps({
                        "type": "error",
                        "message": "You can only delete your own messages"
                    }))
                    continue

                room = meta["room"]

                await broadcast(room, {
                    "type": "delete",
                    "room": room,
                    "message_id": message_id
                })
                del message_store[message_id]

            # -----------------------
            # Create group
            # -----------------------
            elif msg_type == "create_group":
                room = data.get("room")
                if not room:
                    await ws.send_str(json.dumps({
                        "type": "error",
                        "message": "Group name required"
                    }))
                    continue

                if room in chat_rooms:
                    await ws.send_str(json.dumps({
                        "type": "error",
                        "message": "Group already exists"
                    }))
                    continue

                chat_rooms[room] = set([ws])
                group_names.add(room)
                await send_group_list()

            # Join group
            elif msg_type == "join_group":
                room = data.get("room")
                if room and room in chat_rooms:
                    chat_rooms[room].add(ws)
                    await send_group_list()

            # Leave group
            elif msg_type == "leave_group":
                room = data.get("room")
                if room in chat_rooms:
                    chat_rooms[room].discard(ws)
                    await send_group_list()

            # Delete group
            elif msg_type == "delete_group":
                room = data.get("room")
                if room in chat_rooms:
                    del chat_rooms[room]
                    group_names.discard(room)
                    await send_group_list()

    # ---------------------------
    # User disconnected
    # ---------------------------
    finally:
        user_info = connected_users.pop(ws, None)
        if user_info:
            release_anonymous_id(user_info["anonymous_id"])

        for members in chat_rooms.values():
            members.discard(ws)

        # remove user's messages
        for mid in list(message_store.keys()):
            meta = message_store[mid]
            if meta["owner_ws"] == ws:
                del message_store[mid]

        await send_user_list()
        await send_group_list()

        if user_info:
            await broadcast("global", {
                "type": "system",
                "message": f"❌ {user_info['name']} left"
            })

    return ws


async def index(request):
    return web.FileResponse("client.html")

async def js_file(request):
    return web.FileResponse("client.js")


app = web.Application()
app.router.add_static("/images",
    path=os.path.join(os.path.dirname(__file__), "images"),
    show_index=False,
)
app.router.add_get("/", index)
app.router.add_get("/client.js", js_file)
app.router.add_get("/ws", websocket_handler)

PORT = int(os.environ.get("PORT", 8080))
web.run_app(app, host="0.0.0.0", port=PORT)
