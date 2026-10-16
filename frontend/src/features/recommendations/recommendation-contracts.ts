import { ApiProblem, type CurrentUser } from "../../api/client";
import { isRecommendationIdentifier, normalizeDefinition } from "./schema-validation";
import { isGenerationResponse, isRecommendationPage, isRecommendationRecord, isReportPage, isReportReceipt, isSubscriptionPage, isSubscriptionRecord, type GenerationResponse, type RecommendationCandidate, type RecommendationPage, type RecommendationRecord, type ReportPage, type ReportReceipt, type SubscriptionPage, type SubscriptionRecord } from "./recommendation-wire-types";

export interface RecommendationScope { userId: string; tenantId: string; dataMode: CurrentUser["data_mode"] }
export class RecommendationScopeMismatch extends ApiProblem {
  constructor() { super(502, "invalid_response", false); this.name = "RecommendationScopeMismatch"; }
}
function invalid(): never { throw new ApiProblem(502, "invalid_response", true); }
function checkOwner(tenant: string, user: string, scope: RecommendationScope): void { if (tenant !== scope.tenantId || user !== scope.userId) throw new RecommendationScopeMismatch(); }
function checkIdentifier(value: string): void { if (!isRecommendationIdentifier(value)) return invalid(); }
function checkSubscription(record: SubscriptionRecord, scope: RecommendationScope, subscriptionId?: string): SubscriptionRecord {
  checkOwner(record.tenant_id, record.user_id, scope);
  if (subscriptionId !== undefined && record.subscription_id !== subscriptionId.toLowerCase()) throw new RecommendationScopeMismatch();
  const selectors = [record.spec.product_keys, record.spec.asset_ids, record.spec.risk_topics];
  if (!selectors.some((items) => items.length > 0) || selectors.some((items) => new Set(items).size !== items.length)) return invalid();
  return record;
}
function checkCandidate(candidate: RecommendationCandidate, scope: RecommendationScope, subscriptionId: string): void {
  checkOwner(candidate.tenant_id, candidate.user_id, scope);
  if (candidate.key.subscription_id !== subscriptionId.toLowerCase()) throw new RecommendationScopeMismatch();
  checkIdentifier(candidate.key.event_id);
  for (const assessment of candidate.assessments) {
    for (const identifier of [assessment.assessment_id, assessment.asset_id, assessment.asset_snapshot_id, assessment.rule_id]) checkIdentifier(identifier);
    for (const evidence of assessment.evidence) {
      if (evidence.scope.visibility === "tenant" && evidence.scope.tenant_id !== scope.tenantId) throw new RecommendationScopeMismatch();
      if (evidence.scope.visibility === "public" && evidence.scope.tenant_id !== null) return invalid();
      if (evidence.end_offset - evidence.start_offset !== [...evidence.quote_text].length) return invalid();
    }
  }
  for (const reason of candidate.reasons) {
    if (reason.code === "asset_assessment") {
      if (reason.assessment_id === null || reason.claim_id !== null || reason.citations.length !== 0 || !candidate.assessments.some((assessment) => assessment.assessment_id === reason.assessment_id)) return invalid();
    } else if (reason.claim_id === null || reason.citations.length === 0 || reason.assessment_id !== null) return invalid();
  }
}
function checkRecommendation(record: RecommendationRecord, scope: RecommendationScope, subscriptionId: string, recommendationId?: string): RecommendationRecord {
  checkCandidate(record.content, scope, subscriptionId);
  if (recommendationId !== undefined && record.recommendation_id !== recommendationId.toLowerCase()) throw new RecommendationScopeMismatch();
  return record;
}
function checkReport(record: ReportReceipt, scope: RecommendationScope, subscriptionId: string, reportId?: string): ReportReceipt {
  const report = record.content.report; checkOwner(report.tenant_id, report.user_id, scope);
  if (report.subscription_id !== subscriptionId.toLowerCase() || record.content.data_mode !== scope.dataMode || (reportId !== undefined && record.report_id !== reportId.toLowerCase())) throw new RecommendationScopeMismatch();
  const candidates = [...report.supported_risks, ...report.verification_items, ...report.excluded_items, ...report.intelligence_updates];
  const identities = candidates.map((candidate) => `${candidate.key.event_id}:${candidate.key.material_version}`);
  if (new Set(identities).size !== identities.length) return invalid();
  for (const candidate of candidates) { checkCandidate(candidate, scope, subscriptionId); if (!record.content.event_ids.includes(candidate.key.event_id)) throw new RecommendationScopeMismatch(); }
  for (const key of report.continuation_keys) if (key.subscription_id !== subscriptionId.toLowerCase()) throw new RecommendationScopeMismatch();
  return record;
}
function checkPage<T>(page: { items: T[]; next_cursor: string | null }, cursor: string | null, identify: (item: T) => string): void {
  if (page.items.length > 100 || (cursor !== null && page.next_cursor === cursor) || new Set(page.items.map(identify)).size !== page.items.length) return invalid();
}
export function parseSubscription(value: unknown, scope: RecommendationScope, subscriptionId?: string): SubscriptionRecord {
  const record = normalizeDefinition(value, "SubscriptionRecord"); if (!isSubscriptionRecord(record)) return invalid(); return checkSubscription(record, scope, subscriptionId);
}
export function parseSubscriptionPage(value: unknown, scope: RecommendationScope, cursor: string | null): SubscriptionPage {
  const page = normalizeDefinition(value, "SubscriptionPage"); if (!isSubscriptionPage(page)) return invalid(); checkPage(page, cursor, (record) => record.subscription_id); page.items.forEach((record) => checkSubscription(record, scope)); return page;
}
export function parseRecommendation(value: unknown, scope: RecommendationScope, subscriptionId: string, recommendationId?: string): RecommendationRecord {
  const record = normalizeDefinition(value, "RecommendationRecord"); if (!isRecommendationRecord(record)) return invalid(); return checkRecommendation(record, scope, subscriptionId, recommendationId);
}
export function parseRecommendationPage(value: unknown, scope: RecommendationScope, subscriptionId: string, cursor: string | null): RecommendationPage {
  const page = normalizeDefinition(value, "RecommendationPage"); if (!isRecommendationPage(page)) return invalid(); checkPage(page, cursor, (record) => record.recommendation_id); page.items.forEach((record) => checkRecommendation(record, scope, subscriptionId)); return page;
}
export function parseReport(value: unknown, scope: RecommendationScope, subscriptionId: string, reportId?: string): ReportReceipt {
  const record = normalizeDefinition(value, "ReportReceipt"); if (!isReportReceipt(record)) return invalid(); return checkReport(record, scope, subscriptionId, reportId);
}
export function parseReportPage(value: unknown, scope: RecommendationScope, subscriptionId: string, cursor: string | null): ReportPage {
  const page = normalizeDefinition(value, "ReportPage"); if (!isReportPage(page)) return invalid(); checkPage(page, cursor, (record) => record.report_id); page.items.forEach((record) => checkReport(record, scope, subscriptionId)); return page;
}
export function parseGeneration(value: unknown, scope: RecommendationScope): GenerationResponse {
  const receipt = normalizeDefinition(value, "GenerationResponse"); if (!isGenerationResponse(receipt)) return invalid();
  if (receipt.data_mode !== scope.dataMode) throw new RecommendationScopeMismatch();
  if (new Set(receipt.recommendation_ids).size !== receipt.recommendation_ids.length) return invalid();
  return receipt;
}
