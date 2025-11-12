import asyncio
import websockets
import json

connected_users = {}       # websocket -> username
chat_rooms = {"global": set()}  # room_name -> set(websocket)

async def broadcast_to_room(room_name, data):
    """ส่งข้อความถึงทุกคนในห้อง"""
    for ws in chat_rooms.get(room_name, set()):
        try:
            await ws.send(json.dumps(data))
        except:
            pass

async def send_user_list():
    """อัปเดตชื่อผู้ใช้ทั้งหมด"""
    users = list(connected_users.values())
    msg = json.dumps({"type": "user_list", "users": users})
    for ws in connected_users:
        await ws.send(msg)

async def handle_client(websocket):
    try:
        # รับ username
        username = await websocket.recv()
        if username in connected_users.values():
            await websocket.send(json.dumps({"type": "error", "message": "Username already exists"}))
            await websocket.close()
            return

        connected_users[websocket] = username
        chat_rooms["global"].add(websocket)
        print(f"✅ {username} connected")

        await send_user_list()
        await broadcast_to_room("global", {"type": "system", "message": f"👋 {username} joined the global chat"})

        # วนรับข้อความจาก client
        while True:
            data = await websocket.recv()
            msg = json.loads(data)
            sender = connected_users[websocket]

            msg_type = msg.get("type")
            text = msg.get("message")

            if msg_type == "global":
                await broadcast_to_room("global", {"type": "chat", "room": "global", "sender": sender, "message": text})

            elif msg_type == "private":
                target = msg.get("target")
                room_name = "_".join(sorted([sender, target]))
                chat_rooms.setdefault(room_name, set()).update([
                    ws for ws, name in connected_users.items() if name in [sender, target]
                ])
                await broadcast_to_room(room_name, {"type": "chat", "room": room_name, "sender": sender, "message": text})

            elif msg_type == "group":
                room = msg.get("room")
                chat_rooms.setdefault(room, set()).add(websocket)
                await broadcast_to_room(room, {"type": "chat", "room": room, "sender": sender, "message": text})

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if websocket in connected_users:
            user = connected_users.pop(websocket)
            print(f"❌ {user} disconnected")
            for members in chat_rooms.values():
                members.discard(websocket)
            await send_user_list()
            await broadcast_to_room("global", {"type": "system", "message": f"❌ {user} left the chat"})

async def main():
    async with websockets.serve(handle_client, "0.0.0.0", 6789):
        print("🚀 Server running on ws://localhost:6789")
        await asyncio.Future()

asyncio.run(main())
