import { useMemo } from "react";
import { explainabilitySchema, type Explainability, type ResearchReport } from "@/types/schemas";
import { CreditSafetyBreakdownPanel } from "./CreditSafetyBreakdownPanel";
import { ConfidenceCalibrationPanel } from "./ConfidenceCalibrationPanel";
import { LiquidityAssessmentPanel } from "./LiquidityAssessmentPanel";
import { StructureAnalysisPanel } from "./StructureAnalysisPanel";
import { PositionRiskPanel } from "./PositionRiskPanel";
import { MacroTransmissionPanel } from "./MacroTransmissionPanel";
import { HistoricalAnalogPanel } from "./HistoricalAnalogPanel";
import { AssessmentReasoningPanel } from "./AssessmentReasoningPanel";
import { DecisionJustificationPanel } from "./DecisionJustificationPanel";
import { DecisionSensitivityPanel } from "./DecisionSensitivityPanel";

function parseExplainability(report: ResearchReport): Explainability | null {
  const raw = (report as unknown as { explainability?: unknown }).explainability;
  if (!raw || typeof raw !== "object") return null;
  const parsed = explainabilitySchema.safeParse(raw);
  if (!parsed.success) return raw as Explainability;
  return parsed.data;
}

export function ExplainabilitySection({ report }: { report: ResearchReport }) {
  const layer = useMemo(() => parseExplainability(report), [report]);
  if (!layer) return null;

  const hasAny =
    layer.credit_safety_breakdown ||
    layer.confidence_calibration ||
    layer.liquidity_assessment ||
    layer.structure_analysis ||
    layer.position_risk ||
    layer.macro_transmission ||
    layer.historical_analogs ||
    layer.assessment_reasoning ||
    layer.decision_justification ||
    layer.decision_sensitivity;
  if (!hasAny) return null;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-bold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
        Why? — Reasoning Behind The Card
      </h2>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {layer.credit_safety_breakdown && (
          <CreditSafetyBreakdownPanel data={layer.credit_safety_breakdown} />
        )}
        {layer.confidence_calibration && (
          <ConfidenceCalibrationPanel data={layer.confidence_calibration} />
        )}
        {layer.liquidity_assessment && (
          <LiquidityAssessmentPanel data={layer.liquidity_assessment} />
        )}
        {layer.position_risk && <PositionRiskPanel data={layer.position_risk} />}
        {layer.structure_analysis && (
          <div className="lg:col-span-2">
            <StructureAnalysisPanel data={layer.structure_analysis} />
          </div>
        )}
        {layer.macro_transmission && (
          <MacroTransmissionPanel data={layer.macro_transmission} />
        )}
        {layer.historical_analogs && (
          <HistoricalAnalogPanel data={layer.historical_analogs} />
        )}
        {layer.assessment_reasoning && (
          <div className="lg:col-span-2">
            <AssessmentReasoningPanel data={layer.assessment_reasoning} />
          </div>
        )}
        {layer.decision_justification && (
          <div className="lg:col-span-2">
            <DecisionJustificationPanel data={layer.decision_justification} />
          </div>
        )}
        {layer.decision_sensitivity && (
          <div className="lg:col-span-2">
            <DecisionSensitivityPanel data={layer.decision_sensitivity} />
          </div>
        )}
      </div>
    </section>
  );
}
