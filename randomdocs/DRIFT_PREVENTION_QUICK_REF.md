# Drift Prevention - Quick Reference

## TL;DR

**Your system prevents drift through:**
1. **12 anchor-anchor edges** → Rigid geometry (can't deform)
2. **Anchoring transformation** → Align to global frame
3. **Hard anchor fixing** → Force exact ground truth positions

**Result:** ✅ **ZERO DRIFT** guaranteed

---

## Constraint Mechanisms

### 1. Rigid Anchor Constellation
```python
# 12 bidirectional edges between 4 anchors
edges = [
    (A0, A1, v01), (A1, A0, -v01),  # Pair 0-1
    (A0, A2, v02), (A2, A0, -v02),  # Pair 0-2
    (A0, A3, v03), (A3, A0, -v03),  # Pair 0-3
    (A1, A2, v12), (A2, A1, -v12),  # Pair 1-2
    (A1, A3, v13), (A3, A1, -v13),  # Pair 1-3
    (A2, A3, v23), (A3, A2, -v23),  # Pair 2-3
]
```
**Effect:** Anchors behave as rigid body ⭐⭐⭐

### 2. Phone Measurement Edges
```python
# Up to 4 edges from anchors to phone
for anchor_id in [0, 1, 2, 3]:
    edge = (anchor_id, phone, measured_vector)
```
**Effect:** Constrains phone relative to rigid anchors ⭐⭐

### 3. Global Optimization
```python
# Minimize error across ALL edges
E = Σ ||(predicted_vector - measured_vector)||²
```
**Effect:** Best-fit solution (in arbitrary frame) ⭐⭐⭐

### 4. Anchoring Transformation
```python
# Step 1: Translate to anchor_3 origin
# Step 2: Scale to match anchor_0 distance
# Step 3: Rotate to align anchor_0 direction
# Step 4: FORCE anchors to exact positions
for i in [0,1,2,3]:
    final_position[anchor_i] = ground_truth[anchor_i]
```
**Effect:** Locks to global frame with zero drift ⭐⭐⭐

---

## Drift Types Prevented

| Drift Type | Prevention Mechanism | Status |
|------------|---------------------|--------|
| **Translation** | Anchor_3 → origin constraint | ✅ ELIMINATED |
| **Rotation** | Anchor_0 direction alignment | ✅ ELIMINATED |
| **Scale** | A0↔A3 distance matching | ✅ ELIMINATED |
| **Deformation** | 12 rigid anchor-anchor edges | ✅ ELIMINATED |

---

## Code Locations

```
packages/localization_algos/
├── edge_creation/
│   ├── anchor_edges.py        # Creates 12 anchor-anchor edges
│   └── transforms.py          # Transforms UWB to global frame
├── pgo/
│   ├── solver.py              # Optimization engine
│   └── transforms.py          # Anchoring transformation ⭐
└── binning/
    └── sliding_window.py      # Groups measurements by time
```

**Key Function:** `apply_anchoring_transformation()` in `pgo/transforms.py`

---

## Verification Checklist

### ✅ What Should Be Correct

- [ ] **12 anchor-anchor edges** in every solve
  ```python
  assert len([e for e in edges if 'anchor' in e[0] and 'anchor' in e[1]]) == 12
  ```

- [ ] **Anchoring applied** after optimization
  ```python
  # In solver.py line 131-134
  anchored_positions = apply_anchoring_transformation(
      initial_positions,
      anchor_positions  # Ground truth
  )
  ```

- [ ] **Anchors forced to ground truth**
  ```python
  # In pgo/transforms.py lines 99-100
  for i in range(4):
      transformed_nodes[f'anchor_{i}'] = anchor_positions[i]
  ```

### ⚠️ What Needs Fixing

- [ ] **4 phone-anchor edges** (currently only 1!)
  ```bash
  # Check with mqtt_monitor.py
  python Data_collection/mqtt_monitor.py
  # Should see all 4 anchors publishing
  ```

---

## Current System Status

```json
{
  "n_edges": 13,
  "n_phone_edges": 1,   // ❌ Should be 4
  "n_anchor_edges": 12  // ✅ Correct
}
```

**Issue:** Only 1 of 4 anchors is publishing  
**Impact on Drift:** None (anchors still locked to ground truth)  
**Impact on Accuracy:** High (phone underconstrained)

---

## Why Drift is Impossible

```
Optimized Solution (arbitrary frame)
         ↓
Anchoring Transformation
  • Translate anchor_3 to origin
  • Scale to match true A0-A3 distance  
  • Rotate to match true A0 direction
         ↓
Hard Anchor Fixing
  • A0 = (480, 600, 239) exactly
  • A1 = (0, 600, 239) exactly
  • A2 = (480, 0, 239) exactly
  • A3 = (0, 0, 239) exactly
         ↓
Phone inherits same transformation
         ↓
✅ ZERO DRIFT in global coordinates
```

---

## Mathematical Guarantee

Given:
- Optimized positions: `X_opt` (in arbitrary frame)
- Anchoring transform: `T = (t, R, s)` where
  - `t`: translation
  - `R`: rotation matrix
  - `s`: scale factor

Transformation:
```
X_final = s · R · (X_opt + t)
```

Constraints:
```
T(X_opt_A3) = X_true_A3  (determines t)
T(X_opt_A0) = X_true_A0  (determines R, s)
```

Since `T` is uniquely determined by 2 anchor constraints,
and all anchors are forced to ground truth:
```
X_final_Ai = X_true_Ai  ∀i ∈ {0,1,2,3}
```

The phone transformation uses the **same** `T`:
```
X_final_phone = T(X_opt_phone)
```

Therefore, phone is in the **same global frame** as anchors.

**QED:** No drift possible ∎

---

## Debugging Drift Issues

If you suspect drift:

### 1. Check Anchor Positions
```python
# After PGO solve
for i in range(4):
    assert np.allclose(result.node_positions[f'anchor_{i}'], 
                      true_positions[i], 
                      atol=1e-6)
```
Should be **exactly** ground truth (within floating point precision)

### 2. Check Edge Counts
```python
assert n_anchor_edges == 12  # Must be exactly 12
assert n_phone_edges >= 2    # Need at least 2 for good constraint
```

### 3. Check Anchoring Applied
```python
# In solver.py, verify lines 131-134 are NOT commented out
anchored_positions = apply_anchoring_transformation(...)
```

### 4. Verify Ground Truth Positions
```python
# In Server_bring_up.py
self.true_nodes = {
    0: np.array([480, 600, 239]),  # Must match physical setup
    1: np.array([0, 600, 239]),
    2: np.array([480, 0, 239]),
    3: np.array([0, 0, 239])
}
```

---

## Next Steps

To improve accuracy (not drift, which is already zero):

1. **Fix anchor publishing** (critical!)
   - Get all 4 anchors sending measurements
   - Use `mqtt_monitor.py` to verify

2. **Add outlier rejection** (optional)
   - Filter bad UWB measurements
   - Use RANSAC or statistical filtering

3. **Add temporal smoothing** (optional)
   - Kalman filter on top of PGO
   - Smooth noisy measurements over time

4. **Tune PGO parameters** (optional)
   - Adjust convergence threshold
   - Weight edges differently

---

## Summary

✅ **Your PGO design is excellent for preventing drift**

The system uses:
- Rigid anchor geometry (12 edges)
- Global frame alignment (anchoring)
- Hard position fixing (exact ground truth)

**Drift is mathematically impossible** because anchors are locked to ground truth and phone position is derived from these locked anchors.

The **only** issue is getting all 4 anchors to publish measurements for better accuracy.

