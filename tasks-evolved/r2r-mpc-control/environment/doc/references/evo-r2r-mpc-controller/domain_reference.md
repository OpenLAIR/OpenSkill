# Domain Reference for evo-r2r-mpc-controller

**Responsibility**: Build MPC prediction matrices (Phi, Gamma), formulate and solve the dense QP (unconstrained or constrained via scipy.optimize.minimize), implement the receding horizon control loop with the R2R simulator, handle the reference change at t=0.5s by recomputing steady-state targets and re-linearizing, generate controller_params.json, control_log.json, and metrics.json output files.

**Key functions to implement**: build_prediction_matrices, build_qp_matrices, solve_mpc_step, run_simulation_loop, compute_performance_metrics, save_output_files

---

## 5. MPC Implementation Without External Optimization Libraries


In resource-constrained or specialized deployment environments where advanced C++ solvers like OSQP or CasADi cannot be installed, standard Python libraries (`numpy 1.26.4`, `scipy 1.13.0`) provide sufficient mathematical breadth to implement a full dense-QP MPC [cite: 13, 14, 15].

## 6. Reference Tracking with Step Changes


In practical operations, tension references are rarely constant. A process recipe may demand Section 3 tension to step from 20N to 44N at $t = 0.5$s [cite: 3].

## 7. Tuning Guidelines for Q and R matrices


The diagonal weighting matrices $Q \in \mathbb{R}^{12 \times 12}$ and $R \in \mathbb{R}^{6 \times 6}$ dictate control trade-offs [cite: 3, 18].

## 9. Complete Python MPC Implementation Example


Synthesizing all derived algorithms, the following represents the core execution loop architecture using native SciPy for an integrated MPC cycle.

```python
import numpy as np
from scipy.signal import cont2discrete
from scipy.linalg import solve_discrete_are
from scipy.optimize import minimize

class R2R_MPC:
    def __init__(self, sys_params, dt, N):
        self.dt = dt
        self.N = N
        self.nx = 12
        self.nu = 6
        # Assume Q and R carefully tuned per Section 7
        self.Q = np.diag([100.0]*6 + [0.1]*6)
        self.R = np.eye(self.nu) * 0.05
        
    def prepare_matrices(self, A_cont, B_cont):
        # 1. Discretization
        C = np.eye(self.nx)
        D = np.zeros((self.nx, self.nu))
        Ad, Bd, _, _, _ = cont2discrete((A_cont, B_cont, C, D), self.dt, method='zoh')
        
        # 2. DARE for Terminal Cost
        P = solve_discrete_are(Ad, Bd, self.Q, self.R)
        
        # 3. Form Q_bar and R_bar
        Q_bar = np.kron(np.eye(self.N), self.Q)
        Q_bar[-self.nx:, -self.nx:] = P # Apply terminal cost
        R_bar = np.kron(np.eye(self.N), self.R)
        
        # 4. Construct Phi and Gamma
        Phi = np.zeros((self.N * self.nx, self.nx))
        Gamma = np.zeros((self.N * self.nx, self.N * self.nu))
        A_power = Ad.copy()
        
        for i in range(self.N):
            Phi[i*self.nx:(i+1)*self.nx, :] = A_power
            A_power_b = np.eye(self.nx)
            for j in range(i, -1, -1):
                Gamma[i*self.nx:(i+1)*self.nx, j*self.nu:(j+1)*self.nu] = A_power_b @ Bd
                A_power_b = A_power_b @ Ad
            A_power = A_power @ Ad
            
        # 5. Hessian H
        self.H = Gamma.T @ Q_bar @ Gamma + R_bar
        self.Gamma_T_Q = Gamma.T @ Q_bar @ Phi
        
    def step(self, x_meas, x_ss, u_ss, u_min_abs, u_max_abs):
        # Calculate deviation state
        dx = x_meas - x_ss
        
        # Calculate f vector
        f = self.Gamma_T_Q @ dx
        
        # Define bounds (deviation bounds based on ss)
        bounds = []
        for i in range(self.N * self.nu):
            idx = i % self.nu
            bounds.append((u_min_abs[idx] - u_ss[idx], u_max_abs[idx] - u_ss[idx]))
            
        def obj(U):
            return 0.5 * U.T @ self.H @ U + f.T @ U
            
        def grad(U):
            return self.H @ U + f
            
        # Initial guess
        U0 = np.zeros(self.N * self.nu)
        
        # Solve constrained QP
        res = minimize(fun=obj, x0=U0, method='SLSQP', jac=grad, bounds=bounds, 
                       options={'disp': False, 'ftol': 1e-6})
                       
        if res.success:
            du_opt = res.x[:self.nu]
        else:
            # Fallback to unconstrained if SLSQP fails to converge gracefully
            du_opt = np.linalg.solve(self.H, -f)[:self.nu]
            
        # Return physical motor command
        return u_ss + du_opt
```

