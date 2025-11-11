import asyncio
import websockets
import json  # ✅ ใช้สำหรับส่งข้อมูล list เป็น JSON

connected_users = {}  # websocket -> username

async def send_user_list():
    """ส่งรายชื่อผู้ใช้งานทั้งหมดให้ทุก client"""
    user_list = list(connected_users.values())
    data = json.dumps({"type": "user_list", "users": user_list})
    for client in connected_users:
        await client.send(data)

async def handle_client(websocket):
    try:
        username = await websocket.recv()
        print(f"🔌 New connection request from username: {username}")

        if username in connected_users.values():
            await websocket.send("❌ Username already exists. Please refresh and try again.")
            await websocket.close()
            return

        connected_users[websocket] = username
        print(f"✅ {username} joined the chat. Total users: {len(connected_users)}")

        # แจ้งทุกคนในห้องว่ามีคน join
        for client in connected_users:
            await client.send(f"📢 {username} has joined the chat!")

        # ✅ ส่งรายชื่อปัจจุบันให้ทุกคน
        await send_user_list()

        # รับข้อความปกติ
        async for message in websocket:
            sender = connected_users[websocket]
            print(f"💬 {sender}: {message}")
            for client in connected_users:
                if client != websocket:
                    await client.send(f"{sender}: {message}")

    except websockets.ConnectionClosed:
        pass
    finally:
        # เมื่อ client หลุด
        if websocket in connected_users:
            name = connected_users.pop(websocket)
            print(f"❌ {name} disconnected.")
            for client in connected_users:
                await client.send(f"🚪 {name} has left the chat.")
            # ✅ ส่งรายชื่อใหม่หลังจากออก
            await send_user_list()

async def main():
    try:
        async with websockets.serve(handle_client, "0.0.0.0", 5000):
            print("🚀 Server started on ws://localhost:5000")
            await asyncio.Future()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped manually. Bye!")

if __name__ == "__main__":
    asyncio.run(main())
