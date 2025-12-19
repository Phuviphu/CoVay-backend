from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.models_db import create_tables, SessionLocal, User
from app.game_logic.board import GoBoard
from app.game_logic.ai import AIPlayer
from app.auth_utils import get_password_hash, verify_password, create_access_token
from app.socket_manager import manager
from app.ranking_logic import calculate_elo_change, get_rank_title

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- MODELS ---
class UserReg(BaseModel): username: str; password: str; email: str
class UserLog(BaseModel): username: str; password: str
class MoveReq(BaseModel): row: int; col: int; player: int
class AIMoveReq(BaseModel): difficulty: str = "hard"
class FinishReq(BaseModel): winner_color: int; difficulty: str; opponent_elo: int = 1000
# [MỚI] Model đổi mật khẩu
class ChangePassReq(BaseModel): username: str; old_password: str; new_password: str

games = {} 

@app.on_event("startup")
def startup(): create_tables()

# --- AUTH & USER ---
@app.post("/auth/register")
def register(u: UserReg, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == u.username).first(): raise HTTPException(400, "User tồn tại")
    new_user = User(username=u.username, hashed_password=get_password_hash(u.password), email=u.email, elo=1000)
    db.add(new_user); db.commit()
    return {"msg": "OK"}

@app.post("/auth/login")
def login(u: UserLog, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == u.username).first()
    if not user or not verify_password(u.password, user.hashed_password): raise HTTPException(400, "Fail")
    return {"access_token": create_access_token({"sub": user.username}), "username": user.username, "elo": user.elo, "rank": get_rank_title(user.elo)}

# [MỚI] API ĐỔI MẬT KHẨU
@app.post("/users/change_password")
def change_password(req: ChangePassReq, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user: raise HTTPException(404, "User not found")
    
    if not verify_password(req.old_password, user.hashed_password):
        raise HTTPException(400, "Mật khẩu cũ không đúng")
    
    user.hashed_password = get_password_hash(req.new_password)
    db.commit()
    return {"msg": "Đổi mật khẩu thành công!"}

@app.get("/users/{username}")
def profile(username: str, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == username).first()
    if not u: raise HTTPException(404)
    return {"username": u.username, "email": u.email, "elo": u.elo, "rank": get_rank_title(u.elo), "wins": u.wins, "losses": u.losses, "streak": u.current_streak}

# --- GAME LOGIC (GIỮ NGUYÊN NHƯ CŨ) ---
@app.post("/game/new/{size}")
def new_game(size: int):
    gid = "game_local"; games[gid] = GoBoard(size=size)
    return {"game_id": gid}

@app.post("/game/{gid}/move")
def move(gid: str, m: MoveReq):
    if gid not in games: raise HTTPException(404)
    board = games[gid]
    suc, msg = board.make_move(m.row, m.col, m.player)
    return {"msg": msg, "grid": board.grid, "captured": {"black": board.captured_black, "white": board.captured_white}, "game_over": False}

@app.post("/game/{gid}/ai_move")
def ai_move(gid: str, req: AIMoveReq):
    board = games.get(gid)
    if not board: raise HTTPException(404)
    ai = AIPlayer(board.size, req.difficulty)
    mv = ai.get_best_move(board, 2)
    if not mv:
        is_over, msg = board.pass_turn()
        if is_over:
            b, w = board.calculate_score()
            return {"msg": "AI Bỏ lượt. Kết thúc!", "grid": board.grid, "game_over": True, "score": {"black": b, "white": w}}
        return {"msg": "AI Pass", "grid": board.grid, "game_over": False}
    board.make_move(mv[0], mv[1], 2)
    return {"msg": "AI Move", "move": {"row": mv[0], "col": mv[1]}, "grid": board.grid}

@app.post("/game/{gid}/pass")
def pass_turn(gid: str):
    if gid not in games: raise HTTPException(404)
    board = games[gid]
    is_over, msg = board.pass_turn()
    if is_over:
        b, w = board.calculate_score()
        return {"msg": msg, "grid": board.grid, "game_over": True, "score": {"black": b, "white": w}}
    return {"msg": "Bạn đã Pass", "grid": board.grid, "game_over": False}

@app.post("/game/{gid}/hint")
def get_hint(gid: str, req: MoveReq):
    board = games.get(gid)
    if not board: return {"move": None}
    ai = AIPlayer(board.size, "hard")
    mv = ai.get_best_move(board, req.player)
    return {"move": mv} 

@app.post("/game/{gid}/undo")
def undo_move(gid: str):
    if gid not in games: raise HTTPException(404)
    board = games[gid]; board.undo_round()
    return {"msg": "Undo", "grid": board.grid}

@app.post("/users/{username}/finish")
def finish(username: str, req: FinishReq, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.username == username).first()
    if not u: raise HTTPException(404)
    
    is_win = (req.winner_color == 1)
    is_online = (req.difficulty == "online")
    if is_win:
        u.current_streak = u.current_streak + 1 if u.current_streak > 0 else 1
        u.wins += 1
    else:
        u.current_streak = u.current_streak - 1 if u.current_streak < 0 else -1
        u.losses += 1
    gain, loss = calculate_elo_change(u.elo if is_win else req.opponent_elo, req.opponent_elo if is_win else u.elo, req.difficulty, u.current_streak if is_win else 0, u.current_streak if not is_win else 0, is_online)
    delta = gain if is_win else -loss
    u.elo = max(0, u.elo + delta)
    db.commit()
    return {"new_elo": u.elo, "delta": delta, "rank": get_rank_title(u.elo)}

@app.get("/leaderboard")
def leaderboard(db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.elo.desc()).limit(50).all()
    return [{"username": u.username, "elo": u.elo, "rank": get_rank_title(u.elo)} for u in users]

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            if data['type'] == 'find_match': await manager.add_to_queue(websocket, data['size'], data['user'])
            elif data['type'] == 'move': await manager.broadcast_move(data['game_id'], data, websocket)
    except WebSocketDisconnect: manager.disconnect(websocket)