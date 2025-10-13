## Unresolved
- [x] Verify that the * 100 has to be removed 
- [x] Resolve laptop dependancies (commands in .md, paths, emojis)
- [x] DeprecationWarning: callback_api_version=mqtt.CallbackAPIVersion.VERSION2
- [x] Verify that node 0 is working properly (the one with the new UWB board), can use /Data_collection/inspect_raw_data.py to read all nodes.
- [x] Previous run of data_collection_server.py only logged from node 0 becasue the configured_anchor_id in uwb_hardware.py was reading from serial saying TWR[0] and publishing to uwb/anchor/0/vector instead of uwb/anchor/1/vector etc.
- [ ] Not sure if the server bringup is correct, in the logs, the number for phone_edges printed is sometimes 1. @hongyi i think shld be solved from prev point. 
- [ ] Verify that all nodes are publishing simultaneously /Data_collection/inspect_raw_data.py shows all 4 nodes

## Unverified (not sure if its a problem but we must check)
- [ ] The rotation matrix previously it was rotating the vectors +45 degree about y axis, however we are supposed to rotate down ( if the board reads 0 angle of elevation, the real vector is poining down towards the middle, hence should have negative z component) @jiyong ive changed it to -45 for now inside the package. Might be useful to find a way to test a singular vector if its reasonable before running it into the PGO pipeline @hongyi ok i see, logically makes sense, we can test.       

## TODO
- [ ] Confirm if PGO is correct 
- [ ] Streamline the data_collection_server
- [ ] config.py: ln 17 change back to `keepalive: int = 10`