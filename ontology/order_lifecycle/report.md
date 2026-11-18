# OrderLifecycle

TLC reached 29 states and 56 steps. The chart draws 12 states and 11 arrows.
The chart does not draw 4 steps that stay in one chart state.

## NoReviewBeforeDelivery breaks
The shortest path has 3 steps:
0. Order Placed, Promise Before promise date, Survey No survey
1. the promised date arrives: Order Placed, Promise Promise date passed, Survey No survey
2. Olist emails the survey: Order Placed, Promise Promise date passed, Survey Survey sent
3. customer answers the survey: Order Placed, Promise Promise date passed, Survey Survey answered

## Rules that hold
LateMeansArrivedAfterPromise, SurveyFollowsPolicy, NoDeadlock
