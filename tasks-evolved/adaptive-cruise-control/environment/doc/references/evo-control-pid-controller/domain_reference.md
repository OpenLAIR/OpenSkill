# Domain Reference for evo-control-pid-controller

**Responsibility**: Provide a standalone PIDController class with reset() and compute(error, dt) methods, including output limits and integral windup prevention via clamping.

**Key functions to implement**: PIDController.__init__, PIDController.reset, PIDController.compute

---

## 1. Discrete PID Controller Implementation in Python


The Proportional-Integral-Derivative (PID) controller is the workhorse of industrial control systems, including longitudinal vehicle dynamics [cite: 1, 2]. In a digital simulation, continuous-time calculus is replaced by discrete-time difference equations.

### 1.1 Mathematical Formulation and the Derivative Term


A standard continuous-time PID controller calculates the control output \( u(t) \) based on the error \( e(t) \):
\[ u(t) = K_p e(t) + K_i \int_{0}^{t} e(\tau) d\tau + K_d \frac{de(t)}{dt} \]

In a discrete-time Python simulation with a fixed timestep \( \Delta t \) (`dt`), this is approximated using numerical integration (forward Euler or trapezoidal) and finite differences. The exact discrete-time formulation for the derivative term often poses a theoretical dilemma: should it be calculated on the error—\( (e_k - e_{k-1}) / \Delta t \)—or directly on the measurement (process variable) to avoid "derivative kick" when the setpoint changes? 

For an ACC system, setpoints (desired speed or distance) are generally smooth and derived from physical kinematics rather than abrupt step changes [cite: 3, 4]. Therefore, computing the derivative on the error via backward difference is mathematically sound, easily implemented, and widely accepted in standard ADAS prototyping:
\[ \text{Derivative Term} = K_d \frac{e_k - e_{k-1}}{\Delta t} \]

To handle the **first timestep** (when there is no previous error to reference), the derivative term evaluates to zero. This is handled programmatically by initializing `prev_error` to `None` and assigning it the current error on the first pass [cite: 5, 6].

### 1.2 Handling Integral Windup via Clamping


**Integral windup** is a severe vulnerability in PID controllers, occurring when the actuator (vehicle acceleration) reaches its physical limits (saturation), yet the error persists [cite: 2, 7]. The integral term continues to accumulate (wind up), resulting in massive overshoot when the setpoint is eventually reached because the accumulated integral must "unwind" [cite: 8, 9]. 

The most robust technique for vehicle dynamics is **conditional integration**, also known as **integrator clamping** [cite: 7, 10]. The logic dictates that if the controller's output is saturated (hits the maximum or minimum acceleration limits) AND the current error is pushing the output further into that same saturation direction, integration is suspended. If the error is pulling the output *away* from saturation, integration is permitted.

### 1.3 Complete Python Implementation


Below is a complete, reusable Python class implementing a discrete PID controller from scratch, devoid of external control libraries.

```python
class PIDController:
    """
    Discrete PID controller with integral clamping (anti-windup).
    """
    def __init__(self, kp: float, ki: float, kd: float, output_limits: tuple = (None, None)):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.min_out, self.max_out = output_limits
        
        self.integral = 0.0
        self.prev_error = None

    def reset(self):
        """Resets the internal state of the PID controller."""
        self.integral = 0.0
        self.prev_error = None

    def compute(self, error: float, dt: float) -> float:
        """
        Computes the control output based on the current error and time step.
        """
        if dt <= 0.0:
            return 0.0
            
        # Handle the first timestep gracefully
        if self.prev_error is None:
            self.prev_error = error

        # Proportional term
        p_term = self.kp * error
        
        # Derivative term (on error)
        d_term = self.kd * (error - self.prev_error) / dt
        
        # Calculate provisional output to check for saturation
        unclamped_output = p_term + self.ki * self.integral + d_term
        output = unclamped_output

        # Apply output limits
        if self.max_out is not None:
            output = min(output, self.max_out)
        if self.min_out is not None:
            output = max(output, self.min_out)

        # Anti-windup (Clamping/Conditional Integration)
        # Check if the output is saturated
        is_saturated = (output != unclamped_output)
        
        # Check if the error and the saturation are in the same direction
        # (meaning integration would make the saturation worse)
        same_sign = False
        if is_saturated:
            if (error > 0 and output == self.max_out) or \
               (error < 0 and output == self.min_out):
                same_sign = True

        # Only accumulate the integral if we are not worsening the saturation
        if not (is_saturated and same_sign):
            self.integral += error * dt

        # Update state
        self.prev_error = error

        return output
```

---