This extensive framework directly satisfies deployment demands by avoiding C++ wrapper dependencies (CasADi, CVXPY) while preserving analytical fidelity, constraints handling, and dynamic recalculation parameters essential to stabilizing robust R2R mechanisms.

**Sources:**
1. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEvzbRcJAQG5vXXQaSjZDL2y2Ydlh6osr1JAAwDLTONL8Bc5KhqBTfLUo2Cmn6wjZgDoOpEEI5dcb6nfBdJZnDQLUJW44UEjTURX427LlYaS4xHqHuoM9cr)
2. [asme.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWeKDiFf4F-DdoWaIoy55ksMQoZrM7b_2DtZ9mdgefsb0BleL1CFt0Va5tevlfr3Vmzmdiv0fXBjQdVdLcytd03cPa3su_A4av-wQ-DkrhWprVBgkP5zKiPBE8TFcVaBehnHFIsnKu8kdI3TjAeOYu3HMiOhN1CXnb41qiLZKjlI5FRYioRuFPngxIOvuvxlNF9xzP76hgRxYP8Q2IjZ13txA7_TYybxOTTkqLB8kr84H8bdmvndOdJtnM21eX)
3. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH0qWdN0LT_UI0eteO-MMJpulqBfWNTc2pS9oyDNp16OOGm2qjbdI_f00SrfMjcqQ3DFITGOwO6yvsj-v2wNnMxUrH5yRMfxs38QSZUM37p99xKKKvPlzoB)
4. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGX-YCqS4Z18sInSX8WYQtIYZ_vXcSqCMfCeU0rYfj5CIwcXvAPr-ERUO6dE_NGl7YUarZU1QvBpdSmjFbaoMnUvrAM5qlnNSrF3c-C88JaD-xCdnA-V2iN0_knnhhFUHIkSCf4ceX-V1UolQAnW_OdShbs2XRAcNCEOO2XZKnZpAnm9FPGE5Lu-pdICs0lEH-3_pQE7z9oVviVg08tynIrLrow2Sv1HeNebPwSqPfzW6aIKaI7rQczOpzbQqzgS_swo-rMj6qZGug=)
5. [rsc.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjBtL9OF6dAHb62sWY6Kp3tDZoBd4WQPCcDRqHVUlWOUVyhVWvksgoY5D1mlvUXAS8jn8iFL-oBSfv5BREC1TLPc1vmtDGxq5EqFuIcG_kL1RCNf2cNkyRUL4INdfY27wXEupffoSZyUK4CVPuuYQabBK4)
6. [ieee.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFnpYX__Cmqs8SuUfs-edzVttrKJo4sywrpTvtKb5Okx3mRp0beZV2pzaMk_ZHklSN0vU4mu6Htgwiyu9qCYGaQAGaIZ61ZERK98EhQqTfHxcAivXG-ihrBZNcQ_uNruCUqqOg2Ie8huqRcEMt-1EydcYlv)
7. [asme.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFzwHZ12bJMwPNnrM9bkfts85kjw3d9rtjz6Ed-37r9Vn5v_hazDdeeFXJblzK4DI9sp03ttGPa5r-OJYDe_XnFVkxrzi5vLlh4FKaNEAWqzNFOoi8LcqOKOOZvM95qwx5RRPedip-TkRdCMlJIWZA0rwkQfvfvE24f8FlQsTA6ZF9h-M3Rx8lodsFxhcT0y23ZGGfpcePcYNO7zHk-cVdn4DXN0i1T5VmHsjaVmxfYeStnpn2MxyU=)
8. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGHhkdCqCe4VKpInVmdg5FYZnCK5iyBzNP1annfDsHahmZKNXUwDEoqMCI3LJEABOULzyPz4mYcUavbDQkQWckWgji_eCX55_GPqu9bKeuQ5Shf-mkkzjIM6uw-E0X1YyoJ590vsq7khQgmiWibs-87DQLdvCafbIXSyC0UoyZMjxDZE_Ft_kIQYhZZh8Z_Lif7SLZOI3wf7jWrP7dz)
9. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7kFR8B6nrHqyihqWa1zne373xL60i5_mXCtauaTPGhI06D30JubCOnUTyuxh_JrTWxoXsQRY75_HNM_QeQfwm6IoNEGOG7Pnsk5WV0pTfb0suXfCxRrMOiPvJLEl46YL9OUlahMLNjJySF90g1NbEmaqwxAZySYPBYWPRsnRo0bMnX4610Va-5w==)
10. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHk70nj0p-5b1buXLSLArP8fG4eMsCagqvkc6ZPMAnXbfjeXWhltq0SySWFDAILgiR50wRRVcpH47jJXT629tdpo5yaDW2Bd9jmzDEICkbXErO-oensu3TVS94oHSi5pDQu9Ip4WNtuDN0UVvRiiQK_bAYFtPE5_-ahIWU3W_4aug==)
11. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFKSqfDoubcoFOQ1fBiEiFJsh_YsFDgeH39l-5Uf7DO8gkpCBuu3TfPsjBe70yjHGa69XKwFU1HAfxla0T_7ileyIfgr9yCsV59OOMzi_L2KsvFwhcG0Bjz4_vStMyTxQJ5d9nshqYjn9WNyfTDkWXN5VvFNXWkX8mkb2CoG6-IaVHKgW4Xd2ToXZcVz1YG)
12. [stackexchange.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFbascq_2PwFY-XWC0CYsV4rND8roVXBwVWgmutby_Dy7tljcd83-7o9MTHzuETPC03SInIF_eHfkZmfXqtEFWEr4ZUm4PPHF1oOq6ViPmmhYFL5L-84EsivpVixoIB4LemQhPhXhTFz6rFi_-bQ7GYZFj0diF7PXRanbUTviqjRTjl3qBOP8CMVfUcASMFvj4ajOB1eKUSy6WMbBzn_H8FBNLGRhlZxp2SbEhAbDHd6_XkkjLKv_E=)
13. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGcfW2x_GKQ7JuRanZp4sacdB66MirAsh_YensPhnh3ReCrmwzuc5jxuvEWcci2SfYGE88StrebBjIM2Y0zNjCp9enKkF5Atb_6yrC4TsqHVAXopKzXg2zpoh2NcM75SVJRl_VWB42WjUGH709F9rgrz7KoMMqWWMdbncWdotEAN9IKGtzlfA==)
14. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE2SyjenrDWYUtM6_5YgKr3lL8aUF_adoqLaIQ1RrpAh-h7DHeC5B8Rv1bU5a1bttAvnTq5e2hpdgkmRCRMrUo_qUu51KA7vkmSCQsDaU_nDmzXwqbJKWEfA7USAa6SMRSHCtJwXWAVfl2nd0Sqkv80T_ULcSdLbopU8g6w)
15. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNX9zLMzTrgku8DMYINWWJd6t3v_G73WdBRraUswHfbOMaBjD2P0KX6R0aCgUOJBuBRSsbb_rJNhbRFZsdz6W-EVvCL7GNwhkD-xS_Pt-NpFYm4uG-gaqUmAS9A1HibNkmKSqieJ5H2rvAnChl-puSFWYqRVMcTxwJKLHRv1qNvkQCEw==)
16. [scipy.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGS26jVk_BKIlYRd6laJLbU5zJm27eFg63XHxzSC-MswvJ_-3W-ZKP0UOeBqX9r4OCcW6FKVIymEDCDw61ly0EBRtJBoDdRb-7w4m8HVigBSdzGPj-0sCtZ-NqNwavK52bcszhLjAiGCk_92Q==)
17. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHYhSoG0vpf0eA2Q6-kegidAdpEV54jPDYNlMSQT9O2tpt5OkJdMzPDPwHDeA4Ed-ztL97kyDFqOdM9WwCVjTFgPQCDjhMq73Hj-X0V7MD6WvHARdnCYF4z8TnKFmNSJ8Q7FDGnDs3WMMtQYx2z0XsyIDxXQpd8kxb3HOqxeKSWfJWX7KRS5j6xvYzexCPHaq6RyLGcuRQF)
18. [agnxi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdnW0p6GjuRVw8XHvviWdx3-8xeFJ00tg-fz2FDmNDPzV1nHcJ3pOqdBSonH_nWWT9EOhdLE8lCnujWQu_Xg31bgnjD1IlD5zIjKJ8pI02pK9B2uzOqCEWo7SD_O1IMfpr10CB79oBBfqxlkMD)
19. [asme.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaUbq15VyVIC6cCdPjoOjs4QvHB-mhPqEeRvAuNDN7aV-l9we5lNtKDuMRdgSzcU14-MpesJlPYqe7hTYUhljk4OJiWCiXknTv0u4P8-u90QSk31C78gVHvIBWoykodX7p9WXAAfkOnUqQdV6yWy83M_-9EJBZoGHh0ie62cGnvFGM3bq8nTF_3uZ6RaIosu_hXqBjeShXsGOMH7NutO-GM2JkA0OFaJ0r6IinvwHNgBqL)