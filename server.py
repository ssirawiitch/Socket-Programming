from aiohttp import web
import json
import os
import uuid

connected_users = {}
chat_rooms = {"global": set()}   # room_name -> set of ws
# map message_id -> metadata {"owner_ws": ws, "room": room}
message_store = {}
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
                    # assign a stable id so messages can be unsent
                    msg_id = uuid.uuid4().hex
                    message_store[msg_id] = {"owner_ws": ws, "room": "global"}

                    # ตรวจ anonymous จาก client
                    is_anon = data.get("anonymous", False)

                    if is_anon:
                        # สร้าง anonymous id ถ้ายังไม่มี
                        if "anon_id" not in connected_users[ws]:
                            connected_users[ws]["anon_id"] = uuid.uuid4().hex[:4]  # 4 ตัว

                        anon_name = f"Anonymous #{connected_users[ws]['anon_id']}"
                        anon_avatar = "/images/ano.jpg"  

                        sender_name = anon_name
                        sender_avatar = anon_avatar

                    else:
                        # ชื่อจริง
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


                # PRIVATE
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

                    # assign id and store ownership like other message types
                    msg_id = uuid.uuid4().hex
                    message_store[msg_id] = {"owner_ws": ws, "room": room}
                    await broadcast(room, {
                        "type": "chat",
                        "message_id": msg_id,
                        "sender": name,
                        "sender_avatar": avatar_url,
                        "room": room,
                        "message": text
                    })    

                # UNSEND / DELETE message
                elif msg_type == "delete":
                    message_id = data.get("message_id")
                    if not message_id:
                        try:
                            await ws.send_str(json.dumps({"type": "error", "message": "message_id required"}))
                        except Exception:
                            pass
                        continue

                    meta = message_store.get(message_id)
                    if not meta:
                        try:
                            await ws.send_str(json.dumps({"type": "error", "message": "Message not found or already deleted"}))
                        except Exception:
                            pass
                        continue

                    # only original sender may delete
                    if meta.get("owner_ws") != ws:
                        try:
                            await ws.send_str(json.dumps({"type": "error", "message": "You can only delete your own messages"}))
                        except Exception:
                            pass
                        continue

                    room = meta.get("room")
                    # broadcast delete event to the room
                    await broadcast(room, {"type": "delete", "room": room, "message_id": message_id})
                    # remove from store
                    try:
                        del message_store[message_id]
                    except KeyError:
                        pass

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
        # remove any stored messages owned by this ws
        for mid in list(message_store.keys()):
            meta = message_store.get(mid)
            if meta and meta.get("owner_ws") == ws:
                try:
                    del message_store[mid]
                except KeyError:
                    pass
        
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
# app.router.add_static("/", path=os.path.join(os.path.dirname(__file__)), show_index=False)
# but keep your existing explicit routes if you like


app.router.add_get("/", index)
app.router.add_get("/client.js", js_file)
app.router.add_get("/ws", websocket_handler)

PORT = int(os.environ.get("PORT", 8080))
web.run_app(app, host="0.0.0.0", port=PORT)