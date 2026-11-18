---- MODULE OrderLifecycle ----
\* One Olist order from checkout to survey answer.
\* Survey policy (Olist data card): the survey email goes out when the order is delivered
\* OR when the promised (estimated) delivery date arrives, whichever comes first.
VARIABLES stage, promisePassed, deliveredLate, survey
vars == <<stage, promisePassed, deliveredLate, survey>>

Open == {"placed", "approved", "with_carrier"}

Init == stage = "placed" /\ promisePassed = FALSE /\ deliveredLate = FALSE /\ survey = "none"

PaymentApproved == stage = "placed" /\ stage' = "approved" /\ UNCHANGED <<promisePassed, deliveredLate, survey>>
SellerShips == stage = "approved" /\ stage' = "with_carrier" /\ UNCHANGED <<promisePassed, deliveredLate, survey>>
CarrierDelivers == stage = "with_carrier" /\ stage' = "delivered" /\ deliveredLate' = promisePassed /\ UNCHANGED <<promisePassed, survey>>
OrderCanceled == stage \in Open /\ stage' = "canceled" /\ UNCHANGED <<promisePassed, deliveredLate, survey>>
SellerOutOfStock == stage = "approved" /\ stage' = "unavailable" /\ UNCHANGED <<promisePassed, deliveredLate, survey>>
PromiseDatePasses == ~promisePassed /\ promisePassed' = TRUE /\ UNCHANGED <<stage, deliveredLate, survey>>
SurveySent == survey = "none" /\ (stage = "delivered" \/ promisePassed) /\ survey' = "sent" /\ UNCHANGED <<stage, promisePassed, deliveredLate>>
CustomerAnswers == survey = "sent" /\ survey' = "answered" /\ UNCHANGED <<stage, promisePassed, deliveredLate>>
Done == stage \in {"delivered", "canceled", "unavailable"} /\ promisePassed /\ survey = "answered" /\ UNCHANGED vars

Next == PaymentApproved \/ SellerShips \/ CarrierDelivers \/ OrderCanceled \/ SellerOutOfStock
        \/ PromiseDatePasses \/ SurveySent \/ CustomerAnswers \/ Done

Spec == Init /\ [][Next]_vars

\* Rule 1: "late" means it arrived after the promised date had passed (calendar day).
LateMeansArrivedAfterPromise == deliveredLate => (stage = "delivered" /\ promisePassed)
\* Rule 2: the survey only goes out under Olist's policy (delivered, or promise date reached).
SurveyFollowsPolicy == survey # "none" => (stage = "delivered" \/ promisePassed)
\* Rule 3 (the rule as people first state it): nobody reviews an order before it is delivered.
NoReviewBeforeDelivery == survey = "answered" => stage = "delivered"
====
