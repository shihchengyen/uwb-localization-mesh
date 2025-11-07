```mermaid
sequenceDiagram
    participant User
    participant ServerBringUp
    participant UWBMQTTServer
    participant SlidingWindowBinner
    participant PGOSolver

    %% Initialization Phase
    rect rgb(240, 248, 255)
        User->>ServerBringUp: server = ServerBringUp(mqtt_config)
        activate ServerBringUp
        ServerBringUp->>ServerBringUp: __init__()
        ServerBringUp->>UWBMQTTServer: Create UWBMQTTServer(config, _handle_measurement)
        ServerBringUp->>PGOSolver: Create PGOSolver()
        ServerBringUp->>ServerBringUp: Create AnchorConfig, pre-compute anchor edges
        ServerBringUp->>ServerBringUp: Initialize per-phone data structures
        deactivate ServerBringUp
    end

    %% Startup Phase
    rect rgb(255, 250, 240)
        User->>ServerBringUp: server.start()
        activate ServerBringUp
        ServerBringUp->>UWBMQTTServer: start()
        activate UWBMQTTServer
        UWBMQTTServer->>UWBMQTTServer: Connect to MQTT broker
        UWBMQTTServer->>UWBMQTTServer: Subscribe to "uwb/anchor/+/vector"
        deactivate UWBMQTTServer

        ServerBringUp->>ServerBringUp: Start _processor_thread (background)
        note over ServerBringUp: Background processing thread starts
        deactivate ServerBringUp
    end

    %% Main Processing Loop
    loop Every ~10ms in background thread
        rect rgb(255, 248, 240)
            ServerBringUp->>ServerBringUp: Check all phone_ids in _measurements queue
            ServerBringUp->>SlidingWindowBinner: create_binned_data(phone_id)
            activate SlidingWindowBinner
            SlidingWindowBinner->>SlidingWindowBinner: Aggregate measurements in 1s time window
            SlidingWindowBinner-->>ServerBringUp: Return BinnedData or None
            deactivate SlidingWindowBinner

            alt If binned data available
                ServerBringUp->>ServerBringUp: Create phone-anchor edges from binned measurements
                ServerBringUp->>PGOSolver: solve(nodes, edges + anchor_edges, true_nodes)
                activate PGOSolver
                PGOSolver->>PGOSolver: Nonlinear least squares optimization (Levenberg-Marquardt)
                PGOSolver->>PGOSolver: Apply anchoring transformation to ground truth
                PGOSolver-->>ServerBringUp: Return PGOResult with optimized positions
                deactivate PGOSolver

                ServerBringUp->>ServerBringUp: Update user_position from optimized result
                ServerBringUp->>ServerBringUp: Update data[phone_id] with latest binned data
                ServerBringUp->>ServerBringUp: Log position update with metrics
            end
        end
    end

    %% Measurement Reception via MQTT
    rect rgb(240, 255, 240)
        UWBMQTTServer->>ServerBringUp: _handle_measurement(Measurement) [callback]
        activate ServerBringUp
        ServerBringUp->>SlidingWindowBinner: add_measurement(measurement)
        activate SlidingWindowBinner
        SlidingWindowBinner->>SlidingWindowBinner: Validate measurement:<br/>- Statistical outlier detection<br/>- Anchor variance checks<br/>- Time window bounds
        SlidingWindowBinner-->>ServerBringUp: Return accepted/rejected status
        deactivate SlidingWindowBinner

        alt If measurement accepted
            ServerBringUp->>ServerBringUp: Add to _measurements[phone_id] queue
            note over ServerBringUp: Queued for background processing
        else If measurement rejected
            ServerBringUp->>ServerBringUp: Log rejection reason and update metrics
        end
        deactivate ServerBringUp
    end

    %% Shutdown Phase
    rect rgb(255, 240, 240)
        User->>ServerBringUp: server.stop()
        activate ServerBringUp
        ServerBringUp->>ServerBringUp: Set _stop_event (signals background thread to stop)
        ServerBringUp->>UWBMQTTServer: stop()
        activate UWBMQTTServer
        UWBMQTTServer->>UWBMQTTServer: Disconnect from MQTT broker
        deactivate UWBMQTTServer
        ServerBringUp->>ServerBringUp: Wait for _processor_thread to finish
        deactivate ServerBringUp
    end
```

## Server Bring-up Processing Sequence

### Key Components and Data Flow (within Server_bring_up.py scope):

**1. Initialization Phase:**
- Creates UWBMQTTServer with measurement callback (`_handle_measurement`)
- Initializes PGOSolver instance
- Creates AnchorConfig and pre-computes anchor-anchor edges for efficiency
- Sets up per-phone data structures (queues, binners, locks)

**2. Startup Phase:**
- Starts MQTT server and connects to broker
- Subscribes to measurement topics: `uwb/anchor/+/vector`
- Launches background processing thread (`_processor_thread`)

**3. Measurement Reception (MQTT Callback):**
- Raw UWB measurements arrive via `UWBMQTTServer._on_message()`
- Triggers `ServerBringUp._handle_measurement()` callback
- Measurements validated by `SlidingWindowBinner.add_measurement()`
- Accepted measurements queued in `_measurements[phone_id]` for processing

**4. Background Processing Loop:**
- Runs continuously (~every 10ms) in separate thread
- Checks all phone_ids with queued measurements
- Creates time-windowed bins via `SlidingWindowBinner.create_binned_data()`
- Generates phone-anchor relative measurement edges
- Runs PGO optimization with anchor anchoring to ground truth
- Updates `user_position` and `data[phone_id]` state
- Logs position updates with processing metrics

**5. Data Structures (within ServerBringUp class):**
- **data**: `Dict[int, BinnedData]` - Latest processed bins per phone
- **user_position**: `Optional[np.ndarray]` - Current position estimate
- **_measurements**: `Dict[int, Queue[Measurement]]` - Thread-safe per-phone queues
- **_filtered_binners**: `Dict[int, SlidingWindowBinner]` - Per-phone binning instances
- **_anchor_edges**: `List[Tuple[str, str, np.ndarray]]` - Pre-computed anchor constraints
- **uwb_mqtt_server**: `UWBMQTTServer` - MQTT communication instance
- **_processor_thread**: `threading.Thread` - Background processing thread

**6. Threading Model:**
- **Main Thread**: Handles initialization, startup, shutdown
- **MQTT Thread**: Handles network communication and callbacks (in UWBMQTTServer)
- **Processing Thread**: Background optimization loop (`_process_measurements()`)

**7. Key Processing Steps:**
1. **Measurement Ingestion**: MQTT callback → validation → queuing
2. **Binning**: Aggregate measurements into 1-second windows with quality filtering
3. **Edge Creation**: Transform binned measurements to relative position constraints
4. **PGO Optimization**: Solve pose graph with anchor anchoring to ground truth
5. **State Update**: Update position estimates and maintain latest processed data

This sequence diagram shows the core processing pipeline within `Server_bring_up.py`, focusing on the real-time localization logic from raw MQTT measurements to optimized position estimates.
