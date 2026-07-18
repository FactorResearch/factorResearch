"""Shared visual shell for non-Dash research and legal routes."""

from __future__ import annotations

import html


def head(title: str) -> str:
    return f"""<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><link rel="stylesheet" href="/assets/style.css">
<script>(function(){{var t=localStorage.getItem('fr-theme')||'system';var l=t==='light'||(t==='system'&&matchMedia('(prefers-color-scheme: light)').matches);document.documentElement.classList.toggle('light',l);addEventListener('DOMContentLoaded',function(){{document.body.classList.toggle('light',l);document.querySelectorAll('[data-theme]').forEach(function(b){{b.classList.toggle('active',b.dataset.theme===t);b.addEventListener('click',function(){{localStorage.setItem('fr-theme',b.dataset.theme);location.reload();}});}});}});}})();</script></head>"""


def header(active: str = "") -> str:
    links = (("Screener", "/"), ("Analyze", "/?tab=analyze"), ("Portfolio", "/?tab=portfolio"), ("Factor Lab", "/?tab=factorlab"), ("Pricing", "/pricing"))
    nav = "".join(f'<a class="topbar-nav-btn{" active" if label.lower().replace(" ", "-") == active else ""}" href="{href}">{label}</a>' for label, href in links)
    return f"""<header class="topbar"><a class="topbar-brand" href="/"><img src="/assets/logo.svg" alt="Cenvarn" class="topbar-logo"><span class="topbar-title">Cenvarn</span></a>
<nav class="topbar-nav" aria-label="Primary navigation">{nav}</nav><div class="topbar-actions"><div class="theme-toggle" aria-label="Color theme">
<button class="theme-btn" data-theme="light" aria-label="Use light theme">☀</button><button class="theme-btn" data-theme="system" aria-label="Use system theme">◐</button><button class="theme-btn" data-theme="dark" aria-label="Use dark theme">☾</button></div></div></header>"""


def footer() -> str:
    return """<footer class="app-footer"><span>© Cenvarn · </span><a href="/terms">Terms of Service</a><span> · </span><a href="/privacy">Privacy Policy</a><span> · Not financial advice.</span></footer>"""
