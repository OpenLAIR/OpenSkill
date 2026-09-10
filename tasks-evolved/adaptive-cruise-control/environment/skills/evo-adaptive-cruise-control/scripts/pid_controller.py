"""
Discrete-time PID controller with integral anti-windup (conditional clamping)
and optional derivative-on-measurement to prevent derivative kick.
"""


class PIDController:
    """
    Discrete PID controller with:
    - Output clamping (configurable min/max)
    - Integral anti-windup via conditional integration
    - Optional derivative-on-measurement (pass measurement arg to compute)
    - Safe first-timestep handling (zero derivative on first call)
    """

    def __init__(self, kp: float, ki: float, kd: float,
                 output_limits: tuple = (None, None)):
        """
        Args:
            kp: Proportional gain.
            ki: Integral gain.
            kd: Derivative gain.
            output_limits: (min_output, max_output) tuple. None means unbounded.
        """
        self.kp = float(kp)
        self.ki = float(ki)
        self.kd = float(kd)
        self.min_out, self.max_out = output_limits

        self.integral = 0.0
        self.prev_error = None
        self.prev_measurement = None

    def reset(self):
        """Resets all internal state (integral accumulator, previous values)."""
        self.integral = 0.0
        self.prev_error = None
        self.prev_measurement = None

    def compute(self, error: float, dt: float, measurement: float = None) -> float:
        """
        Compute PID control output.

        Args:
            error: Current tracking error (setpoint - measurement).
            dt: Time step in seconds. Must be > 0.
            measurement: (Optional) Current process variable. If provided,
                         derivative is computed on measurement to avoid kick.

        Returns:
            Clamped control output (float).
        """
        if dt <= 0.0:
            return 0.0

        # First timestep: initialize previous values, zero derivative
        if self.prev_error is None:
            self.prev_error = error
        if measurement is not None and self.prev_measurement is None:
            self.prev_measurement = measurement

        # Proportional term
        p_term = self.kp * error

        # Derivative term
        if measurement is not None and self.prev_measurement is not None:
            # Derivative on measurement (avoids derivative kick on setpoint change)
            d_term = -self.kd * (measurement - self.prev_measurement) / dt
        else:
            # Standard derivative on error
            d_term = self.kd * (error - self.prev_error) / dt

        # Compute unclamped output (using current integral, before update)
        unclamped_output = p_term + self.ki * self.integral + d_term

        # Apply output limits
        output = unclamped_output
        if self.max_out is not None and output > self.max_out:
            output = self.max_out
        if self.min_out is not None and output < self.min_out:
            output = self.min_out

        # Anti-windup: conditional integration (clamping)
        is_saturated = (output != unclamped_output)
        freeze_integral = False
        if is_saturated:
            if (error > 0 and self.max_out is not None and output >= self.max_out):
                freeze_integral = True
            elif (error < 0 and self.min_out is not None and output <= self.min_out):
                freeze_integral = True

        if not freeze_integral:
            self.integral += error * dt

        # Update state for next call
        self.prev_error = error
        if measurement is not None:
            self.prev_measurement = measurement

        return output