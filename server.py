# server.py
import asyncio
import websockets

# เก็บ client ที่เชื่อมต่อทั้งหมด
connected_clients = set()

# ฟังก์ชันหลักสำหรับจัดการแต่ละ client
async def handle_client(websocket):
    connected_clients.add(websocket)
    print(f"🔌 New client connected. Total clients: {len(connected_clients)}")

    try:
        async for message in websocket:
            print(f"📩 Received: {message}")
            # ส่งข้อความต่อให้ client อื่น ๆ
            for client in connected_clients:
                if client != websocket:
                    await client.send(message)
    except:
        print("⚠️  Client disconnected unexpectedly.")
    finally:
        connected_clients.remove(websocket)
        print(f"❌ Client disconnected. Total clients: {len(connected_clients)}")

# ฟังก์ชันเริ่มต้น server
async def main():
    async with websockets.serve(handle_client, "0.0.0.0", 5000):
        print("🚀 Server started on ws://localhost:5000")
        await asyncio.Future()  # รันค้างไว้ตลอดเวลา

if __name__ == "__main__":
    asyncio.run(main())
