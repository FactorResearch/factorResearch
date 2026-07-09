from __future__ import annotations

import html

from codes.services.analysis_snapshot_service import list_public_snapshots


def generate_analysis_sitemap(base_url: str, *, limit: int = 5000) -> str:
    base_url = base_url.rstrip("/")
    urls = []
    for snapshot in list_public_snapshots(limit=limit):
        loc = html.escape(f"{base_url}{snapshot.public_path}")
        lastmod = snapshot.analysis_date.isoformat()
        urls.append(
            "  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            "  </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )

