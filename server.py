from aiohttp import web
import json, os, random

connected_users = {}
chat_rooms = {"global": set()}
group_names = set(["global"])
anonymous_ids = {}
used_anonymous_ids = set()

def generate_anonymous_id():
    for _ in range(100):
        anon_id = random.randint(1000, 9999)
        if anon_id not in used_anonymous_ids:
            used_anonymous_ids.add(anon_id)
            return anon_id
    anon_id = random.randint(10000, 99999)
    used_anonymous_ids.add(anon_id)
    return anon_id

def release_anonymous_id(anon_id):
    if anon_id: used_anonymous_ids.discard(anon_id)

async def send_user_list():
    users = [{"name": info["name"], "avatar": info["avatar"]} for info in connected_users.values()]
    payload = json.dumps({"type": "user_list", "users": users})
    for ws in list(connected_users.keys()):
        try: await ws.send_str(payload)
        except: pass

async def send_group_list():
    groups = []
    for room in sorted(group_names):
        members = chat_rooms.get(room, set())
        member_names = [connected_users[m]["name"] for m in members if m in connected_users]
        groups.append({"name": room, "members": member_names, "kind": "group"})
    payload = json.dumps({"type": "group_list", "groups": groups})
    for ws in list(connected_users.keys()):
        try: await ws.send_str(payload)
        except: pass

async def broadcast(room, data):
    remove = []
    for ws in chat_rooms.get(room, []):
        try: await ws.send_str(json.dumps(data))
        except: remove.append(ws)
    for ws in remove:
        chat_rooms[room].discard(ws)

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    info = json.loads(await ws.receive_str())
    username = info["username"]
    avatar = info["avatar"]

    if username in [u["name"] for u in connected_users.values()]:
        await ws.send_str(json.dumps({"type":"error","message":"Username already exists"}))
        await ws.close()
        return ws

    connected_users[ws] = {"name": username, "avatar": avatar, "anonymous_id": None}
    chat_rooms["global"].add(ws)
    await send_user_list()
    await send_group_list()
    await broadcast("global", {"type":"system","message":f"👋 {username} joined"})

    try:
        async for msg in ws:
            if msg.type != web.WSMsgType.TEXT: continue
            data = json.loads(msg.data)
            msg_type = data.get("type")
            text = data.get("message")
            name = connected_users[ws]["name"]
            avatar_url = connected_users[ws]["avatar"]

            # Global chat
            if msg_type == "global":
                is_anonymous = data.get("anonymous", False)
                if is_anonymous:
                    if connected_users[ws]["anonymous_id"] is None:
                        anon_id = generate_anonymous_id()
                        connected_users[ws]["anonymous_id"] = anon_id
                        anonymous_ids[ws] = anon_id
                    else: anon_id = connected_users[ws]["anonymous_id"]
                    sender_name = f"Anonymous #{anon_id}"
                    # Use a generic avatar for anonymous users (use avatar1 as placeholder)
                    sender_avatar = "/images/avatar1.jpg"
                else:
                    sender_name = name
                    sender_avatar = avatar_url

                await broadcast("global", {
                    "type":"chat","sender":sender_name,"sender_avatar":sender_avatar,
                    "room":"global","message":text,"is_anonymous":is_anonymous,
                    "original_sender": name
                })

            # Private
            elif msg_type == "private":
                target = data["target"]
                room = "_".join(sorted([name, target]))
                chat_rooms.setdefault(room, set())
                for w, info_user in connected_users.items():
                    if info_user["name"] in [name, target]:
                        chat_rooms[room].add(w)
                await broadcast(room, {"type":"chat","sender":name,"sender_avatar":avatar_url,"room":room,"message":text})

            # Group
            elif msg_type == "group":
                room = data.get("room")
                if not room: continue
                members = chat_rooms.get(room, set())
                if ws not in members:
                    try: await ws.send_str(json.dumps({"type":"error","message":f"Join '{room}' first"}))
                    except: pass
                    continue
                await broadcast(room, {"type":"chat","sender":name,"sender_avatar":avatar_url,"room":room,"message":text})

            # Create group
            elif msg_type == "create_group":
                room = data.get("room")
                if not room: continue
                if room in chat_rooms: continue
                if "_" in room: continue
                chat_rooms[room] = set([ws])
                group_names.add(room)
                await send_group_list()
                try: await ws.send_str(json.dumps({"type":"system","message":f"✅ Group '{room}' created"}))
                except: pass

            # Join group
            elif msg_type == "join_group":
                room = data.get("room")
                if not room: continue
                if room not in chat_rooms: continue
                chat_rooms[room].add(ws)
                await send_group_list()
                try: await ws.send_str(json.dumps({"type":"system","message":f"✅ Joined '{room}'"}))
                except: pass

            # Leave group
            elif msg_type == "leave_group":
                room = data.get("room")
                if not room: continue
                chat_rooms.get(room,set()).discard(ws)
                await send_group_list()
                try: await ws.send_str(json.dumps({"type":"system","message":f"Left '{room}'"}))
                except: pass

            # Delete group
            elif msg_type == "delete_group":
                room = data.get("room")
                if not room: continue
                if room in chat_rooms:
                    del chat_rooms[room]
                    group_names.discard(room)
                    await send_group_list()
                    try: await ws.send_str(json.dumps({"type":"system","message":f"✅ Group '{room}' deleted"}))
                    except: pass

    finally:
        user_info = connected_users.pop(ws, None)
        if user_info and user_info.get("anonymous_id"):
            release_anonymous_id(user_info["anonymous_id"])
            anonymous_ids.pop(ws, None)
        for members in chat_rooms.values():
            members.discard(ws)
        empty_groups = [room for room in chat_rooms if room in group_names and room != "global" and len(chat_rooms[room])==0]
        for room in empty_groups:
            del chat_rooms[room]
            group_names.discard(room)
        if user_info:
            await send_user_list()
            await send_group_list()
            await broadcast("global", {"type":"system","message":f"❌ {user_info['name']} left"})
    return ws

async def index(request): return web.FileResponse("client.html")
async def js_file(request): return web.FileResponse("client.js")

app = web.Application()
app.router.add_static("/images", path=os.path.join(os.path.dirname(__file__), "images"), show_index=False)
app.router.add_get("/", index)
app.router.add_get("/client.js", js_file)
app.router.add_get("/ws", websocket_handler)

PORT = int(os.environ.get("PORT", 8080))
web.run_app(app, host="0.0.0.0", port=PORT)
