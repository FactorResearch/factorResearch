from __future__ import annotations

import html

from codes.services.analysis_snapshot_service import list_public_snapshots


def generate_analysis_sitemap(base_url: str, *, limit: int = 5000) -> str:
    base_url = base_url.rstrip("/")
    urls = []
    seen = set()
    for index, snapshot in enumerate(list_public_snapshots(limit=limit)):
        paths = (snapshot.company_path, snapshot.permanent_path)
        lastmod = snapshot.analysis_date.isoformat()
        for path in paths:
            if path in seen:
                continue
            seen.add(path)
            loc = html.escape(f"{base_url}{path}")
            priority = "0.9" if path == snapshot.company_path else ("0.8" if index < 100 else "0.6")
            urls.append(
                "  <url>\n"
                f"    <loc>{loc}</loc>\n"
                f"    <lastmod>{lastmod}</lastmod>\n"
                "    <changefreq>weekly</changefreq>\n"
                f"    <priority>{priority}</priority>\n"
                "  </url>"
            )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
