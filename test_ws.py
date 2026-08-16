import asyncio
import websockets
import json

async def test():
    uri = "ws://127.0.0.1:8000/api/stream"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"prompt": "Simulate incompressible flow over a circular cylinder at 2 m/s. Use a 2D domain. The cylinder radius is 0.05m.", "output_dir": "C:/Users/Administrator/Desktop/temp/TEST", "api_base": "", "model": "", "api_key": "", "max_loops": 3}))
        while True:
            msg = await ws.recv()
            print("WS RECV:", msg)
            data = json.loads(msg)
            if data.get("type") == "complete":
                break

asyncio.run(test())
