import copy

# --- HẰNG SỐ ---
EMPTY = 0
BLACK = 1
WHITE = 2
DEAD_BLACK = 3 # Xác Đen
DEAD_WHITE = 4 # Xác Trắng

class GoBoard:
    def __init__(self, size=9):
        self.size = size
        self.grid = [[EMPTY for _ in range(size)] for _ in range(size)]
        
        self.history_stack = [] 
        self.move_log = []
        self.captured_black = 0
        self.captured_white = 0
        
        self.current_turn = BLACK 
        self.consecutive_passes = 0
        self.is_game_over = False

    def save_state(self):
        state = {
            'grid': copy.deepcopy(self.grid),
            'captured_black': self.captured_black,
            'captured_white': self.captured_white,
            'move_log': list(self.move_log),
            'current_turn': self.current_turn,
            'consecutive_passes': self.consecutive_passes,
            'is_game_over': self.is_game_over
        }
        self.history_stack.append(state)

    def is_valid_coord(self, r, c):
        return 0 <= r < self.size and 0 <= c < self.size

    def get_neighbors(self, r, c):
        neighbors = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if self.is_valid_coord(nr, nc):
                neighbors.append((nr, nc))
        return neighbors

    def get_group_liberties(self, r, c, board_state=None):
        """
        Tính Khí: Coi Xác Chết (3,4) và Ô Trống (0) đều là KHÍ.
        Giúp quân sống không bị nghẹt thở bởi xác chết.
        """
        if board_state is None: board_state = self.grid
        if not self.is_valid_coord(r, c): return set(), 0
        
        color = board_state[r][c]
        if color in [EMPTY, DEAD_BLACK, DEAD_WHITE]: return set(), 0

        group = set(); liberties = set(); queue = [(r, c)]
        group.add((r, c))

        while queue:
            curr_r, curr_c = queue.pop(0)
            for nr, nc in self.get_neighbors(curr_r, curr_c):
                val = board_state[nr][nc]
                
                # Cả Ô Trống và Xác Chết đều tính là đường thở (Liberties)
                if val in [EMPTY, DEAD_BLACK, DEAD_WHITE]:
                    liberties.add((nr, nc))
                
                # Cùng màu (Quân sống) thì nối nhóm
                elif val == color and (nr, nc) not in group:
                    group.add((nr, nc)); queue.append((nr, nc))
                    
        return group, len(liberties)

    def handle_captures(self, r, c, player):
        """Ăn quân: Biến quân bị ăn thành XÁC (3 hoặc 4)"""
        opponent = WHITE if player == BLACK else BLACK
        dead_state = DEAD_BLACK if opponent == BLACK else DEAD_WHITE
        captures_made = 0
        
        for nr, nc in self.get_neighbors(r, c):
            if self.grid[nr][nc] == opponent:
                group, liberties = self.get_group_liberties(nr, nc)
                if liberties == 0:
                    for gr, gc in group:
                        self.grid[gr][gc] = dead_state 
                        captures_made += 1
        
        if player == BLACK: self.captured_white += captures_made
        else: self.captured_black += captures_made
        return captures_made

    def is_valid_move(self, r, c, player):
        """Kiểm tra luật chơi (Fixed logic Snapback/Thí quân)"""
        if self.is_game_over: return False, "Game đã kết thúc"
        if player != self.current_turn: return False, "Chưa tới lượt bạn!"
        if not self.is_valid_coord(r, c): return False, "Tọa độ sai"
        
        val = self.grid[r][c]
        if val != EMPTY:
            if val in [DEAD_BLACK, DEAD_WHITE]: return False, "Ô này đã bị ăn"
            return False, "Ô đã có quân"

        # --- [QUAN TRỌNG] CHECK TỰ SÁT & ĂN QUÂN ---
        temp_board = copy.deepcopy(self.grid)
        temp_board[r][c] = player
        
        captured_any = False
        opponent = WHITE if player == BLACK else BLACK
        
        # 1. Kiểm tra xem nước này có giết được đám nào của địch không?
        for nr, nc in self.get_neighbors(r, c):
            if temp_board[nr][nc] == opponent:
                # SỬA LỖI Ở ĐÂY: Hứng biến đầu tiên là liberties (khí)
                res = self.get_group_liberties(nr, nc, temp_board)
                
                # Xử lý an toàn dù hàm trả về (khí, group) hay chỉ (khí)
                if isinstance(res, tuple):
                    libs = res[0] # Lấy phần tử đầu tiên
                else:
                    libs = res
                
                # Nếu liberties là list/set thì đếm len, nếu là int thì so sánh
                lib_count = len(libs) if isinstance(libs, (set, list, tuple)) else libs

                if lib_count == 0:
                    captured_any = True
                    break # Chỉ cần ăn được 1 đám là nước đi Hợp lệ ngay (Snapback)
        
        # 2. Nếu KHÔNG ăn được ai, mà đặt xuống mình HẾT KHÍ -> LÀ TỰ SÁT -> CẤM
        if not captured_any:
            res_my = self.get_group_liberties(r, c, temp_board)
            
            # Lấy khí của mình
            if isinstance(res_my, tuple):
                my_libs = res_my[0]
            else:
                my_libs = res_my
            
            my_lib_count = len(my_libs) if isinstance(my_libs, (set, list, tuple)) else my_libs

            if my_lib_count == 0:
                return False, "Nước đi tự sát (Cấm)"

        return True, "OK"
    
    def make_move(self, r, c, player):
        # Kiểm tra kỹ luật trước khi đánh
        valid, msg = self.is_valid_move(r, c, player)
        if not valid: return False, msg

        self.save_state()
        self.grid[r][c] = player
        
        # Thực hiện ăn quân (nếu có)
        self.handle_captures(r, c, player)
        
        move_str = f"{'Đen' if player == BLACK else 'Trắng'} đánh ({r},{c})"
        self.move_log.append(move_str)
        self.current_turn = WHITE if player == BLACK else BLACK
        self.consecutive_passes = 0
        return True, "Thành công"

    def pass_turn(self):
        self.save_state()
        self.consecutive_passes += 1
        player_name = "Đen" if self.current_turn == BLACK else "Trắng"
        self.move_log.append(f"{player_name} Bỏ lượt")
        self.current_turn = WHITE if self.current_turn == BLACK else BLACK
        if self.consecutive_passes >= 2:
            self.is_game_over = True
            return True, "Game Over"
        return False, "Đã bỏ lượt"

    # --- TÍNH ĐIỂM (Area Scoring) ---
    def get_territory_owner(self, r, c, visited):
        queue = [(r, c)]; visited.add((r, c)); region = [(r, c)]
        touch_black = False; touch_white = False
        
        while queue:
            curr_r, curr_c = queue.pop(0)
            for nr, nc in self.get_neighbors(curr_r, curr_c):
                val = self.grid[nr][nc]
                # Coi cả Ô Trống và Xác Chết là vùng cần duyệt
                if val in [EMPTY, DEAD_BLACK, DEAD_WHITE]:
                    if (nr, nc) not in visited:
                        visited.add((nr, nc)); queue.append((nr, nc)); region.append((nr, nc))
                elif val == BLACK: touch_black = True
                elif val == WHITE: touch_white = True
        
        if touch_black and not touch_white: return BLACK, region
        if touch_white and not touch_black: return WHITE, region
        return 0, region

    def calculate_score(self):
        black_score = 0; white_score = 0; visited = set()
        
        for r in range(self.size):
            for c in range(self.size):
                val = self.grid[r][c]
                
                # 1. Quân sống
                if val == BLACK: black_score += 1
                elif val == WHITE: white_score += 1
                
                # 2. Xác chết (Nằm trên đất địch -> Điểm cho địch)
                elif val == DEAD_BLACK: white_score += 1
                elif val == DEAD_WHITE: black_score += 1

                # 3. Đất trống (Dùng loang để tìm chủ)
                # Chỉ tính ô EMPTY, vì DEAD đã cộng ở bước 2
                if val in [EMPTY, DEAD_BLACK, DEAD_WHITE] and (r, c) not in visited:
                    owner, points = self.get_territory_owner(r, c, visited)
                    empty_count = 0
                    for pr, pc in points:
                        if self.grid[pr][pc] == EMPTY: empty_count += 1
                    
                    if owner == BLACK: black_score += empty_count
                    elif owner == WHITE: white_score += empty_count
        
        white_score += 7.5
        return black_score, white_score

    def undo_round(self):
        if len(self.history_stack) >= 2:
            self.history_stack.pop(); prev_state = self.history_stack.pop()
            self.grid = prev_state['grid']
            self.captured_black = prev_state['captured_black']
            self.captured_white = prev_state['captured_white']
            self.move_log = prev_state['move_log']
            self.current_turn = BLACK 
            self.consecutive_passes = 0; self.is_game_over = False
            return True, "Đã Undo"
        elif len(self.history_stack) == 1:
            prev_state = self.history_stack.pop()
            self.grid = prev_state['grid']
            self.current_turn = BLACK
            self.consecutive_passes = 0; self.is_game_over = False
            return True, "Về đầu game"
        return False, "Không thể Undo"