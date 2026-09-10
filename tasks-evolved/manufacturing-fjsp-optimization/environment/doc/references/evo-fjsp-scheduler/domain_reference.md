# Domain Reference for evo-fjsp-scheduler

**Responsibility**: All scheduling computation: finding earliest feasible start times considering downtimes, greedy constructive heuristics (ECT), constraint-based schedule repair respecting policy budgets, simulated annealing local search optimization, and schedule decoding from OS/MS representations.

**Key functions to implement**: find_earliest_start, greedy_dispatching, repair_schedule, decode_schedule, simulated_annealing_fjsp, validate_policy_budgets

---

## 1. Problem Formulation and Mathematical Modeling


The standard Flexible Job-Shop Scheduling Problem (FJSP) models a manufacturing floor where a set of independent jobs must be processed by a set of available machines. Unlike the classical Job-Shop Scheduling Problem (JSP) where each operation is permanently assigned to a single specific machine [cite: 11], the FJSP allows each operation to be assigned to one machine out of a set of alternative, eligible machines [cite: 12, 13]. The processing time of the operation is dependent on the machine chosen.

## 3. Handling Machine Downtime Windows Correctly


One of the most complex elements of pure Python scheduling is the logic to calculate the earliest feasible start time for an operation on a machine, considering both previously scheduled operations and fixed downtime windows [cite: 7, 15].

## 4. Scheduling Algorithms for Python Implementation


Without utilizing solvers like CPLEX or Google OR-Tools [cite: 7], we must rely on heuristic and metaheuristic algorithms that can generate high-quality solutions within the computational budget (~15 minutes).

## 5. Policy Budget Constraints


In production environments, a complete re-optimization of a schedule is often highly undesirable due to the physical setup already in place (e.g., tools loaded, materials staged) [cite: 19]. When disruptions occur, schedules are repaired using a limited "Policy Budget" [cite: 6].

## 9. Best Pure-Python Approaches (Within 15 Min Compute Budget)


Because external solvers (OR-Tools, CPLEX, Gurobi) are restricted in this module's setup, pure-Python optimizations are crucial [cite: 7, 8, 17]. The best approach for high-quality FJSP results within a 15-minute Python execution window encompasses the following strategy:

1. **Greedy Initialization Population:**
   Instead of purely random generation, instantiate your initial population (for SA or GA) using variations of the Greedy Dispatching heuristic. By sorting jobs differently (e.g., Shortest Processing Time first, Longest Processing Time first, or random shuffling) before applying the Earliest Completion Time rule, you generate a highly diverse but fundamentally feasible and fast starting point [cite: 19].

2. **Efficient Data Structures:**
   Python dictionaries have an \( O(1) \) lookup, but the constant overhead is higher than list indexing. Where possible, represent the schedule state using pre-allocated lists (e.g., `job_completion =  * num_jobs`).

3. **Algorithm Choice - Simulated Annealing over Genetic Algorithm:**
   In pure Python, managing the crossover operators of a Genetic Algorithm (like the Precedence Preserving Order-Based Crossover or POX) requires extensive list slicing and validation, which is computationally expensive in Python [cite: 23]. Simulated Annealing requires only a single state vector and minimal memory allocation per iteration. SA with efficient neighborhood moves (OS swapping, MS mutation) combined with the optimized `decode_schedule` routine will yield millions of evaluations within 15 minutes, converging to a near-optimal or highly competitive makespan [cite: 2, 19].

4. **JIT Compilation Alternatives:**
   While not part of the standard library, writing the core `find_earliest_start` loop and `decode_schedule` function in a way that avoids complex object-oriented overhead ensures maximum speed.

By adhering to these patterns, a Python skill module will successfully parse industry-standard datasets, rapidly generate feasible machine assignments, seamlessly route around machine breakdowns/maintenance windows, strictly enforce business policy budgets during rescheduling, and output validated data structures ready for factory-floor deployment.

