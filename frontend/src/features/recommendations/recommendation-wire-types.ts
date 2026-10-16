/** Generated from recommendation_api_v1.json. Runtime normalization applies declared defaults before typed guards. */
import { matchesDefinition } from "./schema-validation";

export type SubscriptionSpec = {
  product_keys: (string)[];
  asset_ids: (string)[];
  risk_topics: (string)[];
  maximum_priority_bucket: 0 | 1 | 2 | 3;
  enabled: boolean;
};

export function isSubscriptionSpec(value: unknown): value is SubscriptionSpec { return matchesDefinition(value, "SubscriptionSpec"); }

export type SubscriptionRecord = {
  schema_version: "r15-subscription-1";
  subscription_id: string;
  tenant_id: string;
  user_id: string;
  version: number;
  spec: SubscriptionSpec;
  spec_sha256: string;
  created_at: string;
  updated_at: string;
};

export function isSubscriptionRecord(value: unknown): value is SubscriptionRecord { return matchesDefinition(value, "SubscriptionRecord"); }

export type SubscriptionPage = {
  items: (SubscriptionRecord)[];
  next_cursor: string | null;
};

export function isSubscriptionPage(value: unknown): value is SubscriptionPage { return matchesDefinition(value, "SubscriptionPage"); }

export type AssessmentReference = {
  assessment_id: string;
  asset_id: string;
  asset_snapshot_id: string;
  rule_id: string;
  rule_version: number;
  status: AssessmentStatus;
  knowledge_epoch: number | null;
  scope_epoch_map: Record<string, number | null>;
  input_digest: string;
  evidence: (EvidenceReference)[];
  missing_requirements: (string)[];
  conflicts: (string)[];
  limitations: (string)[];
};

export function isAssessmentReference(value: unknown): value is AssessmentReference { return matchesDefinition(value, "AssessmentReference"); }

export type AssessmentStatus = "supported_applicability" | "excluded_with_evidence" | "insufficient_evidence" | "conflicting_evidence";

export function isAssessmentStatus(value: unknown): value is AssessmentStatus { return matchesDefinition(value, "AssessmentStatus"); }

export type CitationProjection = {
  evidence_id: string;
  revision_id: string;
  quote: string;
  locator: string;
  source_uri: string;
};

export function isCitationProjection(value: unknown): value is CitationProjection { return matchesDefinition(value, "CitationProjection"); }

export type ClaimStatus = "supported" | "disputed" | "unverified" | "superseded" | "withdrawn";

export function isClaimStatus(value: unknown): value is ClaimStatus { return matchesDefinition(value, "ClaimStatus"); }

export type EvidenceReference = {
  evidence_id: string;
  source_id: string;
  document_id: string;
  revision_id: string;
  block_id: string;
  start_offset: number;
  end_offset: number;
  quote_text: string;
  quote_sha256: string;
  scope: VisibilityScope;
  support_kind: "supports" | "refutes" | "context";
  validation_status: "validated" | "unverified";
};

export function isEvidenceReference(value: unknown): value is EvidenceReference { return matchesDefinition(value, "EvidenceReference"); }

export type FreshnessStatus = "current" | "stale" | "unknown";

export function isFreshnessStatus(value: unknown): value is FreshnessStatus { return matchesDefinition(value, "FreshnessStatus"); }

export type RecommendationCandidate = {
  key: RecommendationKey;
  tenant_id: string;
  user_id: string;
  policy_version: "r15-recommendation-policy-1";
  kind: "supported_risk" | "prioritize_verification" | "excluded_with_evidence" | "intelligence_update";
  priority_bucket: 0 | 1 | 2 | 3;
  reasons: (RecommendationReason)[];
  assessments: (AssessmentReference)[];
  observed_at: string;
  source_changed_at: string | null;
  valid_from: string;
  valid_until: string | null;
  validity_as_of: string;
  freshness_at_cutoff: FreshnessStatus;
  current_status: ClaimStatus;
  current_freshness: FreshnessStatus;
  current_state_checked_at: string;
  limitations: (string)[];
};

export function isRecommendationCandidate(value: unknown): value is RecommendationCandidate { return matchesDefinition(value, "RecommendationCandidate"); }

export type RecommendationKey = {
  subscription_id: string;
  event_id: string;
  material_version: string;
};

export function isRecommendationKey(value: unknown): value is RecommendationKey { return matchesDefinition(value, "RecommendationKey"); }

export type RecommendationReason = {
  code: "product_match" | "risk_topic_match" | "asset_assessment" | "high_consequence";
  matched_key: string;
  claim_id: string | null;
  citations: (CitationProjection)[];
  assessment_id: string | null;
};

export function isRecommendationReason(value: unknown): value is RecommendationReason { return matchesDefinition(value, "RecommendationReason"); }

export type VisibilityScope = {
  visibility: string;
  tenant_id: string | null;
};

export function isVisibilityScope(value: unknown): value is VisibilityScope { return matchesDefinition(value, "VisibilityScope"); }

