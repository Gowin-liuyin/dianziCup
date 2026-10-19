"""Record small synthetic inputs and actual DTO fields for independently failed cases."""

from __future__ import annotations

import json

from test_independent_r06_feed_boundaries import atom, entry, item, rss

from ai_intel.ingestion.sources.arxiv_atom import parse_arxiv_atom
from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss


def main() -> None:
    page_input = atom(entry(), 100, 0, 10)
    page = parse_arxiv_atom(page_input)
    date_input = rss(item(extra="<pubDate>Wed, 14 Oct 2026 07:00:00 +1260</pubDate>"))
    date_record = parse_trailofbits_rss(date_input)[0]
    uri_input = rss(item("https://blog.trailofbits.com/review/&#127;"))
    uri_record = parse_trailofbits_rss(uri_input)[0]
    license_input = atom(
        entry(extra="<arxiv:license>https://publisher.invalid/&#127;</arxiv:license>"), 1, 0, 1
    )
    license_record = parse_arxiv_atom(license_input).records[0]
    print(
        json.dumps(
            [
                {
                    "case": "underfull_nonfinal_page",
                    "synthetic_xml": page_input.decode(),
                    "expected": "AcademicContractError for incomplete nonfinal page",
                    "actual": {
                        "records": len(page.records),
                        "total_results": page.total_results,
                        "start_index": page.start_index,
                        "items_per_page": page.items_per_page,
                    },
                },
                {
                    "case": "invalid_timezone_minutes",
                    "synthetic_xml": date_input.decode(),
                    "expected": "FeedParseError for invalid numeric timezone +1260",
                    "actual": {"published_at": date_record.published_at},
                },
                {
                    "case": "rss_uri_del_control",
                    "synthetic_xml": uri_input.decode(),
                    "expected": "FeedParseError for DEL control in official article URI",
                    "actual": {"canonical_uri": uri_record.canonical_uri},
                },
                {
                    "case": "arxiv_license_del_control",
                    "synthetic_xml": license_input.decode(),
                    "expected": "AcademicContractError for DEL control in licence URI",
                    "actual": {
                        "license_identifier": license_record.license_identifier,
                        "full_text_fetched": license_record.full_text_fetched,
                    },
                },
            ],
            ensure_ascii=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
