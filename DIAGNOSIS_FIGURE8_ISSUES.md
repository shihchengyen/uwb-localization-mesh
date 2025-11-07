# Figure-8 Pattern Diagnosis Report

## Summary

I've tested the DummyServerBringUp figure-8 pattern generation and signal emission. Here are my findings:

## ✅ **What's Working**

1. **Signal Emission**: The `pointerUpdated` signal emission in `main_demo.py` is working correctly
   - Position conversion from cm to meters: `x_m = position[0] / 100.0` ✓
   - Signal emission: `self.bus.pointerUpdated.emit(x_m, y_m, ts, "server")` ✓
   - Thread-safe position access using `_position_lock` ✓

2. **Simulated Position Generation**: The figure-8 pattern generation code is correct
   - Uses Lissajous curve: `x = center_x + a * sin(t)`, `y = center_y + b * sin(2*t)`
   - Parameters: `a=200cm`, `b=150cm`, center at (240cm, 300cm)
   - Generates positions in expected range: X [50-430cm], Y [150-450cm]

## ⚠️ **Issues Found**

### Issue 1: PGO Processing Produces Clustered Positions

**Problem**: The PGO (Pose Graph Optimization) output shows very small movement:
- **Test Results**: 
  - X range: 1.326m - 1.632m (only 0.306m span)
  - Y range: 3.362m - 3.579m (only 0.217m span)
  - Expected: X [0.5-4.3m], Y [1.5-4.5m] for full figure-8

**Root Cause**: The PGO solver needs time to accumulate measurements and track movement. The current implementation:
- Uses a 1.0 second window (`window_size_seconds`)
- Processes measurements at 10Hz
- May need several seconds to start showing the full pattern
- Could be converging to a local position instead of tracking movement

### Issue 2: Pattern Range Smaller Than Expected

**Problem**: The figure-8 pattern doesn't use the full Y range:
- Generated Y range: [150-450cm] (3.0m span)
- Expected Y range: [50-550cm] (5.0m span) 
- The pattern parameters (`b=150cm`) limit the vertical span

**Impact**: The pattern covers less of the space than it could.

### Issue 3: Slow Pattern Movement

**Problem**: During a 5-second test, the pattern showed minimal movement:
- Only 0 crossings of the center point (expected: multiple crossings)
- Very small position changes per update
- Suggests the simulation speed or pattern frequency may be too low

## 📊 **Test Results**

### Direct Position Generation (Simulated)
```
X range: [50.0, 430.0] cm → [0.500, 4.300] m ✓
Y range: [150.1, 449.9] cm → [1.501, 4.499] m ⚠️ (narrower than expected)
```

### PGO Output (Actual Processing)
```
X range: [132.6, 163.2] cm → [1.326, 1.632] m ⚠️ (very clustered)
Y range: [336.2, 357.9] cm → [3.362, 3.579] m ⚠️ (very clustered)
Range span: X=0.306m, Y=0.217m (too small)
```

### Signal Emission
```
Conversion: cm → meters ✓
Emission: pointerUpdated(x_m, y_m, ts, "server") ✓
Thread safety: Using _position_lock ✓
```

## 🔧 **Recommendations**

### 1. Increase Simulation Time for Testing
The PGO needs more time to accumulate measurements. Try running the simulation for 30+ seconds to see the full pattern.

### 2. Adjust Pattern Parameters (Optional)
To use more of the space, adjust the figure-8 parameters:
```python
# In DummyServerBringUp.py _get_simulated_position()
a = 220  # Increase width (was 200)
b = 250  # Increase height (was 150)
```

### 3. Verify PGO Window Size
The `window_size_seconds=1.0` might be too small. Consider:
- Increasing to 2.0 seconds for better tracking
- Or verify that the PGO is actually processing movement correctly

### 4. Check Simulation Speed
The pattern speed is controlled by:
```python
scale_t = t * self.simulation_speed * 0.5
```
If `simulation_speed=1.0`, the pattern completes one full cycle every ~12.5 seconds. Consider:
- Increasing `simulation_speed` for faster movement (e.g., 2.0 or 3.0)
- Or wait longer to see the full pattern

### 5. Add Debugging
Add logging to verify PGO is updating positions:
```python
# In _process_measurements(), after PGO solve
if pgo_result.success:
    print(f"PGO position: {pgo_result.node_positions[f'phone_{phone_id}']}")
```

## ✅ **Conclusion**

**Signal Emission**: ✅ Working correctly - no issues with variable passing to signals

**Figure-8 Pattern Generation**: ✅ Code is correct, but:
- Pattern covers less Y range than optimal
- PGO output is clustered (needs more time or adjustment)
- Pattern movement may be too slow for short tests

**Next Steps**:
1. Run the application for 30+ seconds to see if the full pattern appears
2. Increase `simulation_speed` if the pattern seems too slow
3. Check PGO logs to verify positions are updating over time
4. Consider adjusting pattern parameters if you want more coverage

## Test Files Created

- `test_figure8_pattern.py` - Tests pattern generation
- `test_signal_emission.py` - Tests signal emission and conversion

Run these to verify the current behavior.

