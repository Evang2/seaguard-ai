import type {
  RiskAssessment,
} from "../api/types";

function describeMlPercentile(
  percentile: number,
): string {
  if (percentile >= 99.5) {
    return "extremely unusual";
  }

  if (percentile >= 99) {
    return "very unusual";
  }

  if (percentile >= 95) {
    return "unusual";
  }

  return "not strongly unusual";
}

function formatRuleCount(
  count: number,
): string {
  return count === 1
    ? "1 rule flag"
    : `${count} rule flags`;
}

export function buildRiskExplanation(
  assessment: RiskAssessment,
): string {
  const percentile =
    assessment.ml_anomaly_percentile;

  const mlDescription =
    describeMlPercentile(
      percentile,
    );

  const priority =
    assessment.risk_level
      .toUpperCase();

  const ruleCount =
    assessment.rule_flag_count;

  const ruleSeverity =
    assessment.rule_severity
      .toUpperCase();

  const mlSentence =
    `The ML detector ranked this observation `
    + `in the ${percentile.toFixed(2)}th percentile, `
    + `making it ${mlDescription} relative to `
    + `the analyzed AIS observations.`;

  let evidenceSentence: string;

  if (
    assessment.detector_agreement
    && ruleCount > 0
  ) {
    evidenceSentence =
      `The rule engine also triggered `
      + `${formatRuleCount(ruleCount)} `
      + `with ${ruleSeverity} rule severity, `
      + `so both detection methods support investigation.`;
  } else if (ruleCount > 0) {
    evidenceSentence =
      `The rule engine triggered `
      + `${formatRuleCount(ruleCount)} `
      + `with ${ruleSeverity} rule severity. `
      + `The persisted detector-agreement flag is false, `
      + `so the evidence is not confirmed by both `
      + `detection methods.`;
  } else {
    evidenceSentence =
      `No deterministic rule flags were recorded `
      + `for this observation, so its investigation `
      + `priority is being driven primarily by the `
      + `ML-based evidence.`;
  }

  const prioritySentence =
    `SeaGuard therefore assigns this observation `
    + `${priority} investigation priority.`;

  return [
    mlSentence,
    evidenceSentence,
    prioritySentence,
  ].join(" ");
}

export function formatEngineReasons(
  rawReasons: string,
): string[] {
  const trimmed =
    rawReasons.trim();

  if (!trimmed) {
    return [];
  }

  /*
   * Support JSON arrays if the backend
   * ever serializes reasons that way.
   */
  try {
    const parsed: unknown =
      JSON.parse(trimmed);

    if (
      Array.isArray(parsed)
      && parsed.every(
        (item) =>
          typeof item === "string",
      )
    ) {
      return parsed.map(
        (item) =>
          humanizeReason(item),
      );
    }
  } catch {
    /*
     * Not JSON. Continue with the normal
     * text parser below.
     */
  }

  return trimmed
    .split(
      /\n+|;\s*|\|\s*/,
    )
    .map(
      (reason) =>
        humanizeReason(reason),
    )
    .filter(Boolean);
}

function humanizeReason(
  reason: string,
): string {
  const cleaned =
    reason
      .trim()
      .replaceAll("_", " ")
      .replace(
        /\s+/g,
        " ",
      );

  if (!cleaned) {
    return "";
  }

  return (
    cleaned.charAt(0)
      .toUpperCase()
    + cleaned.slice(1)
  );
}