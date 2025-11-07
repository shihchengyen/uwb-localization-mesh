# GOD PLOT 

### General structure of the plot 
Each group of measurements, e.g. for each set of hearders 
` timestamp,ground_truth_x,ground_truth_y,ground_truth_z,pgo_x,pgo_y,pgo_z,orientation,filtered_binned_data_json,raw_binned_data_json,total_measurements,rejected_measurements,late_drops,rejection_reasons `
- The Anchors and the ground truth is plotted (as per the other examples above)
- Crosshair error bars (SDx, SDy) — simple & clear
    - Plot the (pgo_x, pgo_y) estimate as “×”.
    - Add horizontal error bar = SD(x) and vertical error bar = SD(y). (this should be from the PGO_X and PGO_Y)



The idea behind this plot is to describe the accuracy of the system in the most succinct way possible, i need it to demostrate a few things
1. Visualize clearly the accuracy against ground truth (This should be the avg of (pgo_x,pgo_y))
2. How do different orientations of the sensors affect the accuracy (A, B, C, U), should each have their own plots, so i should see 4 plots in total. (you should collapse the readings from the same plots)
3. How do different numbers of anchors affect the accuracy of the system, so you should walk up slowly from 1 anchor, 2, 3, 4. Here i would like you to use **masking** to get the numbers. I want you to walk it up from the least accurate to the most, in other words, if there is one anchor that just happens to be super accurate, you shouldnt use that, use the worst one to the best, we want to show "**worst case**" for 1 2 3 4 anchors 
    - The end result should show that as the number of anchors increases, the readings get more accurate and more stable 
4. It should show how the accuracy changes throughout the 4 positions measured 


### Final output 
In total, you should have **4 * 4 = 16** points in one graph, 4 positions, with measurements for 1 through 4 anchor cases
- Output the final 4 graphs into Data_collection/Data/28oct/god_plots



## Things to take note 
1. Ignore the Z readings, you can effectively squash out all the Z data in all the plots, do not use it in variance calculations etc 
2. use the filtered_binned_data.json 
3. The Datapoints in filtered_binned_data.json are in local coordinates, they have to be translated into global coordinates, to do that you can use the function in `packages/localization_algos/edge_creation`
```
def create_relative_measurement(
    anchor_id: int,
    phone_node_id: int,
    local_vector: np.ndarray
) -> Tuple[str, str, np.ndarray]: 
```
This will transform it to the global frame
4. Only plot in the global frame
5. To do PGO, the function is in `packages/localization_algos/pgo/solver.py`, you will also have to create edges using `packages/localization_algos/edge_creation/anchor_edges.py`, use the default position of the anchors 