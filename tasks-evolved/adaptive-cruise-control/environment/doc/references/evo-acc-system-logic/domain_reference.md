# Domain Reference for evo-acc-system-logic

**Responsibility**: Provide ACC mode selection logic, TTC safety checks, desired distance calculation (time headway policy), and acceleration command selection using minimum acceleration strategy across dual PID controllers.

**Key functions to implement**: AdaptiveCruiseControl.__init__, AdaptiveCruiseControl.compute, calculate_ttc, calculate_desired_distance

---

## 2. ACC Mode Selection Logic


A standard longitudinal ACC system operates as a finite state machine, transitioning seamlessly between free-flow cruising, car-following, and emergency collision avoidance [cite: 11, 12].

### 2.1 Mode Definitions and Calculations


**1. Cruise Mode**:
Triggered when the `lead_speed` is `None` or `NaN` (indicating no vehicle is detected within sensor range). The system utilizes a speed-tracking PID controller.
*   **Error metric**: `speed_error = set_speed - ego_speed`

**2. Follow Mode**:
Triggered when a lead vehicle is present. The system calculates a dynamic safe following distance based on the ego vehicle's current speed (Constant Time Headway policy) [cite: 4, 11, 13].
*   **Desired Distance Formula**: `desired_distance = time_headway * ego_speed + min_distance`
*   **Error metric**: `distance_error = actual_distance - desired_distance`

**3. Emergency Braking Mode**:
Triggered as an override when the **Time-To-Collision (TTC)** falls below a critical safety threshold. The TTC is a kinematic prediction of how long it will take for the ego vehicle to strike the lead vehicle assuming constant velocities [cite: 12, 14, 15].
*   **TTC Formula**: 
    \[
    \text{TTC} = \begin{cases} 
    \frac{\text{actual\_distance}}{\text{ego\_speed} - \text{lead\_speed}} & \text{if } \text{ego\_speed} > \text{lead\_speed} \\
    \infty & \text{otherwise}
    \end{cases}
    \]
*   **Action**: Command maximum deceleration (e.g., `-8.0 m/s²`). PID controllers are completely bypassed in this state [cite: 12, 16].

### 2.2 Mode Blending Strategy


When a lead vehicle is detected but is far away, the ACC must decide how to blend speed control and distance control. The most established and stringently safe approach in the automotive industry is the **Minimum Acceleration Strategy** [cite: 13, 17].

Instead of a hard boolean switch between "speed mode" and "distance mode", both PID controllers are computed continuously in parallel. The overarching system simply selects the minimum of the two acceleration commands:
\[ a_{\text{cmd}} = \min(a_{\text{speed\_controller}}, a_{\text{distance\_controller}}) \]

