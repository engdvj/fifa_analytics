def goals_per_shot(goals: int | float | None, shots: int | float | None) -> float | None:
    if shots in (None, 0):
        return None
    if goals is None:
        return None
    return float(goals) / float(shots)

