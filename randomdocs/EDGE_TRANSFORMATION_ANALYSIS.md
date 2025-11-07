# Edge Transformation Analysis

## Question: Are anchor-anchor edges transformed? Could this cause bad data?

---

## Answer: NO - And this is CORRECT!

### Anchor-Anchor Edges (NO Transformation)

**Code**: `packages/localization_algos/edge_creation/anchor_edges.py`

```python
def create_anchor_anchor_edges(anchor_config: AnchorConfig):
    for anchor_i in positions:
        pos_i = positions[anchor_i]  # ALREADY IN GLOBAL FRAME
        for anchor_j in positions:
            pos_j = positions[anchor_j]  # ALREADY IN GLOBAL FRAME
            
            # Direct subtraction - NO TRANSFORMATION
            relative_vec = pos_j - pos_i
            
            edges.append((f"anchor_{anchor_i}", f"anchor_{anchor_j}", relative_vec))
```

**Input**: Ground truth positions in **GLOBAL room coordinates**
```python
self.true_nodes = {
    0: np.array([480, 600, 239]),  # Already global (x, y, z) in cm
    1: np.array([0, 600, 239]),
    2: np.array([480, 0, 239]),
    3: np.array([0, 0, 239])
}
```

**Output**: Vectors already in **GLOBAL frame**
- Example: `anchor_0 → anchor_1` = `(0-480, 600-600, 239-239)` = `(-480, 0, 0)` cm

**Transformation**: ❌ **NONE** (positions already global)

---

### Phone-Anchor Edges (YES Transformation)

**Code**: `packages/localization_algos/edge_creation/transforms.py`

```python
def create_relative_measurement(anchor_id, phone_node_id, local_vector):
    # Transform local vector to global frame
    v_global = ANCHOR_R[anchor_id] @ local_vector
    
    return (f"anchor_{anchor_id}", f"phone_{phone_node_id}", v_global)
```

**Input**: UWB measurements in **SENSOR-LOCAL coordinates**
- Sensor local frame: x=forward (board normal), y=left, z=up (relative to sensor)
- Example: If sensor measures phone at (100, 50, -30) in its local frame

**Transformation**: ✅ **YES** - Rotation from sensor-local to global
```python
ANCHOR_R[0] = Rz(225°) @ Ry(+45°)  # Sensor tilted 45° down, facing SW
```

**Output**: Vector in **GLOBAL room frame**

---

## Why This Is CORRECT

### Different Coordinate Systems

1. **Anchor Positions**: 
   - Measured/specified in global room coordinates
   - Example: "Anchor 0 is at position (480, 600, 239) cm in the room"
   - NO transformation needed

2. **UWB Measurements**:
   - Measured in sensor's LOCAL coordinate system
   - Each sensor has different orientation (tilted, facing center)
   - REQUIRES transformation to global

### Analogy

Think of it like this:

**Anchor-Anchor Edges** = Measuring distance between two cities on a map
- Both cities' positions are in same coordinate system (latitude/longitude)
- Just subtract: `distance = City_B_coords - City_A_coords`
- No transformation needed

**Phone-Anchor Edges** = GPS reading from a tilted compass
- Compass (sensor) has its own local "north"
- Must rotate compass reading to true north (global)
- Transformation required: `true_north = rotation_matrix @ local_reading`

---

## Verification: Are the Transformations Consistent?

### Edge Type Comparison

| Edge Type | Input Frame | Transform? | Output Frame | Source |
|-----------|-------------|------------|--------------|--------|
| **Anchor→Anchor** | Global | ❌ NO | Global | Ground truth positions |
| **Anchor→Phone** | Sensor-local | ✅ YES | Global | UWB measurements + rotation |

### Graph Structure After Edge Creation

```
All edges in PGO graph are in GLOBAL FRAME:

    Anchor_0 (480, 600, 239)
         ●━━━━━━━━━━━━━━━━━━━━━━●  Anchor_1 (0, 600, 239)
         ┃  vector: (-480,0,0)  ┃
         ┃                       ┃
         ┃    📱 Phone           ┃
         ┃    ╲  ╱ ╲  ╱         ┃
         ┃     ╲╱   ╲╱          ┃
         ┃   (global) (global)  ┃
         ┃                       ┃
         ●━━━━━━━━━━━━━━━━━━━━━━●
    Anchor_2                  Anchor_3

All vectors are in SAME coordinate system (global)
PGO optimization works correctly!
```

---

## Could This Cause Bad Data?

### ✅ Current Design is CORRECT

The fact that:
- Anchor-anchor edges are NOT transformed (stay in global)
- Phone-anchor edges ARE transformed (local → global)

