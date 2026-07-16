"""Optional third-party analytics bootstrapping snippets."""

from __future__ import annotations

import os


def build_head_snippets() -> str:
    snippets: list[str] = []

    posthog_key = os.environ.get("POSTHOG_KEY")
    posthog_host = os.environ.get("POSTHOG_HOST", "https://app.posthog.com")
    if posthog_key:
        snippets.append(
            "<script>"
            "!function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a)"
            "{function g(t,e){var o=e.split('.');2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function()"
            "{t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement('script'))"
            ".type='text/javascript',p.async=!0,p.src=s.api_host+'/static/array.js',"
            "(r=t.getElementsByTagName('script')[0]).parentNode.insertBefore(p,r);var u=e;"
            "for(void 0!==a?u=e[a]=[]:a='posthog',u.people=u.people||[],u.toString=function(t){var e='posthog';"
            "return'posthog'!==a&&(e+='.'+a),t||(e+=' (stub)'),e},u.people.toString=function(){return u.toString(1)+'.people (stub)'},"
            "o='capture identify alias people.set people.set_once register register_once unregister reset opt_in_capturing opt_out_capturing'.split(' '),n=0;n<o.length;n++)g(u,o[n]);"
            "e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);"
            f"posthog.init('{posthog_key}',{{api_host:'{posthog_host}',autocapture:false,capture_pageview:false,disable_session_recording:true,mask_all_text:true,mask_all_element_attributes:true}});"
            "</script>"
        )

    clarity_id = (
        os.environ.get("MICROSOFT_CLARITY_ID")
        if os.environ.get("ENABLE_MASKED_SESSION_REPLAY", "").lower() in {"1", "true", "yes"}
        else None
    )
    if clarity_id:
        snippets.append(
            "<script>"
            "document.documentElement.setAttribute('data-clarity-mask','true');"
            "(function(c,l,a,r,i,t,y){c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};"
            "t=l.createElement(r);t.async=1;t.src='https://www.clarity.ms/tag/'+i;"
            "y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);"
            f"}})(window,document,'clarity','script','{clarity_id}');"
            "</script>"
        )

    sentry_dsn = os.environ.get("SENTRY_DSN")
    if sentry_dsn:
        snippets.append(
            "<script src='https://browser.sentry-cdn.com/7.120.3/bundle.min.js' crossorigin='anonymous'></script>"
            "<script>"
            f"Sentry.init({{dsn:'{sentry_dsn}'}});"
            "</script>"
        )

    if posthog_key or sentry_dsn:
        snippets.append(
            "<script>"
            "(function(){"
            "function syncAnalyticsContext(ctx){"
            "if(window.posthog){"
            "if(ctx.analytics_opt_out){"
            "if(window.posthog.opt_out_capturing){window.posthog.opt_out_capturing();}"
            "}else{"
            "if(window.posthog.opt_in_capturing){window.posthog.opt_in_capturing();}"
            "if(ctx.authenticated&&ctx.user_id&&window.posthog.identify){window.posthog.identify(ctx.user_id);}"
            "}"
            "}"
            "if(window.Sentry&&window.Sentry.setUser){"
            "if(ctx.authenticated&&ctx.user_id&&!ctx.analytics_opt_out){window.Sentry.setUser({id:ctx.user_id});}"
            "else{window.Sentry.setUser(null);}"
            "}"
            "}"
            "window.factorResearchSyncAnalyticsContext=syncAnalyticsContext;"
            "fetch('/privacy/analytics',{credentials:'same-origin'})"
            ".then(function(r){return r.json();})"
            ".then(syncAnalyticsContext)"
            ".catch(function(){});"
            "})();"
            "</script>"
        )

    return "".join(snippets)
