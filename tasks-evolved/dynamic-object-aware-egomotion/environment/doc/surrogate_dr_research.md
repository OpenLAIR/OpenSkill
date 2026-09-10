To verify the output of your egomotion and dynamic object segmentation pipeline without access to ground truth, you can implement the following verification anchors and invariants in your `pytest` suite.

### 1. Independently Computable Reference Values (Geometric Invariants)
Since you are performing camera motion estimation (e.g., Pan/Tilt/Dolly), the resulting motion labels must be consistent with the **Homography Matrix ($H$)** decomposition.

*   **The Invariant**: If the camera motion is classified as "Stay," the homography matrix $H$ between frame $i$ and $i+1$ must be approximately the Identity Matrix $I$.
*   **Verification Logic**:
    *   Compute the homography $H$ using a standard method (e.g., `cv2.findHomography` with RANSAC) on a static scene segment.
    *   **Assertion**: For a "Stay" label, the Frobenius norm of the difference between the estimated $H$ and the identity matrix $I$ must be below a threshold $\epsilon$:
        $$\|H - I\|_F < \epsilon \quad (\text{e.g., } \epsilon = 0.05)$$
    *   **Dolly In/Out**: For "Dolly" motion, the determinant of the upper-left $2 \times 2$ submatrix of $H$ (the scale factor) must deviate significantly from 1.0.

### 2. Dataset-Level Statistical Invariants
These assertions ensure the output structure is valid and physically plausible.

*   **Completeness and Continuity**:
    *   The keys in `pred_instructions.json` must cover the entire video duration sampled at 6 FPS. If the video has $T$ seconds, there must be $T \times 6$ frames.
    *   **Assertion**: `assert sorted(list_of_all_intervals) == expected_continuous_sequence`.
*   **Mask Sparsity and Bounds**:
    *   The `pred_dyn_masks.npz` stores CSR data.
    *   **Assertion (Range)**: For every mask, `0 <= data <= 1` (binary).
    *   **Assertion (Structure)**: The `indptr` array must have length `H + 1`, and `indptr[-1]` must equal the total number of non-zero elements (the length of `data` and `indices`).
    *   **Assertion (Consistency)**: The number of keys in the `.npz` file must match the number of sampled frames defined in the JSON.

### 3. Cross-Validation Approaches
You can use a "Minimalist Baseline" to cross-check the skill's output.

*   **Baseline Method**: Use **Frame Differencing** (without homography compensation) to generate a "naive" mask.
*   **Cross-Check Logic**:
    *   The "sophisticated" mask (from your skill) should be a subset of the "naive" mask in areas where the camera is moving, but significantly smaller (more precise) because the skill compensates for global motion.
    *   **Assertion**: `np.sum(sophisticated_mask) < np.sum(naive_mask)` for frames labeled with non-"Stay" motion. This verifies that the motion compensation is actually reducing false positives caused by camera movement.

### 4. Benchmarks and Reference Implementations
For validating your egomotion logic, you can compare your implementation against the **KITTI Vision Benchmark** logic or standard **OpenCV Tutorials**.

*   **Reference Implementation**: The OpenCV tutorial *[Feature-based Homography Estimation](https://docs.opencv.org/4.x/d1/de0/tutorial_py_feature_homography.html)* provides the exact mathematical framework for calculating $H$.
*   **Test Oracle**:
    *   Create a synthetic "test case" by taking a single frame, applying a known affine transformation (e.g., `cv2.warpAffine` with a known rotation matrix), and running your motion classifier on this pair.
    *   **Assertion**: If you apply a rotation of $\theta$ degrees, the classifier must return "Roll Left/Right" (depending on sign) and the estimated $H$ must match the transformation matrix used to generate the synthetic frame within a tolerance of $10^{-3}$.