import math
import random
import copy
import traceback
import time
from app.game_logic.board import BLACK, WHITE, EMPTY

class AIPlayer:
    def __init__(self, board_size, level='hard'):
        self.size = board_size
        raw_level = level.lower() if level else 'medium'

        if self.size == 19 and raw_level == 'easy': 
            self.level = 'medium'
        else:
            self.level = raw_level

        # --- CẤU HÌNH (Tối ưu cho lối đánh phá hoại) ---
        if self.level == 'hard':
            self.use_advanced_tactics = True
            self.capture_extension = 2
            self.time_limit = 4.8 # Tăng thêm chút thời gian để tính phương án phá
            
            if self.size <= 9:
                self.depth = 6
                self.max_candidates = 35 
            elif self.size <= 13:
                self.depth = 5
                self.max_candidates = 25
            else: 
                self.depth = 3 # 19x19 Depth 3 nhưng lọc candidate siêu kỹ
                self.max_candidates = 15

        elif self.level == 'medium':
            self.time_limit = 2.0
            self.use_advanced_tactics = True
            self.capture_extension = 1
            if self.size <= 9: self.depth = 4; self.max_candidates = 20
            else: self.depth = 2; self.max_candidates = 12
        else: 
            self.time_limit = 1.0
            self.use_advanced_tactics = False
            self.capture_extension = 0
            self.depth = 2; self.max_candidates = 8

        # --- HEATMAP: Ưu tiên trung tâm để dễ cắt ---
        self.position_weights = [[0] * self.size for _ in range(self.size)]
        for r in range(self.size):
            for c in range(self.size):
                dist = min(r, c, self.size - 1 - r, self.size - 1 - c)
                if dist == 0: self.position_weights[r][c] = -5 
                elif dist == 1: self.position_weights[r][c] = 2
                elif dist == 2: self.position_weights[r][c] = 20 # Dòng 3
                elif dist == 3: self.position_weights[r][c] = 18 # Dòng 4
                else: self.position_weights[r][c] = 12 # Trung tâm cao

        self.start_time = 0

    # --- CÁC HÀM HỖ TRỢ ---
    def get_group_liberties(self, board, r, c):
        color = board.grid[r][c]
        if color == EMPTY: return 0, 0
        stack = [(r, c)]
        visited = {(r, c)}
        liberties = set()
        size = 0
        while stack:
            cr, cc = stack.pop()
            size += 1
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = cr + dr, cc + dc
                if board.is_valid_coord(nr, nc):
                    if board.grid[nr][nc] == EMPTY: liberties.add((nr, nc))
                    elif board.grid[nr][nc] == color and (nr, nc) not in visited:
                        visited.add((nr, nc))
                        stack.append((nr, nc))
        return len(liberties), size

    def calculate_influence_map(self, board, player):
        """Tạo bản đồ ảnh hưởng để biết địch đang chiếm chỗ nào"""
        opp = BLACK if player == WHITE else WHITE
        inf_map = [[0] * self.size for _ in range(self.size)]
        
        for r in range(self.size):
            for c in range(self.size):
                if board.grid[r][c] == player:
                    inf_map[r][c] += 10
                    for dr in range(-2, 3):
                        for dc in range(-2, 3):
                            nr, nc = r+dr, c+dc
                            if board.is_valid_coord(nr, nc): 
                                dist = abs(dr) + abs(dc)
                                val = 4 if dist == 1 else 2
                                inf_map[nr][nc] += val
                elif board.grid[r][c] == opp:
                    inf_map[r][c] -= 10
                    for dr in range(-2, 3):
                        for dc in range(-2, 3):
                            nr, nc = r+dr, c+dc
                            if board.is_valid_coord(nr, nc): 
                                dist = abs(dr) + abs(dc)
                                val = 4 if dist == 1 else 2
                                inf_map[nr][nc] -= val
        return inf_map

    def analyze_tactics(self, board, r, c, player):
        """Phân tích các nước đi chiến thuật: Cắt, Đè, Nối"""
        score = 0
        opp = BLACK if player == WHITE else WHITE
        
        # 1. CUTTING POINT (Điểm cắt) - Quan trọng nhất để phá
        # Kiểm tra nếu nước này nằm chéo giữa 2 quân địch
        enemy_diag = 0
        enemy_adj = 0
        
        for dr, dc in [(-1,-1),(-1,1),(1,-1),(1,1)]: # Chéo
            nr, nc = r+dr, c+dc
            if board.is_valid_coord(nr, nc) and board.grid[nr][nc] == opp:
                enemy_diag += 1
        
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]: # Thẳng
            nr, nc = r+dr, c+dc
            if board.is_valid_coord(nr, nc) and board.grid[nr][nc] == opp:
                enemy_adj += 1

        # Nếu địch có 2 quân chéo mà chưa nối -> Cắt ngay
        if enemy_diag >= 2 and enemy_adj == 0:
            score += 300 

        # 2. HANE / BLOCK (Chặn đầu)
        if enemy_adj > 0: score += 50

        # 3. SELF SHAPE (Tạo hình đẹp cho mình)
        my_adj = 0
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            if board.is_valid_coord(nr, nc) and board.grid[nr][nc] == player: my_adj += 1
        
        if my_adj >= 1: score += 40 # Nối quân
        
        return score

    def evaluate(self, board, player):
        score = 0
        my_cap = board.captured_white if player == WHITE else board.captured_black
        opp_cap = board.captured_black if player == WHITE else board.captured_white
        
        # 1. MATERIAL
        score += (my_cap - opp_cap) * 5000 

        # 2. INFLUENCE BALANCE (Cân bằng thế lực)
        # AI muốn tổng điểm ảnh hưởng của mình cao hơn địch
        inf_map = self.calculate_influence_map(board, player)
        total_inf = sum(sum(row) for row in inf_map)
        score += total_inf * 10

        visited = set()
        for r in range(self.size):
            for c in range(self.size):
                if board.grid[r][c] != EMPTY and (r,c) not in visited:
                    color = board.grid[r][c]
                    libs, size = self.get_group_liberties(board, r, c)
                    visited.add((r,c)) 

                    group_val = (libs * 80) + (size * 20)
                    
                    # LOGIC SỐNG CÒN
                    if libs == 1: group_val -= 25000 # Cấp cứu
                    elif libs == 2: group_val -= 6000  # Nguy hiểm
                    elif libs == 3: group_val -= 800   
                    
                    if color == player:
                        score += group_val
                        score += self.position_weights[r][c] * 10
                    else:
                        score -= group_val 
                        # Thưởng lớn nếu bao vây được địch
                        if libs == 1: score += 15000 
                        elif libs == 2: score += 4000

        return score + random.randint(0, 5)

    def get_candidate_moves(self, board, player):
        candidates = {} 
        opp = BLACK if player == WHITE else WHITE
        
        # 1. URGENT MOVES (Sát khí)
        for r in range(self.size):
            for c in range(self.size):
                if board.grid[r][c] != EMPTY:
                    libs, _ = self.get_group_liberties(board, r, c)
                    if libs <= 2:
                        priority = 50000 if libs == 1 else 10000
                        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                            nr, nc = r+dr, c+dc
                            if board.is_valid_coord(nr, nc) and board.grid[nr][nc] == EMPTY:
                                candidates[(nr, nc)] = candidates.get((nr, nc), 0) + priority

        # 2. INVASION & REDUCTION (Phá đất) - NEW FEATURE
        # Quét bản đồ ảnh hưởng
        inf_map = self.calculate_influence_map(board, player)
        
        if len(candidates) < self.max_candidates:
            for r in range(self.size):
                for c in range(self.size):
                    if board.grid[r][c] != EMPTY:
                        # Quét xung quanh các quân cờ hiện có
                        for dr in range(-2, 3):
                            for dc in range(-2, 3):
                                if dr==0 and dc==0: continue
                                nr, nc = r+dr, c+dc
                                if board.is_valid_coord(nr, nc) and board.grid[nr][nc] == EMPTY:
                                    if (nr, nc) in candidates: continue

                                    dist = abs(dr) + abs(dc)
                                    p = 60 // (dist if dist > 0 else 1)
                                    p += self.position_weights[nr][nc] * 5
                                    
                                    # LOGIC PHÁ ĐẤT (Intercept)
                                    # Nếu ô này đang bị địch kiểm soát mạnh (inf < -2)
                                    # NHƯNG không quá mạnh đến mức chết chắc (inf > -10)
                                    # -> Đây là điểm xâm nhập lý tưởng!
                                    curr_inf = inf_map[nr][nc]
                                    if -8 <= curr_inf <= -2: 
                                        p += 50 # Ưu tiên xâm nhập
                                    
                                    # LOGIC CẮT (Cutting)
                                    # Kiểm tra xem nước này có cắt được chéo địch không
                                    has_cut = False
                                    opp_diag_count = 0
                                    for cdr, cdc in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                                        cr, cc = nr+cdr, nc+cdc
                                        if board.is_valid_coord(cr, cc) and board.grid[cr][cc] == opp:
                                            opp_diag_count += 1
                                    if opp_diag_count >= 2: p += 80 # Ưu tiên cắt cực mạnh

                                    candidates[(nr, nc)] = candidates.get((nr, nc), 0) + p

        if len(candidates) < 5:
            stars = [(3,3), (3,self.size-4), (self.size-4,3), (self.size-4,self.size-4), (self.size//2, self.size//2)]
            for p in stars:
                if board.is_valid_coord(p[0],p[1]) and board.grid[p[0]][p[1]] == EMPTY:
                    candidates[p] = 100

        sorted_moves = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
        return [move for move, _ in sorted_moves[:self.max_candidates]]

    def minimax(self, board, depth, alpha, beta, maximizing, player):
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
                valid, _ = board.is_valid_move(r, c, curr)
                if not valid: continue
                try:
                    temp = copy.deepcopy(board)
                    temp.grid[r][c] = curr
                    
                    captured_count = 0
                    res = temp.handle_captures(r, c, curr)
                    if isinstance(res, (list, set, tuple)): captured_count = len(res)
                    elif isinstance(res, int): captured_count = res

                    new_depth = depth - 1
                    if captured_count > 0 and self.capture_extension > 0 and depth > 1: new_depth = depth 

                    eval_score, _ = self.minimax(temp, new_depth, alpha, beta, False, player)
                    
                    # Cộng điểm chiến thuật (Phá/Chặn)
                    tactical = 0
                    if self.use_advanced_tactics: 
                        tactical += self.analyze_tactics(temp, r, c, curr)

                    total_score = eval_score + (captured_count * 5000) + tactical
                    
                    if total_score > max_eval:
                        max_eval = total_score
                        best_move = (r, c)
                    alpha = max(alpha, total_score)
                    if beta <= alpha: break
                    if time.time() - self.start_time > self.time_limit: break
                except: continue
            return max_eval, best_move
        else:
            min_eval = math.inf
            for r, c in moves:
                valid, _ = board.is_valid_move(r, c, curr)
                if not valid: continue
                try:
                    temp = copy.deepcopy(board)
                    temp.grid[r][c] = curr
                    
                    captured_count = 0
                    res = temp.handle_captures(r, c, curr)
                    if isinstance(res, (list, set, tuple)): captured_count = len(res)
                    elif isinstance(res, int): captured_count = res
                    
                    new_depth = depth - 1
                    if captured_count > 0 and depth > 1: new_depth = depth

                    eval_score, _ = self.minimax(temp, new_depth, alpha, beta, True, player)
                    
                    tactical = 0
                    if self.use_advanced_tactics: 
                        tactical += self.analyze_tactics(temp, r, c, curr)

                    total_score = eval_score - (captured_count * 5000) - tactical

                    if total_score < min_eval:
                        min_eval = total_score
                        best_move = (r, c)
                    beta = min(beta, total_score)
                    if beta <= alpha: break
                    if time.time() - self.start_time > self.time_limit: break
                except: continue
            return min_eval, best_move

    def get_best_move(self, board, player):
        print(f"🤖 AI V15 (Interceptor): Size={self.size} | Mode={self.level.upper()} | Depth={self.depth}")
        self.start_time = time.time()
        
        try:
            score, move = self.minimax(board, self.depth, -math.inf, math.inf, True, player)
            elapsed = time.time() - self.start_time
            if move:
                valid, _ = board.is_valid_move(move[0], move[1], player)
                if valid:
                    print(f"AI Selected: {move} | Score: {score} | Time: {elapsed:.2f}s")
                    return move
        except Exception:
            traceback.print_exc()

        print("⚠️ AI Fallback Strategy")
        fallback_candidates = []
        for r in range(self.size):
            for c in range(self.size):
                if board.grid[r][c] == EMPTY:
                    valid, _ = board.is_valid_move(r, c, player)
                    if valid:
                        prio = self.position_weights[r][c]
                        fallback_candidates.append((prio, (r, c)))
        
        if fallback_candidates:
            fallback_candidates.sort(reverse=True)
            return fallback_candidates[0][1]
        return None