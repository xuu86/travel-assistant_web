export type ActivityEnvironment = "indoor" | "outdoor" | "unknown";

export type OptionalCheckupFields = {
  stayMinutes?: number | null;
  transitMinutes?: number | null;
  environment?: ActivityEnvironment;
  walkKm?: number | null;
  stairSteps?: number | null;
  transfers?: number | null;
};
