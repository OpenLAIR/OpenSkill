# Domain Reference for evo-glm-simulation

**Responsibility**: End-to-end GLM workflow: namelist I/O, subprocess execution, NetCDF parsing with depth conversion (lake_depth - z), observation matching/interpolation, RMSE computation, and calibration loop.

**Key functions to implement**: run_glm, update_glm_nml, read_glm_nml, verify_bcs, process_glm_netcdf, load_field_observations, calculate_rmse, calibrate_parameters

---

## 1. GLM 3 Executable Usage


Integrating the GLM 3 binary into a Python automation pipeline requires a robust handling of system processes, environment configurations, and standard streams. GLM is compiled as a command-line interface (CLI) tool that reads a primary configuration file and produces time-series output [cite: 8].

## 2. `glm3.nml` Configuration Format and Critical Parameters


The `glm3.nml` file uses the Fortran namelist standard, organizing parameters into distinct logical blocks delineated by `&block_name` and terminated by `/` [cite: 13]. This structure provides GLM with all necessary initial conditions, morphometric data, boundary forcings, and mixing coefficients [cite: 12].

## 3. Python Libraries for Reading/Writing Fortran Namelists


Parsing Fortran namelists manually using regular expressions is brittle due to Fortran's flexible syntax (e.g., case insensitivity, trailing commas, array definitions, nested types, and varying string quote standards). The standard Python library for handling these files is `f90nml` [cite: 19, 20].

## 4. Boundary Condition CSV Formats


GLM is forced by external meteorological and hydrological data. These are provided as Comma-Separated Values (CSV) files. Within the utility skill, verifying the integrity of the files mapped to `meteo_fl`, `inflow_fl`, and `outflow_fl` (often residing in `/root/bcs/`) is a crucial pre-execution step [cite: 8, 9].

## 5. Parsing GLM NetCDF Output


When the simulation completes successfully, GLM outputs a binary NetCDF file, conventionally named `output.nc` in the output directory [cite: 7, 9]. NetCDF (Network Common Data Form) is highly efficient for multi-dimensional array data but requires specialized parsing.

## 6. Observation Data Matching and RMSE Computation


To assess the skill of the GLM model run, the simulated temperatures must be matched tightly against empirical field observations.

## 7. Calibration Strategy


GLM's default parameters provide a general fit, but to capture the exact thermodynamic profile of Lake Mendota—targeting an RMSE of < 2.0°C [cite: 5]—calibration is strictly required. For Lake Mendota, which has been extensively modeled via GLM [cite: 6, 25], achieving an RMSE in the range of 1.0 - 2.0°C is typical [cite: 26].

## 8. Common Pitfalls


Building an automated GLM wrapper exposes the model to edge-case errors that are often opaque to diagnose.

1. **Layer Thickness Constraints (`min_layer_thick` / `max_layer_thick`)**
   GLM adjusts the number of layers dynamically. If surface heating creates extreme density gradients, the model attempts to create highly localized layers [cite: 2]. If the physics demand a layer thinner than `min_layer_thick` (e.g., < 0.15m), or if inflows overwhelm the domain boundaries rapidly, the model may crash silently, exiting without completing the time series [cite: 12, 28]. Conversely, if `max_layer_thick` is too large, the model fails to capture the thermocline resolution accurately.
2. **Depth Sign Conventions**
   A frequent source of critical errors in Python wrappers is failing to account for GLM's NetCDF `z` variable representing *height from the lake bottom* (positive up) rather than depth from the surface (positive down) [cite: 7]. Failing to apply `lake_depth - z` will invert the temperature profile, making the lake appear to have a warm bottom and cold surface, devastating the RMSE calculation [cite: 7].
3. **Timezones and Leap Days**
   Meteorological boundary files must strictly adhere to continuous time steps. If the field observations (e.g., buoy data) account for Daylight Savings Time (DST) shifting, whereas the meteorological forcing (e.g., reanalysis data) is strictly in UTC, the misalignment introduces diurnal cycle errors. GLM has no internal concept of timezones; it strictly adheres to the hours elapsed since the `start` date provided in `&time` [cite: 13]. Furthermore, ensure February 29th is accounted for in multi-year meteorological datasets.
