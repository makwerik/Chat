from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
import uuid
from manager import ConnectionManager
from collections import deque
from datetime import datetime

app = FastAPI()
manager = ConnectionManager()

# Предопределенные логин и пароль для администратора (замените на более безопасное решение)
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "admin"

# Хранение последних 10 сообщений
MAX_MESSAGES = 10
messages = deque(maxlen=MAX_MESSAGES)

# Эндпоинт для получения HTML страницы
@app.get("/")
async def get():
    with open('templates/chat.html', 'r', encoding='utf-8') as f:
        html = f.read()
    return HTMLResponse(html)

# Эндпоинт WebSocket для обработки соединений
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    username = ""  # Имя пользователя
    is_admin = False  # Флаг для проверки, является ли пользователь администратором
    try:
        await websocket.accept()  # Принятие соединения WebSocket
        data = await websocket.receive_text()  # Ожидание получения данных от клиента
        join_data = json.loads(data)  # Разбор данных из JSON

        if join_data['type'] == 'join':  # Проверка типа сообщения
            username = join_data['name']  # Получение имени пользователя
            if manager.is_name_taken(username):  # Проверка уникальности имени
                await websocket.send_text(json.dumps({"type": "error", "message": "name_taken"}))
                return
            manager.active_connections[username] = websocket  # Присоединение нового пользователя

            # Отправка последних 10 сообщений новому пользователю
            for message in messages:
                await websocket.send_text(json.dumps(message))

            await websocket.send_text(json.dumps({"type": "success", "message": "joined"}))
            await manager.broadcast(
                {"type": "message", "content": f"{username} присоединился к чату.", "id": str(uuid.uuid4()), "time": datetime.now().isoformat()})

        elif join_data['type'] == 'admin_login':
            # Проверка логина и пароля администратора
            if join_data['login'] == ADMIN_LOGIN and join_data['password'] == ADMIN_PASSWORD:
                username = 'admin'
                is_admin = True
                manager.active_connections[username] = websocket
                await websocket.send_text(json.dumps({"type": "success", "message": "admin_logged_in"}))
                await manager.broadcast(
                    {"type": "message", "content": "Администратор присоединился к чату.", "id": str(uuid.uuid4()), "time": datetime.now().isoformat()},
                    exclude_admin=True)
            else:
                await websocket.send_text(json.dumps({"type": "error", "message": "invalid_credentials"}))
                return

        while True:
            message_data = await websocket.receive_text()  # Ожидание получения нового сообщения
            data = json.loads(message_data)  # Разбор сообщения из JSON
            if data['type'] == 'message':
                if manager.is_user_blocked(data['name']):
                    await websocket.send_text(json.dumps({"type": "block"}))
                    continue  # Пропустить сообщения от заблокированных пользователей

                timestamp = datetime.now().isoformat()
                message = {
                    "type": "message",
                    "content": f"{data['name']}: {data['content']}",
                    "id": str(uuid.uuid4()),
                    "time": timestamp
                }
                messages.append(message)  # Сохранение сообщения
                await manager.broadcast(message)  # Рассылка сообщения всем пользователям

            elif data['type'] == 'delete' and is_admin:
                # Логика для удаления сообщения
                await manager.broadcast({"type": "delete", "messageId": data['messageId']})
            elif data['type'] == 'block' and is_admin:
                # Логика для блокировки пользователя
                manager.block_user(data['name'])
                await manager.broadcast({"type": "block", "name": data['name']}, exclude_admin=True)
    except WebSocketDisconnect:
        if username:
            manager.disconnect(username)  # Удаление пользователя из активных соединений при отключении
            await manager.broadcast({"type": "message", "content": f"{username} покинул чат.", "id": str(uuid.uuid4()), "time": datetime.now().isoformat()})
