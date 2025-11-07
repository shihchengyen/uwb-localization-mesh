import numpy as np
from typing import Dict, Tuple, Optional


class GainController:
    """
    Gain controller that selects the closer anchor pair (0&1) vs (2&3)
    and outputs left/right gains for the chosen pair.

    Features:
    - Distance-based gain model (linear or quadratic)
    - Near-field clamp (avoid infinite/huge gains at very small distances)
    - Rate limiting per update (avoid sudden jumps)
    - Exponential smoothing (low-pass filtering of gain targets)
    """

    def __init__(
        self,
        anchor_positions: Dict[int, np.ndarray],
        pair_a: Tuple[int, int] = (0, 1),
        pair_b: Tuple[int, int] = (2, 3),
        distance_model: str = "quadratic",  # "linear" or "quadratic"
        min_distance_cm: float = 30.0,       # clamp distances below this
        smoothing_alpha: float = 0.25,       # 0..1, higher = snappier
        max_delta_per_update: float = 0.08   # rate limit applied after smoothing
    ) -> None:
        self.anchor_positions = anchor_positions
        self.pair_a = pair_a
        self.pair_b = pair_b
        self.distance_model = distance_model
        self.min_distance_cm = float(min_distance_cm)
        self.smoothing_alpha = float(np.clip(smoothing_alpha, 0.0, 1.0))
        self.max_delta_per_update = float(np.clip(max_delta_per_update, 0.0, 1.0))

        self._prev_output: Optional[np.ndarray] = None  # [L, R]
        self._prev_pair: Optional[Tuple[int, int]] = None

    def update_position(self, phone_xyz_cm: Tuple[float, float, float]) -> Tuple[float, float, Tuple[int, int]]:
        """
        Update the controller with the latest phone position.

        Returns:
            (left_gain, right_gain, active_pair)
            - gains are in [0, 1]
            - active_pair is a tuple of anchor IDs corresponding to (L, R)
        """
        phone = np.asarray(phone_xyz_cm, dtype=float)

        active_pair = self._select_active_pair(phone)
        left_gain, right_gain = self._compute_pair_gains(phone, active_pair)

        # Smoothing (EMA) + rate limiting
        target = np.array([left_gain, right_gain], dtype=float)
        smoothed = self._ema(target)     # see how can rm this
        limited = self._rate_limit(smoothed)     # see how can rm also

        self._prev_output = limited #update values
        self._prev_pair = active_pair
        return float(limited[0]), float(limited[1]), active_pair

    def _select_active_pair(self, phone: np.ndarray) -> Tuple[int, int]:
        # Pair distance defined as min distance to either anchor in the pair
        a0, a1 = self.pair_a
        b0, b1 = self.pair_b

        d_a = min(self._dist_cm(phone, self.anchor_positions[a0]),
                  self._dist_cm(phone, self.anchor_positions[a1]))
        d_b = min(self._dist_cm(phone, self.anchor_positions[b0]),
                  self._dist_cm(phone, self.anchor_positions[b1]))

        return self.pair_a if d_a <= d_b else self.pair_b

    def _compute_pair_gains(self, phone: np.ndarray, pair: Tuple[int, int]) -> Tuple[float, float]:
        left_id, right_id = pair
        d_left = self._dist_cm(phone, self.anchor_positions[left_id])
        d_right = self._dist_cm(phone, self.anchor_positions[right_id])

        # Clamp near-field
        d_left = max(d_left, self.min_distance_cm)
        d_right = max(d_right, self.min_distance_cm)

        # Distance models
        if self.distance_model == "linear":
            g_left = 1.0 / d_left
            g_right = 1.0 / d_right
        else:  # quadratic (default)
            g_left = 1.0 / (d_left * d_left)
            g_right = 1.0 / (d_right * d_right)

        # Normalize within the pair so the louder side maps to 1.0
        max_g = max(g_left, g_right)
        if max_g > 0:
            g_left /= max_g
            g_right /= max_g

        # Clamp to [0, 1]
        g_left = float(np.clip(g_left, 0.0, 1.0))
        g_right = float(np.clip(g_right, 0.0, 1.0))
        return g_left, g_right

    def _ema(self, target: np.ndarray) -> np.ndarray:
        if self._prev_output is None:
            return target
        alpha = self.smoothing_alpha
        return alpha * target + (1.0 - alpha) * self._prev_output

    def _rate_limit(self, current: np.ndarray) -> np.ndarray:
        if self._prev_output is None:
            # First frame: just clamp
            return np.clip(current, 0.0, 1.0)
        delta = current - self._prev_output
        delta = np.clip(delta, -self.max_delta_per_update, self.max_delta_per_update)
        limited = self._prev_output + delta
        return np.clip(limited, 0.0, 1.0)

    @staticmethod
    def _dist_cm(p: np.ndarray, q: np.ndarray) -> float:
        return float(np.linalg.norm(p - q))


__all__ = ["GainController"]


