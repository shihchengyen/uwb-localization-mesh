# Edge Transformation Summary

## Quick Answer

**Q: Are anchor-anchor edges transformed through `create_relative_measurement()`?**

**A: NO - and this is CORRECT!**

---

## Verification Results ✅

```
╔══════════════════════════════════════════════════════════════╗
║          VERIFICATION PASSED - All Transformations OK        ║
╚══════════════════════════════════════════════════════════════╝

✓ Anchor-anchor edges: NOT transformed (already global)
✓ Phone-anchor edges: Transformed (local → global)  
✓ Both edge types: End up in SAME coordinate system
✓ PGO optimization: Works correctly with mixed edges
```

---

## Edge Creation Flow

### Anchor-Anchor Edges

```python
# Input: Ground truth positions (ALREADY GLOBAL)
true_nodes = {
    0: np.array([480, 600, 239]),  # Global (x,y,z) cm
    1: np.array([0, 600, 239]),
    2: np.array([480, 0, 239]),
    3: np.array([0, 0, 239])
}

# Process: Simple subtraction (NO TRANSFORMATION)
def create_anchor_anchor_edges(anchor_config):
    relative_vec = pos_j - pos_i  # Direct subtraction
    edges.append((anchor_i, anchor_j, relative_vec))

# Output: Vectors in GLOBAL frame
Example: anchor_0 → anchor_1 = [-480, 0, 0] ✓
```

**Path**: `anchor_edges.py` → NO TRANSFORM → Global vectors

---

### Phone-Anchor Edges

```python
# Input: UWB measurements (SENSOR-LOCAL frame)
local_vector = [100, 50, -30]  # In sensor's local coords

# Process: Rotation transformation (LOCAL → GLOBAL)
def create_relative_measurement(anchor_id, phone_id, local_vector):
    v_global = ANCHOR_R[anchor_id] @ local_vector  # Transform!
    return (anchor_id, phone_id, v_global)

# Output: Vectors in GLOBAL frame
Example: After Rz(225°)@Ry(45°) → [-50, -50, -70.7] ✓
```

**Path**: `transforms.py` → TRANSFORM → Global vectors

---

## Why This Is Correct

```
┌─────────────────────────────────────────────────────────────┐
│                    COORDINATE SYSTEMS                        │
└─────────────────────────────────────────────────────────────┘

Anchor Positions:
    ┌──────────────────────────┐
    │ Surveyed/measured in     │
    │ GLOBAL room coordinates  │──┐
    │ (480, 600, 239) etc.     │  │ Already global
    └──────────────────────────┘  │ NO transform needed
                                  │
                                  ▼
                            Global Vectors


UWB Measurements:
    ┌──────────────────────────┐
    │ Measured by sensor in    │
    │ SENSOR-LOCAL coords      │──┐
    │ Each sensor has own      │  │ Local frame
    │ orientation (tilted)     │  │ MUST transform
    └──────────────────────────┘  │
                                  │
                                  ▼
                          Rotation Matrix
                                  │
                                  ▼
                            Global Vectors
```

---

## Verification Test Results

### Test 1: Anchor-Anchor Edges ✓

All 12 edges verified to be simple position differences:

```
✓ anchor_0 → anchor_1: [-480, 0, 0] (expected: [-480, 0, 0])
✓ anchor_0 → anchor_2: [0, -600, 0] (expected: [0, -600, 0])
✓ anchor_0 → anchor_3: [-480, -600, 0] (expected: [-480, -600, 0])
... (9 more edges all correct)
```

**Conclusion**: No transformation applied ✓

### Test 2: Phone-Anchor Transformations ✓

Test vector `[100, 0, 0]` (forward in sensor frame):

```
Anchor 0 (Rz(225°)@Ry(45°)): → [-50, -50, -70.7] ✓
Anchor 1 (Rz(315°)@Ry(45°)): → [50, -50, -70.7] ✓
Anchor 2 (Rz(135°)@Ry(45°)): → [-50, 50, -70.7] ✓
Anchor 3 (Rz(45°)@Ry(45°)):  → [50, 50, -70.7] ✓
```

All Z-components negative ✓ (sensors pointing downward at 45°)

**Conclusion**: Transformations correctly applied ✓

### Test 3: Coordinate Consistency ✓

Both edge types end up in **SAME** global coordinate system:

- Anchor-anchor: Global (no transform)
- Phone-anchor: Global (after transform)
- Result: PGO can optimize them together ✓

---

## Conclusion: Bad Data Is NOT From This

### ✅ What's Working

1. Anchor-anchor edges are correctly in global frame
2. Phone-anchor edges are correctly transformed to global frame
3. Both use the same coordinate system
4. PGO optimization works correctly

### ❌ What's Causing Bad Data

Based on your logs (`n_phone_edges: 1`):

**Primary Issue**: Only 1 anchor publishing
- System is severely underconstrained
- Phone position has 2 degrees of freedom
- Will produce inaccurate results even with correct math

**Possible Secondary Issues**:
1. Rotation matrices may not match actual physical setup
2. UWB measurement noise/outliers
3. Multipath interference

---

## Action Items

### 1. Fix Anchor Publishing (Critical!)

```bash
# Check which anchors are active
python Data_collection/mqtt_monitor.py

# Expected:
✓ Anchor 0: ACTIVE
✓ Anchor 1: ACTIVE  
✓ Anchor 2: ACTIVE
✓ Anchor 3: ACTIVE

# Current (problem):
✓ Anchor 0: ACTIVE
✗ Anchor 1: NOT PUBLISHING
✗ Anchor 2: NOT PUBLISHING
✗ Anchor 3: NOT PUBLISHING
```

### 2. Verify Physical Setup (Optional)

If you still get bad data after fixing anchors:

```python
# Check if rotation matrices match physical reality
# Are sensors actually:
# - Tilted 45° downward? (Ry(+45°))
# - Facing room center with yaw angles:
#   * Anchor 0: 225° (SW)
#   * Anchor 1: 315° (SE)
#   * Anchor 2: 135° (NW)
#   * Anchor 3: 45° (NE)
```

### 3. Add Outlier Filtering (Future)

Once basics are working, add measurement validation.

---

## Mathematical Proof

### Why Mixed Transformations Are OK

Given:
- Anchor positions: $A_i$ in global frame
- UWB measurement: $m$ in sensor-local frame
- Rotation matrix: $R$

**Anchor-Anchor Edges**:
$$e_{ij} = A_j - A_i \quad \text{(already global)}$$

**Phone-Anchor Edges**:
$$e_{iP} = R \cdot m \quad \text{(transformed to global)}$$

**PGO Minimizes**:
$$\min_P \sum \|e_{ij} - (A_j - A_i)\|^2 + \sum \|e_{iP} - (P - A_i)\|^2$$

Since both $e_{ij}$ and $e_{iP}$ are in **same frame** (global), optimization is valid ✓

---

## References

- **Verification Script**: `Data_collection/verify_edge_transforms.py`
- **Detailed Analysis**: `EDGE_TRANSFORMATION_ANALYSIS.md`
- **Rotation Fix Guide**: `ROTATION_MATRIX_FIX.md`
- **Drift Prevention**: `DRIFT_PREVENTION_QUICK_REF.md`

---

## TL;DR

```
Question: Are anchor-anchor edges transformed?
Answer:   NO

Is this correct?
Answer:   YES ✓

Is this causing bad data?
Answer:   NO ✗

What's the real problem?
Answer:   Only 1 of 4 anchors is publishing measurements
```

**Fix**: Get all 4 anchors active, then bad data will improve dramatically!