**Why this works:**
*   If the lead vehicle is very far away, the distance controller will output a massive positive acceleration (capped at the vehicle's max limit). The speed controller will output a lower acceleration required to maintain `set_speed`. The minimum ensures the car cruises at the set speed without violating it [cite: 17, 18].
*   As the ego vehicle approaches the lead vehicle, the distance error drops, causing the distance controller's output to plunge. Once it drops below the speed controller's output, the car naturally and seamlessly decelerates to follow the lead vehicle [cite: 17].

**Full Decision Logic Tree**:
```python
def select_acceleration(ego_speed, lead_speed, actual_distance, set_speed, 
                        time_headway, min_distance, ttc_threshold, 
                        speed_pid, dist_pid, max_decel, dt):
    
    # 1. No lead vehicle -> Cruise Mode
    if lead_speed is None or math.isnan(lead_speed):
        speed_error = set_speed - ego_speed
        return speed_pid.compute(speed_error, dt), "cruise"
    
    # Calculate TTC
    relative_speed = ego_speed - lead_speed
    if relative_speed > 0:
        ttc = actual_distance / relative_speed
    else:
        ttc = float('inf')

    # 2. Emergency Mode Override
    if ttc < ttc_threshold:
        return max_decel, "emergency"

    # 3. Follow Mode (Minimum Acceleration Selection)
    desired_distance = (time_headway * ego_speed) + min_distance
    distance_error = actual_distance - desired_distance
    
    speed_error = set_speed - ego_speed
    
    accel_speed = speed_pid.compute(speed_error, dt)
    accel_dist = dist_pid.compute(distance_error, dt)
    
    # Select the most conservative acceleration
    if accel_dist < accel_speed:
        return accel_dist, "follow"
    else:
        return accel_speed, "cruise"  # Technically cruising, constrained by speed limit
```

---

## 3. PID Tuning for ACC: Practical Parameter Ranges and Methodology


Tuning PID controllers for longitudinal vehicle dynamics requires bridging the gap between mathematical theory and physical comfort constraints [cite: 1, 3, 19]. Given `set_speed = 30 m/s`, acceleration limits `[-8.0, 3.0] m/s²`, and `dt = 0.1s`.

### 3.1 Tuning the Speed Controller


**Goal**: Rise time < 10s, Overshoot < 5%, Steady-state error < 0.5 m/s.
**Constraints**: Vehicle starts at 0 m/s. It must reach 30 m/s. Max acceleration is 3.0 m/s². Minimum theoretical time to reach 30 m/s is exactly 10s.

To achieve this minimum rise time, the controller *must* command the maximum acceleration (3.0) for the majority of the acceleration phase.
*   **Proportional Gain (\(K_p\))**: The initial error is 30 m/s. To command an acceleration of 3.0, a \(K_p\) of just `0.1` is mathematically sufficient (30 * 0.1 = 3.0). However, as the error drops to 10 m/s, a \(K_p\) of 0.1 would only command 1.0 m/s², drastically extending the rise time. To maintain maximum acceleration until the error is very small (e.g., 2 m/s), an aggressive \(K_p\) is required. A \(K_p\) in the range of **1.0 to 2.0** ensures the output remains heavily saturated at 3.0 m/s² for 85% of the acceleration curve, yielding a rapid rise time [cite: 20].
*   **Integral Gain (\(K_i\))**: Because of windup clamping, high \(K_p\) will cause a fast approach but might leave a small steady-state error due to drag (if modeled) or digital discretization. A \(K_i\) of **0.1 to 0.5** will eliminate the steady-state error. As indicated in the literature, \(K_i\) has a substantial effect on ego car response [cite: 19].
*   **Derivative Gain (\(K_d\))**: High \(K_p\) introduces overshoot. A derivative gain of **0.0 to 0.5** acts as a damper.

**Recommended Starting Speed Gains**: `kp=1.5, ki=0.2, kd=0.1`

### 3.2 Tuning the Distance Controller


**Goal**: < 2m steady-state error, minimum distance never below 5m.
Distance dynamics act essentially as a double-integrator (acceleration directly integrates twice into position), making them highly prone to string instability and oscillations if tuned aggressively [cite: 13].
*   **\(K_p\)**: Must be lower than the speed controller. A range of **0.1 to 0.5** translates a 10m distance error into a 1 to 5 m/s² acceleration correction.
*   **\(K_i\)**: Should be very low or exactly **0.0** to prevent low-frequency oscillations (string instability) commonly seen in car-following [cite: 1, 20, 21].
*   **\(K_d\)**: The derivative of distance error is effectively relative speed. A strong \(K_d\) (range **0.2 to 1.0**) provides excellent damping, anticipating the closing speed before the distance error reaches zero.

**Recommended Starting Distance Gains**: `kp=0.3, ki=0.01, kd=0.5`

## 7. Common Pitfalls and Mitigation Strategies


When orchestrating a continuous physics simulation bound to discrete sensor logic, several mathematical and programmatic hazards arise.

**1. Division by Zero in TTC Calculation**
If the ego vehicle and the lead vehicle are moving at exactly the same speed (`ego_speed == lead_speed`), the denominator of the TTC formula is zero, causing a `ZeroDivisionError` [cite: 4, 15].
*   *Mitigation*: Preemptively check if `relative_speed > 0`. If `relative_speed <= 0` (meaning the lead vehicle is pulling away or perfectly matched), TTC is theoretically infinite (`float('inf')`).

**2. Integral Windup During Mode Switching**
When the vehicle is in "Follow Mode" for an extended period, the unselected "Speed Controller" accumulates massive error (because the vehicle is driving slower than `set_speed`). If the lead vehicle suddenly changes lanes, the ACC snaps back to "Cruise Mode" and the saturated integral term causes a violent, unsafe acceleration spike.
*   *Mitigation*: The controllers must be systematically reset upon mode transitions. If `previous_mode != current_mode`, explicitly call `pid_speed.reset()` and `pid_dist.reset()`.

**3. Off-By-One Errors in Time Arrays**
Simulating from `t = 0.0` to `t = 150.0` with `dt = 0.1` requires exactly **1501 steps**, not 1500. Using `range(int(150/0.1))` produces 1500 elements (stopping at 149.9). 
*   *Mitigation*: Use `np.linspace(0.0, 150.0, 1501)` or calculate steps as `int(total_time / dt) + 1` to guarantee boundary inclusiveness.

**4. Pandas `NaN` vs Python `None` Logic**
Python's `None` cannot participate in mathematical operations, while Pandas' `np.nan` is a float but evaluates as `False` in equality checks (`np.nan == np.nan` is False). Comparing `csv_val == np.nan` or `csv_val is None` will fail when iterating through rows [cite: 25, 30].
*   *Mitigation*: Always isolate missing-value checks strictly to `pd.isna()` or `math.isnan()` before executing any floating-point arithmetic on the extracted sensor logs.

**Sources:**
1. [aip.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHC0JMFuVK5LZW1qgvprZBA4LQ3bwCGiOYhjqsX_AoXHf3BE1Pxkxg7V4jTf5cYR-Mkv4Qt5P86C4R9LovjNsSf-CX5_ctsHI5zvR7gpX9num_s0Kte02ouoC1LAO7c28OW-YGbnF1eGm8GwA2e4tLH9X1Ie_tIZIf3gsZLTxmtuAIlDTWh-JHqK04CfVt09mEYk8-N)
2. [patsnap.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG0t5M36QaNHBnCdoOy2ChaSKwSnfArYWf_FJ2YhpwGve92FWzJy4Jnom3ZI1N94dJrXZ_OUl2Sr8EYyOHtHKQCVj8bF2kzLlN1TyFjNiPLjaGdMXEJSPhVIcE-KNzc3KLgKiXi1AHKyb50pFPjYnUCzksFSHs8xTlB0lDaOYTq0Bl9fjx2JBAo9ASptjVukz8nlw==)
3. [asme.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEpGJEmiXqbaz-vyKLD6heqUYHJgj8B-Syu0aLSttNXu2SXgFb8UUTFQIrw0khw1rA5GH9UtXjx9ETzSmPZerX17bL15IxAfRamG8jbTDXuwavNLjsow5URIVVBxAx3aY9Fj_H81HlygCi6GzlisCdMpD7Pla7zXtmWvWphXnt9h3OUL4_Mu70y3NJbBSO7pMHpBNt6z7zppdIeH7hS8vvNTBcOdELoboFmzrewsLo5yHrRTTO9QHCvSA==)
4. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEVGac-o76oikOUG1RhE7eamuCWOiIl0IGvue24kZ1Rp3HsDICoz3L4bxtEx8DxLBurIIUc3GSy0_k4JvZCpF7A7YZo8_iyaSENXeQ87U4rzMD9nhiong==)
5. [a-lab.ee](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHk5s9HBZ6fLBQQa6o1lpupeAjGGiBQs4rEGcLJW74pFrjY2ySqnS8agOkSkNocDScnoLu0HhyHoufhZYNbUh-R6uwrS8yCHl1iJGmoXMLFBYD0D9MRRtncJzd3kM7_Aobg-MJQkMoo4BkF_88mVcLaRIiCRw==)
6. [embedded.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFj3PA6QvLfwvTMZEArsdhJgjF0UaBifqbWtHR5wL-4cgghDB9PJDNH9uvZ16Zv5ltOOH4lmFKI9GIsoR3un8-6mVzywBPrnriAUdP30dDDModTmwGcuFDluZR3M3EVLSlh1vsWYNNffSTgIH8u6MsUKfLC9fhTNGkKgx8=)
7. [erdosmiller.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnzRvVQPSMSkmPgPWczDe76iFy4YlIgXwEDBN8RKz4q9eHjo4h0juSfFqzqm333n38YKDt_ysirl9urZT5d6emik-8WzqWswPMglkxjoh5LkLeUowui-QX2_AeY_IbUsXPpXYTNjFIYjj6OoZClTmUemY=)
8. [scilab.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEE5oU0mSYrmHQrn0GM1bQHc8ePpCU6BA-BmAibKaH-KZIz91q3y1Uo4SXEKRPtjVBL5SV2VXIsmrA3iwFGj_kMdOXEcxBp3r3tWKNqo7ImDbYXyLKoJ_kpct-xl1Og8Fh2EoqQ)
9. [industrialmonitordirect.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEuvnaiv1vhvS4bja1wg8THU-T1QSx5f0tiCFMwo1591dN3T2pVE4q-4LThzkZLgKZSc-HsSasz_vI__IuhjlsK3_-auTbZVoGLn39VUEkafOU8S5nzK0mRD8p0gKFoBzGvyjTJCVqFWtS617D201HpYemgd2MzqI0_WvsIoNTWGzYNxPsdHIF8Jcc9VKxtaCPC4qaz0983wDt5tda5iC5rFmtbkXEnMXrkxhk=)
10. [mathworks.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEn7EBKyACmwKDfCb2UUBAIunVH5T1YNBozXeadS8xr32SqHZE9cYuh-mMtXSgtyRtl4kPQAoYNFAS81GNYOhMGnevdmzHi8_JXA1d7B6MYYCJk1bv6ZlHmKH2cLbUvM9BGaZIBgY4HfrPSOnSB2LQbR3zfkZSUSAs5AxwlJgEEdATPcvV5ZpiiAhiaZ32FavVgNEE=)
11. [tum.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF6-077YCQSGZWzm8Axtqqw0EDdmOTuLSy76zuuicsFoNJyKVNg7arcG-nxmeVTHTm8uOKuZUhiE2sGycMnnFOMk-voOHqO_TB6syK70XhScy96-T0zQFFFnJ0ibFMt3qBOVYbOf18b)
12. [tsr.international](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEOvBWEIcm-GrDV3qppmXRrM5nEI-gQolnkK2jGu_Fcn80MGuhg375bTUf5pUUzyTyhAJeVO0HMpCwYaePmd_VDuI8jIBhho0UGWkMrGiFiy_8Vp59pGo4WcQP9wQewwyooOcjrGfdh0jr2Fq8=)
13. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFo41ich5irl5Xg7Vmy5Tsy1kkMavDLW2bjFIxqipsg0zL28MXUUuzFSiqEd8T3W4_Eok26KQVjo1_87TnD6zvzebEa7u3fjX2Qqu3w3Fjem_ufAiwxCKhIkGfoFI1UpxU2YQLH3TeLUN1jTCQS0ioTWwtbUKhPHu9mIXU2tLxF539OS7CeceBS2W0AOSwJSv5sR8HWqZqTjKtLV23MHQl27yhNmpi8jT0yf4eAXiOxTOdiTLA_p7cHFc028A==)
14. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEZRssY6AAm7sMujk2OdpJ_XhS0pUiJTviq0COYQCTk_mhhKLmIlA86IQflBRJ-zqVOGP3EwspRqpr8l2y9DswUcDWFDi60Aeq6Jk4fhqr0dcEmd6Wl-nR6gfIU5JT1YK1WmQVCw5GIYK_HpuWGmu8bfkYzJbYtvP8z7Def3sz9IkFzpB-IxJypIrUYshodho-3PWGp03PQPJ6r-tNOMcRQVqNO-qm8NlGX8uquLueagOBX85-j_kNmpM6O7E4SzuXxWpcHB9iUB45qgNIf033NqMtXx5FSoxu-W-9poR-GYAngMSmV0HTebnDEGw==)
15. [leeroopedia.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEOXx579ciE6UCGJ9Ep7kHAxPd5kAl3VorWjGdKWnwR2Cx-Dqiq0djJCp26xFslLmeMvc4Ot9ptv21TA6gNeEpyQ-J2C5oHlGvQ80NjiwpRPJDk5qxg4hNZJ_M8PeNhLZgTHY8w1NwxObg6IrocjqBchbvtQy-jzwUCu2BWBa_KEYHP-LR9NwVeXqeayMRgd0qA5qfJq7maM7cPIT-c71--)
16. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE_AVwHdjRi5r6dTh5j5szumggaz6OCEqHMyFKgpdJDJ0m_gB3tK8fBYtTjMNXuPk8KZC8_rbWoHy-EZsvHP0mwxhtn6o8DDHgF1yzVS4roNKVgqEvVlH40n2i90CVaFl02u2Hcwim5UkWSSL8u068RVoyM8WVBV7A9cU0RRAWa5nXunkvGKU23Dj3mZ2D3GNNbMP5hQCXfSWZ6tFQf)
17. [lu.se](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHrP6p6fSV3ajOI-zU9vS-9BSwIe7iiqV2PJMec293n9SckrCMPg6LmptyRmsFoDAMGJinT6XENwA6Lo3o9W8wPJsunG7lQtemu4m3bk6EpZtVvkJlvpIYfNdY9xgfK6kh4BfJyz_y75SwdiZ9qwlEhykV2x0WZ_g96wfv2g9_VSdEz88KcOZHR_oMu3BA=)
18. [mathworks.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF2kVojgfomgkF9RdRrabLLdcCGkl6086n63aNnCZktMehYkfmzmHrJJOuhGNngnqmR0HNmfiMUq7psyya07S2WX_md5T0tfgpOiTsXtAbYqivJ0lqLwpSJdzmoK-qevQu5BV_v7oO0elNMpaAQVYkasWMR__lr2eBQ2DxGCrVNghr12WltLoZdRTER5Na3Aka5QyhaGxmvjQFcMDdl)
19. [dergipark.org.tr](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHCuSM1O3068ucBjf2x17cdCj_YXNjmGRSiYNDLGOonGlnmK2MzhRT6mNYWcgXeOFdZD7h6E-CwXmENCh-v4Rble4GHXfu6oR53vpsElVNJTU6q8XvUC_c0Y7jzrR6gSH4RGRVY-j266n_0Q4wdrg==)
20. [core.ac.uk](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEEACtUGQXLcFAdkH9QLtYDlfLeihzU7n7KdLyn5RJPTJkL4aOC49MxS9mcROB8zqawnbf9SRjyh_gYsIY2DZykkDYXtfhC01WSu0Uho3GVJF0kkDE-0Wtcb_Eu0ODn8gVy23k=)
21. [taylors.edu.my](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGtgL8ocaPBuTsDlWlywKUvR2_UQHuWyRKKTnK5S49frtyAldnfe_2VJoYClxh8cUHpK7MH7UJn0X_XsDqHasxXX0SdHB4XnVVDg92UOErIuyCHwgK4Pzk9nrlqCGNxaE8Hv0KXfAiGly8v3ZMnASF6NERMc8tM5xkGXTvn1XzZqsN-5s12jw==)
22. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFiWVe18jrzBmYpfg1a-o8dj3J077ekio7AtmApAbcdtKD0-HqquXgQqjzQGhLU69p__NBr20AbCRvpurOOnbG-HFzLszh2nmxmAy0q-fgU8u60lbPZFRP-87S7qg==)
23. [lobehub.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHfH5HgY-UzqVvK7Fhy6zi2Ie2Nx4Ktkzpd3DzoqHun5mDd1FKcY86tCMdkdbWZpwT9m7753MCFzsVSXJlMZ5_2o6XTl2SNwgZ6QUhlwBfvTcbqAc1LDM-pnOMiEihFsVBYZilv9AJPsstZ5QZl-0IvXLsTVURlWXUtMg==)
24. [mojoauth.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHGLRXh_hqNFkS6mB2tG0VJF7ak5lPpcqIXzV8X4P4CbfrwctXnmoZ_5B1tlnOgCxq0X0IMMtOc3FtG4Jvoz-FrG0HomjgFy9d7ai_ImiC5izuoedlaDWv_DiWFwWXoYn15DYfwFqp1v-hC_J8LZMBeL9HUGoP8PyIkit0iG2B4WM8HpupU-vid2lGn0OcK_XASww==)
25. [codemia.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE4EEtyqN87tlk1j90ikGBtPdxVsdtRVJaYAxxJ-SwKwdmjlnwcK2Xb33oZxp15aGk6RyTXbn8okIxiCMriJ3Opf2wyFVBLyf4zqmb7t7YUMiGOk0UvRWcE7rR32hN0Wc7wjW8U2PZFpdwgq5yiZCO_jJ9zxHGvT5Ym9TUPzySHiceB2Hkat2VwO8clG3kJEBmnWLquDojqjsxe-uxFQ9bK8uM=)
26. [nkmk.me](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQErICR3gDUFEGOe1GDIWHlrDt72zE92-u2NbP-qfFqhtTiriTvQZKNtqK6RDPIqvywSlkFtwMmNTLGeXnd8LQuZO8CEG8GugD0ToZBdafSXBojQG4PLP0ThG9hCpVXSb0TUtJs=)
27. [digitalocean.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEqEFeZbOXrKW6P8VIV-mU_RuaH9Q_zIy7iMEZ80huH3cMyyDX4odLwtp7OfKjfxqEhx3WioZwVk9Yn4UlFeEFonoVJDAwWyOmem5R964NQLutQZCAU2h3G3AHD-O6HPtXyK6MlmGVX-3uZHtzxUE8lHyZsG0IagH1WEzhFmnN85bBF2jH6LgwiE4EeGMg=)
28. [medium.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGlATFTnBrJSKKClFJetdhhrWA0g_Gwu8kpOSOJ8oKEQUraNpxs9Q5L-0j-or38GDasR-ieXe9AK1kQQTonVq9VkDNyb6D6pwuUvyQzQQ76ZgM8WTo4zorjLNZdnOUUhHrZeXr0ltWnz5gpM6UHtAguMfi9N3Zo_JwmVzF0vgC_G13LfS59zWWYWsUr)
29. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH8pebKXCpvkzwv5_-0WkGJhvpsybuqdgPhtgW1ZqFCfUE1HOu4fUzRMURX8I24P5Xdns1IVQa_qjQml2fnZ4J1wux4uG9v0ToHUP42i4pBQUqLKsTX4IVzJZmSLYHItA==)
30. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEIbUCw94s2J8B6flPMMeIDX9z-aRbOe-zp7rVDTdRBk8IOCaU7_K6DFYz327YXyReTCfXgSurb5hjTmtHuFRNCgB2Iuyz3glXvuABXYqBwPHp16x-_7gxh66FH-r4zh1dgy2lNIFKHI4QE3gSt4tGmsA39vdTzXbfzIj40jc6nBVxEVAII5yQ_M4OauXRNaWCqYWx5-FkRfE9P9rENfAFbfU0=)