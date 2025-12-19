from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        # Hàng chờ riêng cho từng loại bàn cờ
        self.queues = {9: [], 13: [], 19: []}
        # Lưu trận đấu đang diễn ra: {game_id: [ws_player1, ws_player2]}
        self.active_games = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        # Xóa khỏi hàng chờ nếu đang đợi
        for size in self.queues:
            if websocket in self.queues[size]:
                self.queues[size].remove(websocket)

    async def add_to_queue(self, websocket: WebSocket, size: int, user_info: dict):
        # Kiểm tra hàng chờ của size này có ai không
        if self.queues[size]:
            opponent_ws = self.queues[size].pop(0)
            game_id = f"online_{id(websocket)}"
            
            self.active_games[game_id] = [opponent_ws, websocket]
            
            # Opponent (người đợi trước) đi trước (Đen - 1)
            # Người mới vào đi sau (Trắng - 2)
            await opponent_ws.send_json({"type": "start", "game_id": game_id, "color": 1, "opponent": user_info})
            await websocket.send_json({"type": "start", "game_id": game_id, "color": 2, "opponent": "waiting_player"})
        else:
            self.queues[size].append(websocket)
            await websocket.send_json({"type": "waiting", "message": f"Đang tìm đối thủ bàn {size}x{size}..."})

    async def broadcast_move(self, game_id: str, move_data: dict, sender_ws: WebSocket):
        if game_id in self.active_games:
            for ws in self.active_games[game_id]:
                if ws != sender_ws:
                    await ws.send_json(move_data)

manager = ConnectionManager()