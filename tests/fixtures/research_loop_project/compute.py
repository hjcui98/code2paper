def run_training(values, scale=2):
    """Aggregate values, compute a scaled score, and return a branch result."""
    total = sum(values)
    score = total / scale
    if score > 0:
        result = max(values)
    else:
        result = min(values)
    return result
