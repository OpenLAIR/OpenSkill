import pandas as pd
import numpy as np
from itertools import combinations


# ============================================================
# SCORING FUNCTIONS - 6 categories for dice game
# ============================================================

def score_high_and_often(rolls):
    """Highest number rolled multiplied by the number of times it was rolled."""
    highest = max(rolls)
    count = rolls.count(highest) if isinstance(rolls, list) else list(rolls).count(highest)
    return highest * count


def score_summation(rolls):
    """Sum of all six dice rolls."""
    return sum(rolls)


def score_highs_and_lows(rolls):
    """Highest * Lowest * (Highest - Lowest)."""
    highest = max(rolls)
    lowest = min(rolls)
    return highest * lowest * (highest - lowest)


def score_only_two_numbers(rolls):
    """If all 6 rolls use exactly 2 distinct numbers, score is 30. Otherwise None."""
    distinct = set(rolls)
    if len(distinct) == 2:
        return 30
    return None  # Not applicable


def score_all_the_numbers(rolls):
    """If rolls are 1,2,3,4,5,6 in any order, score is 40. Otherwise None."""
    if set(rolls) == {1, 2, 3, 4, 5, 6}:
        return 40
    return None  # Not applicable


def score_ordered_subset_of_four(rolls):
    """If rolls (in order rolled) contain a run of 4 consecutive increasing
    or decreasing numbers, score is 50. Otherwise None."""
    rolls_list = list(rolls)
    n = len(rolls_list)
    for i in range(n - 3):
        subset = rolls_list[i:i+4]
        # Check increasing: each next is exactly 1 more
        increasing = all(subset[j+1] == subset[j] + 1 for j in range(3))
        # Check decreasing: each next is exactly 1 less
        decreasing = all(subset[j+1] == subset[j] - 1 for j in range(3))
        if increasing or decreasing:
            return 50
    return None  # Not applicable


# ============================================================
# TURN AND GAME SCORING
# ============================================================

SCORING_FUNCTIONS = {
    'high_and_often': score_high_and_often,
    'summation': score_summation,
    'highs_and_lows': score_highs_and_lows,
    'only_two_numbers': score_only_two_numbers,
    'all_the_numbers': score_all_the_numbers,
    'ordered_subset_of_four': score_ordered_subset_of_four,
}


def compute_turn_scores(rolls):
    """Compute all possible category scores for a single turn.
    Returns dict of {category_name: score} for applicable categories.
    Categories that don't apply (return None) are excluded."""
    scores = {}
    for name, func in SCORING_FUNCTIONS.items():
        result = func(rolls)
        if result is not None:
            scores[name] = result
    return scores


def compute_game_score(turn1_rolls, turn2_rolls):
    """Compute the highest possible combined score for a game of 2 turns.
    Each turn must use a different category. Find the best pair of
    different categories that maximizes the total score."""
    t1_scores = compute_turn_scores(turn1_rolls)
    t2_scores = compute_turn_scores(turn2_rolls)
    
    best_score = 0
    
    # Try all combinations: assign one category to turn1, different category to turn2
    for cat1, s1 in t1_scores.items():
        for cat2, s2 in t2_scores.items():
            if cat1 != cat2:
                total = s1 + s2
                if total > best_score:
                    best_score = total
    
    return best_score


# ============================================================
# DATA LOADING
# ============================================================

def load_excel_data(filepath, sheet_name='Data'):
    """Load dice roll data from Excel file.
    Returns DataFrame with columns: turn_number, game_number, roll1-roll6.
    Data starts at row 9 (0-indexed) in the Data sheet, columns C-J (indices 2-9)."""
    df = pd.read_excel(
        filepath,
        sheet_name=sheet_name,
        header=None,
        engine='openpyxl'
    )
    
    # Extract data rows (row 8 is header, rows 9+ are data)
    # Column 2 = Turn number, 3 = Game number, 4-9 = Roll 1-6
    data = df.iloc[9:, 2:10].copy()
    data.columns = ['turn_number', 'game_number', 'roll1', 'roll2', 'roll3', 'roll4', 'roll5', 'roll6']
    data = data.reset_index(drop=True)
    
    # Convert to numeric
    for col in data.columns:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    
    data = data.dropna()
    
    # Convert to int
    for col in data.columns:
        data[col] = data[col].astype(int)
    
    return data


# ============================================================
# MATCH ANALYSIS
# ============================================================

def compute_all_game_scores(data):
    """Compute scores for all games from the turn data.
    Each game has 2 turns. Returns dict of {game_number: score}."""
    game_scores = {}
    
    # Group by game number
    grouped = data.groupby('game_number')
    
    for game_num, group in grouped:
        if len(group) != 2:
            continue
        
        rows = group.sort_values('turn_number')
        turn1 = rows.iloc[0]
        turn2 = rows.iloc[1]
        
        t1_rolls = [turn1['roll1'], turn1['roll2'], turn1['roll3'],
                    turn1['roll4'], turn1['roll5'], turn1['roll6']]
        t2_rolls = [turn2['roll1'], turn2['roll2'], turn2['roll3'],
                    turn2['roll4'], turn2['roll5'], turn2['roll6']]
        
        game_scores[game_num] = compute_game_score(t1_rolls, t2_rolls)
    
    return game_scores


def split_by_parity(game_scores):
    """Split games into Player 1 (odd-numbered games: 1,3,5...)
    and Player 2 (even-numbered games: 2,4,6...).
    Returns two dicts."""
    p1_scores = {g: s for g, s in game_scores.items() if g % 2 == 1}
    p2_scores = {g: s for g, s in game_scores.items() if g % 2 == 0}
    return p1_scores, p2_scores


def compare_paired_matches(p1_scores, p2_scores):
    """Pair games: game 1 vs game 2, game 3 vs game 4, etc.
    Returns (p1_wins, p2_wins, ties)."""
    p1_wins = 0
    p2_wins = 0
    ties = 0
    
    # Sort by game number
    p1_sorted = sorted(p1_scores.items())  # (1, score), (3, score), (5, score)...
    p2_sorted = sorted(p2_scores.items())  # (2, score), (4, score), (6, score)...
    
    min_len = min(len(p1_sorted), len(p2_sorted))
    
    for i in range(min_len):
        s1 = p1_sorted[i][1]  # Player 1's score (odd game)
        s2 = p2_sorted[i][1]  # Player 2's score (even game)
        
        if s1 > s2:
            p1_wins += 1
        elif s2 > s1:
            p2_wins += 1
        else:
            ties += 1
    
    return p1_wins, p2_wins, ties


def compute_win_difference(p1_wins, p2_wins):
    """Compute (Player 1 wins) - (Player 2 wins)."""
    return p1_wins - p2_wins


def write_answer(result, filepath='/root/answer.txt'):
    """Write the numeric result to a file with no trailing newline."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(str(result))
