from aiohttp import web
import json
import os

connected_users = {}
chat_rooms = {"global": set()}   # room_name -> set of ws
group_names = set(["global"])    # only rooms in this set are real groups shown to clients


# -----------------------
# Send user list
# -----------------------
async def send_user_list():
    users = [{"name": info["name"], "avatar": info["avatar"]} for info in connected_users.values()]
    payload = json.dumps({"type": "user_list", "users": users})

    for ws in list(connected_users.keys()):
        try:
            await ws.send_str(payload)
        except:
            pass

# -----------------------
# Send group list
# -----------------------
async def send_group_list():
    """Broadcast the list of groups (only real groups) and their member names to all clients.

    We intentionally only use `group_names` as the authoritative source of groups.
    As a defensive measure, skip any name that looks like a private-room (contains '_'
    and both sides look like usernames) unless you intentionally named a group with '_'.
    """
    groups = []
    for room in sorted(group_names):
        # Defensive: skip any room that looks like a private one-to-one room.
        # This is optional if you allow underscores in real group names — remove if needed.

        members = chat_rooms.get(room, set())
        member_names = [connected_users[m]["name"] for m in members if m in connected_users]
        groups.append({"name": room, "members": member_names, "kind": "group"})

    payload = json.dumps({"type": "group_list", "groups": groups})
    for ws in list(connected_users.keys()):
        try:
            await ws.send_str(payload)
        except Exception:
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
    await send_group_list()
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

                # GROUP: sending a chat message to a group (must be member)
                elif msg_type == "group":
                    room = data.get("room")
                    if not room:
                        continue

                    #Ensure group exists and sender is one of the group member
                    members = chat_rooms.get(room, set())
                    if ws not in members:
                        #notify sender that they must join first
                        try:
                            await ws.send_str(json.dumps({
                                "type": "error",
                                "message": f"You are not a member of group '{room}'. Join the group to send messages!"
                            }))
                        except Exception:
                            pass
                        continue

                    await broadcast(room, {
                        "type": "chat",
                        "sender": name,
                        "sender_avatar": avatar_url,
                        "room": room,
                        "message": text
                    })    

                # CREATE GROUP (R8)
                elif msg_type == "create_group":
                    room = data.get("room")
                    if not room:
                        try:
                            await ws.send_str(json.dumps({"type": "error", "message": "Group name is required"}))
                        except Exception:
                            pass
                        continue

                    if room in chat_rooms:
                        try:
                            await ws.send_str(json.dumps({"type": "error", "message": f"Group '{room}' already exists"}))
                        except Exception:
                            pass
                        continue
                    if "_" in room:
                        try:
                            await ws.send_str(json.dumps({"type": "error", "message": "Group name cannot contain underscore '_'"}))
                        except Exception:
                            pass
                        continue

                    # create group with creator as sole member
                    chat_rooms[room] = set([ws])
                    group_names.add(room)
                    await send_group_list()
                    try:
                        await ws.send_str(json.dumps({"type": "system", "message": f"✅ Group '{room}' created"}))
                    except Exception:
                        pass

                # JOIN GROUP (R10)
                elif msg_type == "join_group":
                    room = data.get("room")
                    if not room:
                        continue
                    if room not in chat_rooms:
                        try:
                            await ws.send_str(json.dumps({"type": "error", "message": f"Group '{room}' does not exist"}))
                        except Exception:
                            pass
                        continue

                    chat_rooms[room].add(ws)
                    await send_group_list()
                    try:
                        await ws.send_str(json.dumps({"type": "system", "message": f"✅ Joined group '{room}'"}))
                    except Exception:
                        pass

                # optional: leave group
                elif msg_type == "leave_group":
                    room = data.get("room")
                    if not room:
                        continue
                    if room in chat_rooms:
                        chat_rooms[room].discard(ws)
                        await send_group_list()
                        try:
                            await ws.send_str(json.dumps({"type": "system", "message": f"Left group '{room}'"}))
                        except Exception:
                            pass
                # delete group
                elif msg_type == "delete_group":
                    room = data.get("room")
                    if not room:
                        try:
                            await ws.send_str(json.dumps({"type": "error", "message": "No Group Selected"}))
                        except Exception:
                            pass
                        continue
                    #delete this group
                    del chat_rooms[room]
                    group_names.discard(room)
                    await send_group_list()
                    try:
                        await ws.send_str(json.dumps({"type": "system", "message": f"✅ Group '{room}' deleted"}))
                    except Exception:
                        pass


    except:
        pass

    finally:
        # ลบ user ออกจากระบบเมื่อหลุด
        user_info = connected_users.pop(ws, None)

        for members in chat_rooms.values():
            members.discard(ws)
        
        # After: for members in chat_rooms.values(): members.discard(ws)

        # Auto-delete any group that becomes empty
        empty_groups = []
        for room in list(chat_rooms.keys()):
            if room in group_names and room != "global":
                if len(chat_rooms[room]) == 0:
                    empty_groups.append(room)

        for room in empty_groups:
            del chat_rooms[room]
            group_names.discard(room)

        if empty_groups:
            await send_group_list()

        if user_info:
            await send_user_list()
            await send_group_list()
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

# serve static files from ./images at URL path /images
app.router.add_static("/images", path=os.path.join(os.path.dirname(__file__), "images"), show_index=False)

# you can also serve client.html & client.js via static if you prefer:
app.router.add_static("/", path=os.path.join(os.path.dirname(__file__)), show_index=False)
# but keep your existing explicit routes if you like


app.router.add_get("/", index)
app.router.add_get("/client.js", js_file)
app.router.add_get("/ws", websocket_handler)

PORT = int(os.environ.get("PORT", 8081))
web.run_app(app, host="0.0.0.0", port=PORT)