export type RecommendationRecord = {
  recommendation_id: string;
  generation_id: string;
  content_sha256: string;
  content: RecommendationCandidate;
  created_at: string;
  read_at: string | null;
  current_status: "current" | "stale" | "withdrawn" | "unknown";
  current_reason: string;
  current_checked_at: string;
};

export function isRecommendationRecord(value: unknown): value is RecommendationRecord { return matchesDefinition(value, "RecommendationRecord"); }

export type RecommendationPage = {
  items: (RecommendationRecord)[];
  next_cursor: string | null;
};

export function isRecommendationPage(value: unknown): value is RecommendationPage { return matchesDefinition(value, "RecommendationPage"); }

export type CandidateGap = {
  event_id: string | null;
  asset_id: string | null;
  code: "no_current_semantic_support" | "selector_evidence_budget_exceeded" | "claim_not_current" | "source_time_unavailable" | "assessment_not_current" | "assessment_unavailable" | "graph_partial" | "source_withdrawn" | "event_not_active" | "unsupported_topic" | "input_scope_partial" | "consequence_selector_unavailable";
};

export function isCandidateGap(value: unknown): value is CandidateGap { return matchesDefinition(value, "CandidateGap"); }

export type ReportCandidate = {
  policy_version: "r15-recommendation-policy-1";
  subscription_id: string;
  tenant_id: string;
  user_id: string;
  frequency: "day" | "week";
  window_start: string;
  cutoff_at: string;
  generated_at: string;
  temporal_mode: "as_of_cutoff";
  window_basis: "first_material_observed_at";
  supported_risks: (RecommendationCandidate)[];
  verification_items: (RecommendationCandidate)[];
  excluded_items: (RecommendationCandidate)[];
  intelligence_updates: (RecommendationCandidate)[];
  partial: boolean;
  continuation_keys: (RecommendationKey)[];
  stop_reason: "disabled" | "no_items_in_window" | "complete" | "item_budget";
  limitations: (string)[];
};

export function isReportCandidate(value: unknown): value is ReportCandidate { return matchesDefinition(value, "ReportCandidate"); }

export type StoredReportContent = {
  schema_version: "r15-report-1";
  report: ReportCandidate;
  generation_id: string;
  event_ids: (string)[];
  data_mode: "live" | "fixture";
  gaps: (CandidateGap)[];
  max_items: number;
};

export function isStoredReportContent(value: unknown): value is StoredReportContent { return matchesDefinition(value, "StoredReportContent"); }

export type ReportReceipt = {
  report_id: string;
  content_sha256: string;
  content: StoredReportContent;
  current_status: "current" | "stale" | "withdrawn" | "unknown";
  current_reason: string;
  current_checked_at: string;
  reused: boolean;
};

export function isReportReceipt(value: unknown): value is ReportReceipt { return matchesDefinition(value, "ReportReceipt"); }

export type ReportPage = {
  items: (ReportReceipt)[];
  next_cursor: string | null;
};

export function isReportPage(value: unknown): value is ReportPage { return matchesDefinition(value, "ReportPage"); }

export type PublicSubscriptionSpec = {
  product_keys: (string)[];
  asset_ids: (string)[];
  risk_topics: (string)[];
  enabled: boolean;
  minimum_priority: 0 | 1 | 2 | 3;
};

export function isPublicSubscriptionSpec(value: unknown): value is PublicSubscriptionSpec { return matchesDefinition(value, "PublicSubscriptionSpec"); }

export type CreateSubscription = {
  spec: PublicSubscriptionSpec;
};

export function isCreateSubscription(value: unknown): value is CreateSubscription { return matchesDefinition(value, "CreateSubscription"); }

export type ReplaceSubscription = {
  expected_version: number;
  spec: PublicSubscriptionSpec;
};

export function isReplaceSubscription(value: unknown): value is ReplaceSubscription { return matchesDefinition(value, "ReplaceSubscription"); }

export type SetSubscriptionEnabled = {
  expected_version: number;
  enabled: boolean;
};

export function isSetSubscriptionEnabled(value: unknown): value is SetSubscriptionEnabled { return matchesDefinition(value, "SetSubscriptionEnabled"); }

export type GenerateRecommendations = {
  max_candidates: number;
};

export function isGenerateRecommendations(value: unknown): value is GenerateRecommendations { return matchesDefinition(value, "GenerateRecommendations"); }

export type GenerationResponse = {
  generation_id: string;
  recommendation_ids: (string)[];
  partial: boolean;
  gaps: (CandidateGap)[];
  reused: boolean;
  data_mode: "live" | "fixture";
};

export function isGenerationResponse(value: unknown): value is GenerationResponse { return matchesDefinition(value, "GenerationResponse"); }

export type CreateReport = {
  subscription_id: string;
  generation_id: string;
  frequency: "day" | "week";
  max_items: number;
};

export function isCreateReport(value: unknown): value is CreateReport { return matchesDefinition(value, "CreateReport"); }
