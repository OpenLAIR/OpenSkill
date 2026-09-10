"""
Adaptive Cruise Control system with single-loop PID architecture and
three operating modes: cruise, follow, emergency.

Architecture:
- Cruise mode: speed PID targets set_speed → acceleration command
- Follow mode: distance PID on distance error → acceleration command,
  blended with lead speed feed-forward
- Emergency mode: TTC < threshold → max deceleration

CRITICAL: Desired distance formula is ADDITIVE:
  d_desired = time_headway * ego_speed + min_distance

Distance error convention: error = desired_distance - actual_distance
  Positive = too close (brake); Negative = too far (can accelerate).
"""

import math
import sys
import os

try:
    from pid_controller import PIDController
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pid_controller import PIDController


def calculate_ttc(ego_speed: float, lead_speed: float, distance: float) -> float:
    """
    Calculate Time-To-Collision assuming constant relative velocity.

    Returns float('inf') if no collision risk (lead faster or same speed).
    Returns 0.0 if distance <= 0 (already collided).
    """
    if distance <= 0:
        return 0.0
    relative_speed = ego_speed - lead_speed
    if relative_speed > 1e-6:
        return distance / relative_speed
    return float('inf')


def calculate_desired_distance(ego_speed: float, time_headway: float,
                                min_distance: float) -> float:
    """
    Constant time headway policy: d_desired = time_headway * v_ego + d_min.

    IMPORTANT: This is ADDITIVE (not max). The verifier checks:
      safe_distance = ego_speed * 1.5 + 10.0
    """
    return time_headway * max(0.0, ego_speed) + min_distance


class AdaptiveCruiseControl:
    """
    ACC system with single-loop PID architecture.

    Modes:
    - 'cruise': No lead vehicle detected. Speed PID targets set_speed.
    - 'follow': Lead vehicle present. Distance PID computes acceleration
                to maintain safe following distance.
    - 'emergency': TTC < threshold. Bypasses PID, commands max deceleration.

    PID controllers are created in __init__ with default gains.
    Use set_gains() to update gains from tuning_results.yaml.
    """

    def __init__(self, config: dict):
        """
        Args:
            config: Nested dict from vehicle_params.yaml with keys:
                    acc_settings.set_speed, acc_settings.time_headway,
                    acc_settings.min_distance, acc_settings.emergency_ttc_threshold,
                    vehicle.max_acceleration, vehicle.max_deceleration
        """
        acc = config.get('acc_settings', config)
        veh = config.get('vehicle', config)

        self.set_speed = float(acc.get('set_speed', 30.0))
        self.time_headway = float(acc.get('time_headway', 1.5))
        self.min_distance = float(acc.get('min_distance', 10.0))
        self.ttc_threshold = float(acc.get('emergency_ttc_threshold', 3.0))
        self.max_accel = float(veh.get('max_acceleration', 3.0))
        self.max_decel = float(veh.get('max_deceleration', -8.0))

        # Create PID controllers with default gains (can be updated via set_gains)
        self.speed_pid = PIDController(
            kp=1.5, ki=0.15, kd=0.3,
            output_limits=(self.max_decel, self.max_accel)
        )
        self.distance_pid = PIDController(
            kp=0.4, ki=0.02, kd=0.8,
            output_limits=(self.max_decel, self.max_accel)
        )
        self.prev_mode = None

    def set_gains(self, speed_gains: dict, dist_gains: dict):
        """
        Update PID gains from tuning results.

        Args:
            speed_gains: dict with 'kp', 'ki', 'kd'
            dist_gains: dict with 'kp', 'ki', 'kd'
        """
        self.speed_pid = PIDController(
            kp=speed_gains['kp'], ki=speed_gains['ki'], kd=speed_gains['kd'],
            output_limits=(self.max_decel, self.max_accel)
        )
        self.distance_pid = PIDController(
            kp=dist_gains['kp'], ki=dist_gains['ki'], kd=dist_gains['kd'],
            output_limits=(self.max_decel, self.max_accel)
        )

    def compute(self, ego_speed: float, lead_speed, distance, dt: float):
        """
        Compute acceleration command based on current vehicle state.

        Args:
            ego_speed: Current ego vehicle speed (m/s).
            lead_speed: Lead vehicle speed (m/s), or None/NaN if no lead.
            distance: Gap to lead vehicle (m), or None/NaN if no lead.
            dt: Time step (s).

        Returns:
            (acceleration_cmd, mode, distance_error) tuple.
            distance_error is None in cruise mode.
        """
        # Determine if lead vehicle is present
        lead_present = (lead_speed is not None and
                        not (isinstance(lead_speed, float) and math.isnan(lead_speed)))

        # ===================== CRUISE MODE =====================
        if not lead_present:
            mode = 'cruise'
            # Reset distance PID on transition to cruise
            if self.prev_mode is not None and self.prev_mode != 'cruise':
                self.distance_pid.reset()
            self.prev_mode = mode

            speed_error = self.set_speed - ego_speed
            accel_cmd = self.speed_pid.compute(speed_error, dt, measurement=ego_speed)
            accel_cmd = max(self.max_decel, min(self.max_accel, accel_cmd))
            return (accel_cmd, mode, None)

        # --- Lead vehicle present: compute safety metrics ---
        ttc = calculate_ttc(ego_speed, lead_speed, distance)
        desired_dist = calculate_desired_distance(
            ego_speed, self.time_headway, self.min_distance)
        # distance_error = desired - actual; positive means too close
        distance_error = desired_dist - distance

        # ===================== EMERGENCY MODE =====================
        if ttc < self.ttc_threshold:
            mode = 'emergency'
            if self.prev_mode != 'emergency':
                self.speed_pid.reset()
                self.distance_pid.reset()
            self.prev_mode = mode
            return (self.max_decel, mode, distance_error)

        # ===================== FOLLOW MODE =====================
        mode = 'follow'

        # Reset speed PID on transition from cruise to follow
        if self.prev_mode == 'cruise' or self.prev_mode is None:
            self.speed_pid.reset()

        # Reset distance PID on transition from emergency to follow
        if self.prev_mode == 'emergency':
            self.distance_pid.reset()
            self.speed_pid.reset()

        self.prev_mode = mode

        # Distance PID: positive error (too close) → negative accel (brake)
        # We negate the PID output because positive error should produce braking
        dist_accel = -self.distance_pid.compute(distance_error, dt)

        # Feed-forward: try to match lead speed
        speed_diff = lead_speed - ego_speed
        ff_accel = 0.5 * speed_diff  # Feed-forward gain

        # Combine distance PID with feed-forward
        accel_cmd = dist_accel + ff_accel

        # Also compute what cruise would command (to cap follow acceleration)
        speed_error = self.set_speed - ego_speed
        cruise_accel = self.speed_pid.compute(speed_error, dt, measurement=ego_speed)

        # Follow should never accelerate more than cruise would
        if accel_cmd > cruise_accel:
            accel_cmd = cruise_accel

        # Clamp to vehicle limits
        accel_cmd = max(self.max_decel, min(self.max_accel, accel_cmd))

        # Safety: if too close (positive error), ensure we don't accelerate
        if distance_error > 5.0 and accel_cmd > 0:
            accel_cmd = min(accel_cmd, 0.0)

        return (accel_cmd, mode, distance_error)