4. **Mismatched Simulation vs. Forcing Data**
   If the `start` and `stop` times in `glm3.nml` extend beyond the data provided in `meteo_fl`, GLM will abort at runtime when it hits the end of the CSV [cite: 9]. The Python utility should ideally dynamically parse the boundary CSV dates and enforce that the namelist `start`/`stop` dates fit entirely within the bounds of the provided forcings. 

By carefully wrapping the GLM execution environment, programmatically enforcing formatting and mathematical conversions (like surface depth inversions), and strategically iterating over the primary turbulence and radiation parameters, a Python skill provides an incredibly powerful, automated framework for digital limnological forecasting on Lake Mendota.

**Sources:**
1. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG4jEk7LIR7LNP4sI4UaKu_oXISgvsfDcoGhD1XG25v0N9l6ovtNbyJwfAeMpz18hAF9wgFwspChLFPZgPDesG7y3qJhDSe1E-kWM8y_vJ9dK0Ru1zioIWlisjEt_1L1umQfwlDv_2jiZ4B_wOk75tRPObGFNBnt8sl5uBANfMQNQfJAGEfgld2C-V-ednPG7MoPxoVBgHyTUe1XHWGwCvWIGwTfcpqjTW0UKGW9nTXVZvQm7eb9mm8JKx0wd1YxaQowGNvbxzxdRf1bpcWsOTWCc5oA8bo56UyaOlPBveJb1MnqE5seMx8_0xF)
2. [uwa.edu.au](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEl5b_vg-jDU1SmfUJMzsKVgMEzUlBniqhb4KjTjhmtFHhGUmhcE-SCe4blQ6BVbMJCOGShuJ3IT9dKgIw-1RghnGbHdDw5MbbMWuZXhwaEt6gNr_J0L8V3I0rKW0-9eSw8B-e4Ry04X4U6fR2DWwEAGkpzSgsi3j_Dv8s=)
3. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFj3aaHf07PMZ8P-dmUj522zpN1lfXIKrw1FEGhLpQDhxXGL47npOVHNgz6G758fawbwVhhmfUaXDJe_hYFuqDuldhN6oE2OuaTkS0UKpwGotgQq0_OxGmo)
4. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH-up3saojGEsIX4XPU-CMwUyTAIpUmo-sN1tBkE6FFpUBJgE-XKTGVvyohd0wyWm3S37wkn_WC4P7-cUcsaqRy8CarFSxxHefMIWdhGuNTX0NL5bIh7DOTCTXPOT1grr6lxw==)
5. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQErtUENDexHmQhcFgj-EFD2zqnEjhU0h4J49yhAiSnOdA8X0aHROccW0WZh-knful1oPH_uscAHYsgM4nVE48LqlqtQSw0DF_SPYIT8qribGobcoDn7ixxxQlmR3q8MDMD7J3_yLXYQ0syXbuDs4kuQ-f03DzxIRqqOsxeJoLiq-mRUA03Bskhwz9CAFS8tBx2OTVbJki2VjirW0bYt7bm-p30bOV6Qlh9HhZfp5Jk=)
6. [vt.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGRSmVOalQeCKEkn1303xUkvcQDASuAaZkhnYjWyh5mNFuIr8QoObilJWb4a2EVuXMIMFQ63bXpH_PIdWJCxxpeupkVfiw2rRdxGMozTXfE9_cpwuodMqtJNVDk9Kl34k3rSaVgONHNmgQPMwmhdMQtwTTgOjE-QgsAv_iP9rUoOE5tCAv6sw==)
7. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHuDBESnKWEFqLepATZWCC0eNr3_G7SnvDPm58_aMXDKrZ3iSDn4_cbv4wK-jGyMn4qoZzu8koQT5RPIYsDxbNGJrWDEDheW2urX_-sA4b8eTeMn9khMJNmGbXVAyb73w6_hulAZ6hlBy7nPdQYhBGZhLPJNL5H5AR4KSoROMXWzIwZNuceXHQCeKbsmV7rmhRRdRZKc8pTpxzmkzzeyPapeIUwO0abacuR)
8. [lobehub.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHzpj_kErNCVCTxqDDH89DYqr3OS1i-9Mgq2_qiEMlA15oHSc4tjtP3WKrv-WwK89Ws3NkqreQ0YWH6_KGWzkoPtkuNvB4SUmmOaJ07jPAhWWbJBf5UAd1gxSPQJ9wBgcc7j8yJHWvWwfVjOsCGVO8gFMGdAC72jCjHavot8bODob0bEkEFzgnqdP2O)
9. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH3egU94WSopWxc-8p1LDBCVpXu1zcgwjdkr6tc2m_WgVa8O5UEzx1BXSnLaTPVp2x01DVEuWXYFzcJyL2Tme_1XnLrSaUlFko3b_cQGzPOKLUhQr-yrYodF5nDgjSkUPLP9NK7-flIvq8C7JYMWXZjCgk7Vozxeo-EVKoY60L1NEOMcjHnb7El4sfWG1kOvl8hvJu8PivTq4FTB4MnegpDnU8P29NWYQkb)
10. [uwa.edu.au](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGAe8Ax8kPL8pQPsUzoFV04WQP7r5tXZKUlXrofPQ4Rdk3YCtRWAsA-q587hE8HunDQ9Og5jJRHwbsrqujiN-ijPNgYWiULbCkBdttfo-qsWnNKzM6kFI2uAQpbLvTtOEXyhoo8marC9GecdaYuU9P4H2VQ-eSJoT0n8dZ3I0TrcJCSg8g=)
11. [uwa.edu.au](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH4hjV717dVbVG1AkZ3bQi8NbWuSuMOfNDn60s_FXt9IBAmCuIkZQWy8QgioYZpHmn4fIuT54yciuxQs0llSiflP4rOTTRU7rUFWFUKlZHhgw3vVmJLIcjUBj4NdL0MswXRT373aBXEPu_NZvmxY6rCGz-X5XH5aAbH)
12. [uwa.edu.au](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGV3ZXbrOijThM7uGGjCwFqVHS7ko5wrBRGg_crJ4lZ1f4sU8-mp_9sWT_BzUMiwYBKAh8wJCtGLexo12uuF4ZbwGzId7Wg-EsLtZrlhxbi2J4d3M-vlfYuMmG9gAOQhfWq5ymRp9D2erUC0WVuHH5RrYYpXfPYBw==)
13. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE_mNpGgy3n7w6otP2NFpveb1JwaRL42AVamV30aFeQ4v8Nc7kMRXfa2cCU4aMhKTKgjCgW1l4wKMUEbEfLbwP1-vnudYr8DPdL4Xl5EDaXF_8q6UO8C-5m9Ef9d9u1KeezYfDA04Gwfr9Bt48Gy3ohE8wxPtyHSEshpL2jCuhT)
14. [mdpi.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQERRCgvZOZxJXdKq9V7Wr3X1ZKfDOAesqTP9qJfcdKgP-lzRwG-WHp9CzbWxNBY7gpsbVRQbmjmIWVlKkeyDKJac0pX6b3B96s1lvFEvJpKYnTvuW4Fg__-7n1Rn6_U)
15. [scribd.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF2-3WV_DF_vezFXjIOLiGMHJreY0izBg6F7hBdoHH0KfQSW1T3mmSv1mIQSEPWSrsRtpsWEGq1jj_mL7x96lzPd6bnJGV0tNKa3Ibha2oSShYQDwl7FlSaergNK4Wg9R_joZW8d5u2WA==)
16. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHoXBgxyMnyNKYEzY2pLODV0_zobxBxz4GR2-Y12KKr3_4BDcM_-Sd5VbEq1UR0WL-_0fPbJKDi25KmiRJNskOV8wA9NTf6nYKlMO6W4k7CZyFTaWe8GlKhf659oj3xKs3zEdTwlNTTIcrXkYUcBKOrWRrZDDqwViAowgKxbw==)
17. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEt6vIE7VN1-P7EYIHns4-kAIZ3bUADMDLHHXIVF4g8zC0JWgHxsxYVaXDiFXNGQn_9q8Ci2elZMb-jzZn2YlVONHhyScpXjmPx0zhBXpuzBZR1oGHhjTBaBtq5Sf65DYcXg2p5NmnuGwZWxUHWE36V663P4tqGwpkX6J-p5tRS)
18. [github.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGy3Rh5SPize7sIXpmIY7M4ve47aq1lZE5J-IPrgcTU5tyjT9xg19Qfje7Iz1koS1mJrim2KJ9SsgqGXmXXkfkEIFxP55ZrtxxtMqTZkv1-x6quZ_689S84QD7luPAwBPKcMPtV9yyPtWE78zVvkYMT46NlPd24bgFwR0PJADzYs0iZfwIvDxam)
19. [theoj.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFOIKh-XZ9Ja1XMlIKx3oAIEOoMfDJPBJAU3iTJxDC_-93h3p_ysBZQXuZLkn00DzKtyfC2s13sdEmryA07qmkqkDXWCdnaB5msKXGfyYWD1kJKeUpUetmi86quLHC32_FJl_-K08PdIVkM-NXkHG7MsrvEBeANcRqgqw==)
20. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnXL6Wj6IL7sMWC2cu-8R46TM7lG_lB46waOYHLEq6WgMiiMvavI-b6LyWdJl8FS8z7-cG0LNL1BF3ixMOYQYwILS4UxtqOk4_wGjEOaeCkVVFA3o6WfMUvmkTYQ==)
21. [readthedocs.io](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF3KmJGXCgVMRsINoVCrsYUJ7u90_QzAeh0729YwHXUzsAlha3leI6sQXfy83At6YKkaZMkAfNU7-uHhX_KFRD3xe48AfTTY_yjVAOcCB9GUsPdPTfCvudqlVIwt7Ej5IpClwCX_NJxVg==)
22. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH0NvTHfk_6acA3dpqPrj-5ABcQDT_oFQEK6w66i0KMoF2RvbbOLEm3ap2K5XHed0jRA_qYtvMV1veyYzMl8PQTYEbMn4o2TCJby3ZYptCd_sGPMOBt5A_sGpk=)
23. [github.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFANHv3YN5JYvPG4xxdwxNd2aPwiKPgU5yo8glCTsuinUbQ26gVI7TetOpAEB2Ag2mAD6pdDofXPE4_xrzKQVF3LQWhAmfc4Cps1KhN3b5ll6QZGJdkgZrivsXUb3ODSQHFZAKXvEE_c50IcbjIFhAIMmgsrrVBsgks)
24. [researchgate.net](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFZkLtFPFP9n-IR5HIAHCAYpnHwBaOvAB9_6aswsWiIDpkEEoqhEPwkFNx-0aqu0AFGUr8SK4zb84N92-_rD9cjzZHU0bon-x7I5jfr9Yx1Vw7XD4YtH3MQsGDc0JJKwsrHK3sHkOZICKHPUOKTm51zeLnGFMZa9i64V-L7XrOz6Mgzk9etzsWYPfmHzJrLiPDBmgbmXYYevPODGpNnrJTmXcHl)
25. [umn.edu](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFaCtT73jx0BlegqJve1NvxwpPMAs3BnDT-qCBrgncVrkKBAfmAf-WIINqNv47qaoe0iARRNoV3ZnVmLX1FdgdiED9qK_0Qve1m64ulIFEXiItW8SjaxMZr9V2fFU8CHyWqLl1Jrg-Z723O2y3ZnodT8ppA_jxiYpVHi9bNZDEKIQTp2Pae4iP6lUw=)
26. [kobv.de](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMxjZ_lgdJwhaxA-Geu-aKu2xFwjA7stSTq2akgEwnPVLTw4sfmorydRzicy2jlpcWwW3X5SEMcXGkLGuspqkn8JWFbHXk694Vf4trc5kLOjKCM1_ITqoA5fgEcEIQy_Dv3e3HjzIzqyezWyu7UhNdncQY3Kf2mqlK0Ee3iInt580ndVrco0aF8_c=)
27. [pypi.org](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHc3hHddcwT9biuyE83v2biTui7t2cN4S-vK1QmJ2z5j-St8MAb2tXSstH9hjCvGFfbVgISrjJWfbt9bMwQXuLolEfveX-Duvc6W8I85h1_KEZqfThhCQ==)
28. [usgs.gov](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFNS0voIwIkGcEZp7i2rdGh4xUI8-BQ4bRaWXcibHR-sXSGNgZt_xSiL2Z50NUv5_xnW68KkfvYkSq-rQLf3zl3Xt4CEvjk6kNtnWTUf57f6p8LAv89i45evfcYbfuwNLOxLUu5KSDZsMdz-oMz2vNsBI9BxJMtskmNj8nmuokTWKQ7)