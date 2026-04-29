Near Real-Time rPPG Integration
Build a small prototype that takes a 60-second face video as input, processes it in 5-second chunks, and generates:
BPM estimate per 5-second chunk
Overall BPM estimate for the full 60 seconds
Basic runtime/performance metrics
You may choose the stack and implementation approach. We care most about your ability to integrate a CV model into a near real-time pipeline and about the accuracy of the data. You can use any of the the open-source rPPG models listed below (or any other) as the starting point:
https://github.com/KegangWangCCNU/open-rppg: Heart Rate and Respiratory Rate
https://github.com/ubicomplab/rPPG-Toolbox: Heart Rate and Respiratory Rate
https://github.com/prouast/heartbeat: Heart Rate
https://github.com/prouast/heartbeat: Heart Rate
https://github.com/eugenelet/Meta-rPPG: Heart Rate
Special bonus point for including Respiratory Rate and any other biomarkers as part of the integration workflow. 
Expected output:
Link to test prototype
Sample output showing chunk-level BPM + final BPM
Any notes on model performance, latency, and failure cases
We strongly expect candidates to use AI as much as possible. We only ask that you share how you used AI tools.
Evaluation criteria:
Performance of the model (accuracy of the estimation)
Clean integration of the rPPG model
Ability to process video incrementally in 5-second windows
Reasonable BPM aggregation logic
Code clarity and reliability
Practical thinking around real-time deployment constraints