**Sources:**
1. [utep.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHY1KS1uKt4VF78VsKKwAMQHWM-6IKwta0aQidBhs8y7h8i9JuS8Fk_WQ2viF_a8sV_vo5flWAsdtf8vKTCL_lc1UYAab8Ndn81dPl1hpSoXlVmGhF9mddVsHnXgymNAzrlxajpmkWdqWrQP0DWCwPTomdJMQzH00hn7AZ8TYnD65uYqvpt)
2. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH36ITLsoBw07nu1OPG2gAb6Z6CmFlC4x8hX9Qe0KQEsr69uTQOBA5v7eVccBLMevlYKoTzXTETvv5C10Cc5Y2GPFq_ibFXaU1Q4uXTPZYYKtJVsAtX6w==)
3. [eudoxuspress.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF3S0P_EE9fLCBsQ0NB-AIULqfKtHUTlJQr6RWnjcc-8g7dunwe_S17_Re1EAKCdKwcOzAanMSoxbd0SSupzvPyxHH-rHK6D5XwlnOPDIqhBi9EqpGsRDO2p9Qo1lOR7nfJJnjnIySQF6YbRHjEMdzj31Sx_aSlxwP_hqOijW-dFA==)
4. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHPYPWh0RKSlo8M4POsRX9mK5ZtnyOxS0fqxFQ78Bq2WYjo74SJCKapco_UclBpOv2TaKxGr6ruXCdfiAr6EPnTWYhKOoKcMudKHu0QurQIEKd4RAPh4MredLZjeT-TFQzHxQQAiK6YyiDo0caQpFckfQ_mBCrK5BI=)
5. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHjBAQM2Gyz82jU2MYb6oeEjh7JHcMJV90xy5D3aIIKODZCnd0r70JK58YFadsJWWmsiVlyd5HmMHqR2l5o_UP-JiSIJ29qzmRQ-PDucNzthTmxvw-8-LD8ERuaq0EbaBDf98tEFmqmP1IBV9xFqgHcYsaxWHHLG5Lj0hb_GZXGHM2CsYyEUryt9wOOxUt3YW_ImcOpnjxwaTEuhwjnxajwconcH7G6ICj2cnJM_RucSHGTWAxq8qrmGixkKhdOPUJTZ5oVBw==)
6. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFCgGaFcVsBR--eM1pgPvFQCGTQ9C86Y_Fft-k9SvG-oaVJoVuk8sI9MJIsQmA2wioE9LX6LLiAtoORzS_Oyx0h5sGsGnbPE8gkDjPyQW_YBAIPqRTA70TCTDNuk76WlgQ3g-F07nUbXqVKBAAib0xcuc-VTYnOhbnCz3BZ5SBrv8kYlGJGnF90jPQsuGdc3NkjWzmsQNQhnjDtWIqmLUvUVSl_s8lAi5F4p6sZb5z1pC7KGFSLyQb7LhkraYppw_ShNf_Yz7LygJ88X_g8FcI2YI37aAciIzFbXXbw)
7. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHaaGwg-MYjZpzMlsxRZkGOZ2VJ1ylbmqc8j08Q-6tqOiiPNphyZkp0VWNnqyttmxW1Ho3O5LYv1A21_4hUsAUqK1xqMc0_Iny1g1ETQ9i1hg-lzfP1uA==)
8. [uu.nl](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF7B_RuTrr2gyx5lORq9gMCPMMVky90z9JXqfdAmDOBwbCnbkRyS9cAmjYyA4b0V0ryD2F4RaUvNeioj7zQs9qxFct67huiFz_G5ySSktNxx5MVQ8Lc6oqNZJNp6Tk2fgqkPveO0BraBIIJuXMbqZ5x9mC8Gpljj-9JU2fgK48u1Uf6Vv25u3DaHfvn6WkbyW6StxQFJvd7leOIobPQtp8OUyaUej2zB5NLaoeaZkmwE4PR)
9. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEKHUdSpjpfUdHNI0NzgeXARvFvcssGcwHUBznCM-GaOKTR8yAhGwmjeGJBcJuvx46ObbyGThsLE5S4uSA-Pq6kef2AUq2TlVTFWMlxVT8KRGxjfwnj0ct1Ncv4jWSIBSNDfr5Ksw==)
10. [hexaly.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGf45-giw9bu0M5X3upaS_J1UivWc6E3X0_NzpKJIFamqpKHbSSVmt06YOSFy8W9maQ3nOjf2WQLACi4jNcwVR_PlelVbprIMqKY3ZUxWZsfCPHaV5yndgpJ3DwshXLunIW4jVoiHw9CcfEsi4naqvEUWIVn_c=)
11. [arxiv.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG6d_tNoi9CXGdXeetkmlX_ENl5d2ngqFDJoB3ciEWB-5DCVsbWIhDT47mgQQdpb3BiwcsKReCAmVv8IK_Gl6qJTo-elq98ecJZPcYaaksfsEUR_cradw==)
12. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFhZt2i8A9oHEPCTnXliR3nNVKPzp-WbmTlSSjZcVtOMhO8pi7rkon4QC8ciUXZ1ZF5hYXuDN3pqaYVSv44EILQuBJCMl1ywJpocnRrXjj4panw3cfEfbJTKf2b9sC7)
13. [nih.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG0qIjYFdSGRntzNl_JOMbgoKu3uLnsFlTE4uUBp5RnxCURC3JaiEHuUua_n_u8GJbRXBjH2J-KzjL8Rxg8KS7YSLXau8WRLndDvQxpF4n5Mm7FmhEwrH1Hz1ofX9caEQCLNwPOQCE-AA==)
14. [waset.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEg0Fd64JB4kc9AWo-jLDe3G_Uy_jLa3SMAMUQR8wnoRj1BH8MFtbxNwCADLcxKkLnWuWbi_0aWTfVljow_wp7pSZZK2uCs05YnB_889tVhsfLowpgJ8F5l_exvYK7OchUHqoh2hD_5cMeTmlJwj6wiv80nVRk65DGxCO__IWbPgcg32v_Evsnlk8MNGPwZ_uxfmMiXj-vNcSabopF8J2Xe1FHpsJ3kOv5dbXdXfyvF)
15. [stackoverflow.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHNiQEFa_6qTmagc1EIAErVLAIpcKjEXcSR4YYinTV8-rmKaCLveSS2qRNLt1aYLf-I7wddwer5-MBq_smhYRwV26NkJTCMC8bSWKhBV49tfy93lXgDjmeP-CoR32kbEttsRjrqM34GbzH2nw_VrfPhFfjzwvouoyPa9GdF73L7twTjklAsT8b5p0SsWEty3Qmxq79HRhaVntgByC1kthI=)
16. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGMmPF4t91O9mRUurmsl40mss-RlkZaUXKlrZVfKO1U31haZBsdOQZ3T5BINhBNJ51Y3tWkV0dHGMhxz9LP8nUEUWJEtxkS8cu_Ta0PWb9IT863Z-dT6_ZGro4A0ek=)
17. [hexaly.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHZosZ4U7TSk65tSccUHoTKXTxf5u-E7lXzOZSZdLZkcUtmaW82_iafLHSRIo_SEnhVkvwI2WH67g4Ilxh-ZYrCdQPNXPRuRGyJ1A3XtvCqSjA0ghyVJCQVR7xhZtXc-mjuUdb_BCjF8PLaYEkOsTy2uppGB-pTWkEekgd8ErxIjqD799mKksa0vGCNB7si6TVt6w==)
18. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHBl9nZowfbDGGVSA7oaFBrwb6H5WX8ZtsvQa7TnX_BgVntUqCRjp4KTihZn1ldNGwhNCeTBRXb8bBo7nAMBsBF--w2DEn6VFLCOQ5kgGks81ldHD2N4mmp_TjPp6A=)
19. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEmTjT3XTOnbPT-VThSCtCBn3qKXrpDCZ3jajAys59LwP6xRdufb4bat7nGTpnVeBYRNnmoWaz3kThfxH8rciHhfot3XK_zhXA1wxYjkU8J_bW4I4I49d2K0mOUPnbW7dTOPQmb6vZHLl_hzxBI3bQ1WsmVYnWXPI_RJ2GgbR09UtUdI10WX-pCN940sms4epniyLm3itK3EPgo2094FFCz-fShaBKmPHrkMNDT7YgXaEjikRCsxvvGYf-i3BwM7zoNMSCBnFpHXL8yzYGVabBO4Nz-zODrlg==)
20. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMfUzKasULwfpokPLg1tHZhY1PNzIhIRWu3327TXY2YvavlOr_Av5NcWgxnui-JfodARIBEO3qmTqsDAj9i-ifYQE64yjGyIZ562MbJRY0Wyz_0VvsrGqHKm920iMJx94-tZPQgaE=)
21. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHb_0c4B0DHy4BJ4havdDuPiPbo5R3MZfNYs7bX3Btl2Mzud6FXwTO35WpGSskPLRm_dYe-dRZt9wWYbM7GqE28BQkUdcwhyAW5H_1Wp7-x7z5fDfd_MpRo9WPnxFSM)
22. [techscience.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHgfEwEUWPKf62Zg9renlti7o21VS_0o5Xgm_h1kStHqyXVMwtPe6rmhr4MdU90_TVrLzYaPh14Ie6mRahCErIFKgg3xYmz5594YXS6TYUSC8Gz8vSCRTyMNquKd95D9C9EaS929Q==)
23. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEZaWL_HW-MMv9VxOv79vQJqstnnndg_0Iv96KBjDXvJKKztRzejkSLs5F3qurEOV7q2Bqe_LjF3zaRyoDw3oIyHQMWIWs0b6a709nTpYGSIHeRWdrvVHEFWHfPX_I=)