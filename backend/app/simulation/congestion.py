"""
Congestion model for CityFlow AI.

Uses a transparent utilization-based classification:
  utilization = traffic / capacity

Classification:
  < 0.50       LOW
  0.50 - 0.75  MODERATE
  0.75 - 0.90  HIGH
  > 0.90       CRITICAL
"""


def calculate_utilization(flow: int, capacity: int) -> float:
    """Calculate utilization ratio."""
    if capacity <= 0:
        return 1.0
    return min(flow / capacity, 2.0)  # Cap at 200% for display


def classify_congestion(utilization: float) -> str:
    """Classify congestion level based on utilization."""
    if utilization < 0.50:
        return "low"
    elif utilization < 0.75:
        return "moderate"
    elif utilization < 0.90:
        return "high"
    else:
        return "critical"


def estimate_speed(speed_limit: int, utilization: float) -> float:
    """
    Estimate actual speed based on utilization.
    Uses a simple BPR-like function:
    speed = free_flow_speed / (1 + alpha * (utilization ^ beta))
    """
    alpha = 0.15
    beta = 4.0
    if utilization <= 0:
        return float(speed_limit)
    return speed_limit / (1 + alpha * (utilization ** beta))


def estimate_delay_percent(
    before_utilization: float,
    after_utilization: float,
    speed_limit: int = 50,
) -> float:
    """
    Estimate the percentage increase in travel time.
    """
    before_speed = estimate_speed(speed_limit, before_utilization)
    after_speed = estimate_speed(speed_limit, after_utilization)
    if after_speed <= 0:
        return 100.0
    if before_speed <= 0:
        return 0.0
    # delay = (new_time - old_time) / old_time * 100
    delay = ((before_speed / after_speed) - 1) * 100
    return max(0.0, round(delay, 1))
