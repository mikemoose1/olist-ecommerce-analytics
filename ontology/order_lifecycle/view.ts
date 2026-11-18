const stageWords: Record<string, string> = {
  placed: "Placed", approved: "Paid", with_carrier: "With carrier",
  delivered: "Delivered", canceled: "Canceled", unavailable: "Unavailable",
};
export const title = "Olist order: stages, promise date and survey";
export const state = (v: any) => ({
  Order: v.stage === "delivered" ? (v.deliveredLate ? "Delivered late" : "Delivered on time") : stageWords[v.stage],
  Promise: v.promisePassed ? "Promise date passed" : "Before promise date",
  Survey: v.survey === "none" ? "No survey" : v.survey === "sent" ? "Survey sent" : "Survey answered",
});
export const step = (a: string) => ({
  PaymentApproved: "payment is approved",
  SellerShips: "seller hands it to the carrier",
  CarrierDelivers: "carrier delivers",
  OrderCanceled: "order is canceled",
  SellerOutOfStock: "seller can't fill it",
  PromiseDatePasses: "the promised date arrives",
  SurveySent: "Olist emails the survey",
  CustomerAnswers: "customer answers the survey",
  Done: null,
} as Record<string, string | null>)[a] ?? a;
