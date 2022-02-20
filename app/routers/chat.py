import logging
import aioredis
import asyncio

from aioredis.client import Redis, PubSub
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, status, WebSocket, WebSocketDisconnect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Room ID: <span id="ws-room-id"></span></h2>
        <h2>Your ID: <span id="ws-id"></span></h2>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="roomText" autocomplete="off"/>
            <button onclick="connect(event)">Connect</button>
            <hr>
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>

        </form>
        <ul id='messages'>
        </ul>
        <script>
            var client_id = Date.now()
            document.querySelector("#ws-id").textContent = client_id;
            var ws = null;

            function connect(event) {
                var room_id = document.getElementById('roomText').value;
                document.querySelector("#ws-room-id").textContent = room_id
                ws = new WebSocket(`ws://localhost/ws/${room_id}/${client_id}`);
                ws.onmessage = function(event) {
                    var messages = document.getElementById('messages')
                    var message = document.createElement('li')
                    var content = document.createTextNode(event.data)
                    message.appendChild(content)
                    messages.appendChild(message)
                };
                event.preventDefault()
            }
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
            function close(event) {
                ws.send("client " + client_id + " closed chat ")
                ws.close()
            }
        </script>
    </body>
</html>
"""


@router.get("/health-check", status_code=status.HTTP_200_OK)
def health_check():
    return "healthy"


@router.get("/")
async def get():
    return HTMLResponse(html)


@router.websocket("/ws/{room_id}/{client_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, client_id: int):
    await websocket.accept()
    await connection(websocket, room_id, client_id)


async def connection(websocket: WebSocket, room_id: str, client_id: int):
    async def consumer_handler(conn: Redis, ws: WebSocket):
        try:
            while True:
                message = await ws.receive_text()
                if message:
                    await conn.publish(room_id, f'[{room_id}]{client_id}: {message}')
        except WebSocketDisconnect:
            # TODO this needs handling better
            await conn.publish(room_id, f'Client [{room_id}]{client_id} left the chat')

    async def producer_handler(conn: Redis, pubsub: PubSub, ws: WebSocket):
        await pubsub.subscribe(room_id)
        await conn.publish(room_id, f'Client {client_id} joined the {room_id}')
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    await ws.send_text(message.get('data'))
        except Exception as exc:
            # TODO this needs handling better
            logger.error(f'{producer_handler.__name__} : {exc}')

    try:
        conn: Redis = await get_redis_pool()
    except Exception as e:
        print(e)

    pubsub: PubSub = conn.pubsub()

    producer_task = producer_handler(conn=conn, pubsub=pubsub, ws=websocket)
    consumer_task = consumer_handler(conn=conn, ws=websocket)
    done, pending = await asyncio.wait(
        [producer_task, consumer_task], return_when=asyncio.FIRST_EXCEPTION,
    )

    logger.debug(f"Done task: {done}")
    for task in pending:
        logger.debug(f"Canceling task: {task}")
        task.cancel()


async def get_redis_pool() -> Redis:
    return await aioredis.from_url(f'redis://redis', password='', encoding='utf-8', decode_responses=True)