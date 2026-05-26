1. Open the Queue Job Functions menu.
2. Open the job function you want to profile.
3. In the Profiler group, enable Profiling and set the Profiling users
	(optional) and Profiling until.
4. Run the job with the selected user (the queue job runner usually executes
	as the superuser).
5. Inspect the generated entries in `ir_profile` to review the captured
	profiling data.