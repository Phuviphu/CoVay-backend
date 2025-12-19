def get_rank_title(elo):
    if elo < 1000: return "Iron"
    if elo < 1200: return "Bronze"
    if elo < 1500: return "Silver"
    if elo < 1800: return "Gold"
    return "Platinum"

def calculate_elo_change(winner_elo, loser_elo, difficulty, winner_streak, loser_streak, is_online=False):
    """
    Tính điểm ELO theo luật:
    - PvE Easy: +5/-10 (No Streak)
    - PvE Medium: +10/-10
    - PvE Hard: +20/-15
    - Online: Base(+25/-20) + Streak Bonus + Diff Bonus - High Elo Penalty
    """
    base_gain = 0
    base_loss = 0
    
    # 1. Điểm cơ bản
    if is_online:
        base_gain = 25; base_loss = 20
    else:
        if difficulty == "easy":
            base_gain = 5; base_loss = 10
        elif difficulty == "medium":
            base_gain = 10; base_loss = 10
        else: # hard
            base_gain = 20; base_loss = 15

    # 2. Bonus Chuỗi thắng (Chỉ Online hoặc PvE không phải Easy)
    streak_bonus = 0
    if is_online or difficulty != "easy":
        ws = winner_streak
        if ws >= 10: streak_bonus = 25
        elif ws >= 7: streak_bonus = 15
        elif ws >= 5: streak_bonus = 10
        elif ws >= 3: streak_bonus = 5

    # 3. Bonus chênh lệch Elo (Khi thắng đối thủ mạnh hơn 100đ)
    diff_bonus = 0
    if is_online and (loser_elo - winner_elo > 100):
        diff_bonus = 20

    # TỔNG CỘNG ĐIỂM THẮNG
    total_gain = base_gain + streak_bonus + diff_bonus
    
    # Cap tối đa +50
    if total_gain > 50: total_gain = 50
    
    # Giảm trừ khi Rank cao (>2000 Elo bị trừ 30%)
    if winner_elo > 2000:
        total_gain = int(total_gain * 0.7)

    # 4. Xử lý điểm thua (Phạt chuỗi thua)
    streak_penalty = 0
    ls = abs(loser_streak)
    if is_online or difficulty != "easy":
        if ls >= 5: streak_penalty = 10
        elif ls >= 3: streak_penalty = 5
    
    total_loss = base_loss + streak_penalty

    return total_gain, total_loss