from fastapi import WebSocket
import json

class ConnectionManager:
    def __init__(self):
        # Хранение активных соединений и их имен
        self.active_connections: dict[str, WebSocket] = {}
        self.blocked_users: set[str] = set()

    # Добавление нового соединения
    async def connect(self, websocket: WebSocket, username: str):
        await websocket.accept()  # Принятие соединения
        self.active_connections[username] = websocket  # Сохранение соединения по имени пользователя

    # Удаление соединения при отключении
    def disconnect(self, username: str):
        if username in self.active_connections:
            del self.active_connections[username]  # Удаление из активных соединений

    # Отправка сообщения всем активным соединениям
    async def broadcast(self, message: dict, exclude_admin=False):
        for username, connection in self.active_connections.items():
            if exclude_admin and username == "admin":
                continue
            await connection.send_text(json.dumps(message))

    # Проверка, занято ли имя
    def is_name_taken(self, name: str) -> bool:
        return name in self.active_connections

    # Блокировка пользователя
    def block_user(self, name: str):
        self.blocked_users.add(name)

    # Проверка, заблокирован ли пользователь
    def is_user_blocked(self, name: str) -> bool:
        return name in self.blocked_users
