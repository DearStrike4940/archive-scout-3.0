# Beta 1.2.1 CI hotfix

The macOS Intel Python 3.12 job completed all application tests except one timing-sensitive concurrency test. The test required six simulated 40 ms page requests with three workers to finish in under 200 ms. On the GitHub macOS runner, thread startup and scheduler overhead raised the measured time to about 296 ms even though the recorded active-worker count proved that requests overlapped and remained bounded.

The hotfix removes the wall-clock deadline and retains the deterministic assertions that matter:

- results remain in page order;
- at least two requests overlap;
- active requests never exceed the configured worker count.

No indexing, networking, database, or packaging behavior changed.
