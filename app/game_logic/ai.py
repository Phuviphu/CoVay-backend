import math
import random
import copy
import traceback
import time
from app.game_logic.board import BLACK, WHITE, EMPTY

class AIPlayer:
    def __init__(self, board_size, level='hard'):
        self.size = board_size
        self.level = level.lower() if level else 'medium'

        # --- CẤU HÌNH ---
        if self.level == 'easy':
            # EASY: "Khôn tí" (Nghĩ 1 nước - Greedy)
            self.depth = 1          
            self.max_candidates = 5 
            self.time_limit = 1.0   
            self.randomness = 500 # Có sai sót
            
        elif self.level == 'medium':
            # MEDIUM: Nghĩ 2 nước
            self.depth = 2
            self.max_candidates = 10
            self.time_limit = 3.0
            self.randomness = 100 
            
        else: # HARD
            # HARD: Chiến thần suy nghĩ 5 giây
            self.time_limit = 5.0 # <--- ĐÚNG Ý CẬU: 5 GIÂY
            self.randomness = 0 # Đánh chuẩn 100%
            
            # Cấu hình độ sâu để tận dụng hết 5s
            if self.size <= 9:
                self.depth = 6 
                self.max_candidates = 40
            elif self.size <= 13:
                self.depth = 4 
                self.max_candidates = 25
            else: 
                self.depth = 3 
                self.max_candidates = 20

        # Heatmap
        self.position_weights = [[0] * self.size for _ in range(self.size)]
        for r in range(self.size):
            for c in range(self.size):
                dist = min(r, c, self.size - 1 - r, self.size - 1 - c)
                if dist >= 2: self.position_weights[r][c] = 10 
                elif dist == 1: self.position_weights[r][c] = 2
                else: self.position_weights[r][c] = -2 

        self.start_time = 0

    # --- CHIẾN THUẬT (HARD) ---
    def analyze_tactics(self, board, r, c, player):
        if self.level != 'hard': return 0

        score = 0
        opp = BLACK if player == WHITE else WHITE
        
        # Cắt quân (Cutting)
        cuts = 0
        for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
            nr, nc = r+dr, c+dc
            if board.is_valid_coord(nr, nc) and board.grid[nr][nc] == opp:
                cuts += 1
        if cuts >= 2: score += 400 

        # Áp sát (Hane)
        adj_opp = 0
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            if board.is_valid_coord(nr, nc) and board.grid[nr][nc] == opp:
                adj_opp += 1
        if adj_opp > 0: score += 50 

        return score

    # --- HÀM TÌM KHÍ ---
    def get_liberties(self, board, r, c):
        color = board.grid[r][c]
        if color == EMPTY: return 0
        stack = [(r, c)]; visited = {(r, c)}; libs = 0
        while stack:
            cr, cc = stack.pop()
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = cr + dr, cc + dc
                if board.is_valid_coord(nr, nc):
                    if board.grid[nr][nc] == EMPTY: 
                        libs += 1
                        if libs > 5: return 5 
                    elif board.grid[nr][nc] == color and (nr, nc) not in visited:
                        visited.add((nr, nc)); stack.append((nr, nc))
        return libs

    def evaluate(self, board, player):
        score = 0
        my_cap = board.captured_white if player == WHITE else board.captured_black
        opp_cap = board.captured_black if player == WHITE else board.captured_white
        
        score += (my_cap - opp_cap) * 10000 

        for r in range(self.size):
            for c in range(self.size):
                if board.grid[r][c] == player:
                    score += 10 + self.position_weights[r][c]
                    
                    libs = self.get_liberties(board, r, c)
                    if libs == 1: score -= 50000 
                    elif libs == 2: score -= 5000

                elif board.grid[r][c] != EMPTY:
                    score -= 10
                    libs = self.get_liberties(board, r, c)
                    if libs == 1: score += 40000 
                    elif libs == 2: score += 3000

        return score

    def get_candidate_moves(self, board, player):
        candidates = {}
        for r in range(self.size):
            for c in range(self.size):
                if board.grid[r][c] != EMPTY:
                    for dr in range(-2, 3):
                        for dc in range(-2, 3):
                            nr, nc = r+dr, c+dc
                            if board.is_valid_coord(nr, nc) and board.grid[nr][nc] == EMPTY:
                                if (nr,nc) in candidates: continue
                                
                                p = self.position_weights[nr][nc] + random.randint(0, 5)
                                if self.level == 'hard':
                                    p += self.analyze_tactics(board, nr, nc, player)

                                candidates[(nr, nc)] = p
        
        if len(candidates) < 5:
            stars = [(2,2), (2,self.size-3), (self.size-3,2), (self.size-3,self.size-3), (self.size//2, self.size//2)]
            for p in stars:
                if board.is_valid_coord(p[0],p[1]) and board.grid[p[0]][p[1]] == EMPTY:
                    candidates[p] = 500

        sorted_moves = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
        return [move for move, _ in sorted_moves[:self.max_candidates]]

    def minimax(self, board, depth, alpha, beta, maximizing, player):
        # Kiểm tra thời gian: Nếu quá 5s thì dừng ngay lập tức
        if time.time() - self.start_time > self.time_limit:
            return self.evaluate(board, player), None
            
        if depth == 0: return self.evaluate(board, player), None
        
        opp = BLACK if player == WHITE else WHITE
        curr = player if maximizing else opp
        moves = self.get_candidate_moves(board, curr)
        
        if not moves: return self.evaluate(board, player), None

        best_move = None
        
        if maximizing:
            max_eval = -math.inf
            for r, c in moves:
                if not board.is_valid_move(r, c, curr)[0]: continue
                try:
                    temp = copy.deepcopy(board)
                    temp.grid[r][c] = curr
                    captured = temp.handle_captures(r, c, curr)
                    
                    eval_score, _ = self.minimax(temp, depth - 1, alpha, beta, False, player)
                    
                    if self.randomness > 0:
                        eval_score += random.randint(-self.randomness, self.randomness)

                    total = eval_score + (captured * 10000)
                    if total > max_eval: max_eval = total; best_move = (r, c)
                    alpha = max(alpha, total)
                    if beta <= alpha: break
                except: continue
            return max_eval, best_move
        else:
            min_eval = math.inf
            for r, c in moves:
                if not board.is_valid_move(r, c, curr)[0]: continue
                try:
                    temp = copy.deepcopy(board)
                    temp.grid[r][c] = curr
                    captured = temp.handle_captures(r, c, curr)
                    
                    eval_score, _ = self.minimax(temp, depth - 1, alpha, beta, True, player)
                    
                    if self.randomness > 0:
                        eval_score += random.randint(-self.randomness, self.randomness)

                    total = eval_score - (captured * 10000)
                    if total < min_eval: min_eval = total; best_move = (r, c)
                    beta = min(beta, total)
                    if beta <= alpha: break
                except: continue
            return min_eval, best_move

    def get_best_move(self, board, player):
        print(f"🤖 AI Thinking (5s Limit)... Level={self.level.upper()}")
        self.start_time = time.time()

        try:
            score, move = self.minimax(board, self.depth, -math.inf, math.inf, True, player)
            elapsed = time.time() - self.start_time
            if move:
                print(f"🔥 AI Move: {move} | Score: {score} | Time: {elapsed:.2f}s")
                return move
        except:
            traceback.print_exc()

        # Fallback
        for r in range(self.size):
            for c in range(self.size):
                if board.grid[r][c] == EMPTY and board.is_valid_move(r, c, player)[0]:
                    return (r, c)
        return None