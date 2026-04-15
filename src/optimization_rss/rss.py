from datetime import timezone
from pathlib import Path

from feedgen.feed import FeedGenerator

from optimization_rss.config import FEED_DESCRIPTION, FEED_LINK, FEED_TITLE
from optimization_rss.dedupe import canonical_id
from optimization_rss.models import Paper

MAX_FEED_ITEMS = 500


def generate_feed(papers: list[Paper], output_path: Path) -> None:
    sorted_papers = sorted(papers, key=lambda p: p.first_seen_at, reverse=True)
    sorted_papers = sorted_papers[:MAX_FEED_ITEMS]

    fg = FeedGenerator()
    fg.title(FEED_TITLE)
    fg.link(href=FEED_LINK, rel="self")
    fg.description(FEED_DESCRIPTION)
    fg.language("en")

    if sorted_papers:
        fg.lastBuildDate(sorted_papers[0].first_seen_at.replace(tzinfo=timezone.utc))

    for paper in sorted_papers:
        fe = fg.add_entry(order="append")
        fe.id(canonical_id(paper))
        fe.title(paper.title)
        fe.link(href=paper.paper_url)
        fe.description(paper.abstract or "No abstract available.")
        fe.pubDate(paper.first_seen_at.replace(tzinfo=timezone.utc))

        if paper.authors:
            fe.author({"name": ", ".join(paper.authors)})

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(output_path), pretty=True)
    print(f"[rss] Feed written to {output_path} ({len(sorted_papers)} items)")