Is **exactly right**! Both types end up in the **same global frame**, which is required for PGO.

### ⚠️ Potential Issues (Not Related to This)

The bad data you're seeing is **NOT** from this difference. Possible actual causes:

1. **Wrong rotation matrices** `ANCHOR_R[i]`
   - If physical sensor orientation doesn't match code assumptions
   - Check: Are sensors actually tilted 45° down?
   - Check: Are yaw angles (225°, 315°, 135°, 45°) correct?

2. **Only 1 anchor publishing**
   - You have only 1 phone-anchor edge
   - System is severely underconstrained
   - This WILL cause bad position estimates

3. **UWB measurement errors**
   - Multipath interference
   - Outliers not being filtered
   - Hardware calibration issues

---

## Testing the Transformations

### 1. Check Anchor-Anchor Edge Values

```python
# In Server_bring_up.py after line 86
print("Anchor-Anchor Edges:")
for from_node, to_node, vec in self._anchor_edges:
    print(f"  {from_node} → {to_node}: {vec}")

# Expected output (12 edges):
# anchor_0 → anchor_1: [-480.   0.   0.]
# anchor_1 → anchor_0: [ 480.   0.   0.]
# anchor_0 → anchor_2: [  0. -600.   0.]
# anchor_2 → anchor_0: [  0. 600.   0.]
# ... etc
```

These should be simple differences of the ground truth positions.

### 2. Check Phone-Anchor Edge Transformation

```python
# In Server_bring_up.py around line 189
for anchor_id, vectors in binned.measurements.items():
    if vectors:
        avg_vector = np.mean(vectors, axis=0)
        print(f"Anchor {anchor_id}:")
        print(f"  Local avg: {avg_vector}")
        
        edge = create_relative_measurement(anchor_id, phone_id, avg_vector)
        from_node, to_node, global_vec = edge
        print(f"  Global: {global_vec}")
        print(f"  Rotation applied: {ANCHOR_R[anchor_id]}")
```

### 3. Verify Rotation Matrices

```python
# Test script to verify sensor orientations
from packages.localization_algos.edge_creation.transforms import ANCHOR_R
import numpy as np

# For anchor 0 (top-right, should face SW and down)
# If sensor measures phone directly "forward" (100, 0, 0) in local frame
test_local = np.array([100, 0, 0])
test_global = ANCHOR_R[0] @ test_local

print(f"Anchor 0 'forward' direction in global: {test_global}")
# Should point generally SW and downward
# Expected: negative X, negative Y, negative Z components
```

---

## Root Cause Analysis

Based on your logs showing only `n_phone_edges: 1`, the bad data is likely from:

### Primary Issue: Underconstrained System
```
With only 1 phone-anchor edge:
- Phone position has 2 degrees of freedom (can slide along a surface)
- PGO will find *some* solution, but it may be wildly inaccurate
```

### Secondary Issue: Possible Rotation Matrix Errors

Check if the rotation matrices match your **actual physical setup**:

```python
ANCHOR_R = {
    0: Rz(225.0) @ Ry(+45.0),  # ← Does anchor 0 face SW at 225°?
    1: Rz(315.0) @ Ry(+45.0),  # ← Does anchor 1 face SE at 315°?
    2: Rz(135.0) @ Ry(+45.0),  # ← Does anchor 2 face NW at 135°?
    3: Rz(45.0) @ Ry(+45.0),   # ← Does anchor 3 face NE at 45°?
}
```

**Verify**:
1. Are all sensors tilted 45° downward from horizontal? (Ry(+45°))
2. Are the yaw angles correct for how they face the room center?

---

## Recommendation

The transformation approach is **correct**. To debug bad data:

1. **Priority 1**: Get all 4 anchors publishing
   - Run `mqtt_monitor.py` to check
   - This is the most likely cause of bad position estimates

2. **Priority 2**: Verify rotation matrices
   - Check physical sensor orientations
   - Compare with code assumptions
   - See `ROTATION_MATRIX_FIX.md` if issues

3. **Priority 3**: Add edge validation
   - Filter outliers in UWB measurements
   - Check for unreasonable phone-anchor distances

---

## Conclusion

✅ **Anchor-anchor edges are correctly NOT transformed** (already in global frame)

✅ **Phone-anchor edges are correctly transformed** (local → global)

❌ **This is NOT the cause of bad data**

The real issues are:
1. Only 1 anchor publishing (underconstrained)
2. Possibly incorrect rotation matrices (if physical setup differs from code)

Focus on getting all 4 anchors active first!

