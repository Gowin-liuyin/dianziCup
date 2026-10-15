import type { SourceKind } from "../../api/source-contracts";
import type { SourceCategory } from "../../api/document-contracts";

export const sourceCategoryLabels: Record<SourceCategory, string> = { structured_vulnerability: "结构化漏洞", vendor_advisory: "厂商公告", security_community: "安全社区", code_repository: "代码仓库", technical_blog: "技术博客", academic_paper: "学术论文", technical_standard: "技术标准", policy_regulation: "政策法规" };
interface SourceDefinition { name: string; category: SourceCategory; contentScope: string; scope: string; boundary: string; }

/** 冻结公开来源目录的中文投影；登记范围不表示启用、在线、已抓取或风险确认。 */
export const sourceCatalog: Record<SourceKind, SourceDefinition> = {
  nvd_ollama: { name: "NVD · Ollama", category: "structured_vulnerability", contentScope: "product_vulnerability", scope: "固定 Ollama 关键词的漏洞记录。", boundary: "关键词结果不代表全生态覆盖；每个任务处理一页。" },
  vllm_vendor: { name: "vLLM · 厂商公告", category: "vendor_advisory", contentScope: "vendor_advisory", scope: "vLLM 官方仓库公开安全公告。", boundary: "服务端处理分页游标；适用版本与资产影响仍需研判。" },
  osv_ollama: { name: "OSV · Ollama Go 包", category: "structured_vulnerability", contentScope: "package_vulnerability", scope: "固定 Go 包 github.com/ollama/ollama 的漏洞记录。", boundary: "包记录不等于当前运行资产受影响。" },
  avid_community: { name: "AVID · AI 社区报告", category: "security_community", contentScope: "community_report", scope: "AVID 固定公开仓库的 AI 风险报告。", boundary: "社区来源主张仍需原文与证据核验。" },
  ollama_releases: { name: "Ollama · 发布记录", category: "code_repository", contentScope: "release_metadata_not_confirmed_vulnerability", scope: "Ollama 官方仓库的发布元数据。", boundary: "发布记录尚未研判，不作为已确认漏洞。" },
  trailofbits_blog: { name: "Trail of Bits · 研究文章", category: "technical_blog", contentScope: "research_article", scope: "固定研究博客的 RSS 发现与片段。", boundary: "片段不等于全文，正文覆盖以保存版本为准。" },
  arxiv_security: { name: "arXiv · AI 安全论文", category: "academic_paper", contentScope: "paper_metadata_full_text_separate", scope: "固定 AI 安全检索的论文元数据与摘要。", boundary: "摘要与全文分开，研究主张不等于确认风险。" },
  nist_ai_rmf: { name: "NIST · AI RMF 1.0", category: "technical_standard", contentScope: "voluntary_framework", scope: "NIST AI RMF 1.0 原文框架。", boundary: "自愿框架，不表示已完成合规或资产影响核查。" },
  cac_generative_ai: { name: "网信办 · 生成式人工智能办法", category: "policy_regulation", contentScope: "official_policy_no_applicability_assessment", scope: "生成式人工智能服务管理办法官方资料。", boundary: "适用范围与义务以原文为准，尚未作适用判断。" },
};
