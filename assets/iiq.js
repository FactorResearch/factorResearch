if (!window.dash_clientside) { window.dash_clientside = {}; }

(function preserveScrollAcrossOrientationChange() {
    let savedScroll = 0;
    window.addEventListener('orientationchange', function() {
        savedScroll = window.scrollY;
    });
    window.addEventListener('resize', function() {
        if (savedScroll > 0) {
            requestAnimationFrame(function() { window.scrollTo(0, savedScroll); });
        }
    });
})();

window.dash_clientside.iiq = {

    broadcastTicker: function(ticker) {
        if (ticker) {
            const bc = new BroadcastChannel('iiq-ticker-sync');
            bc.postMessage(ticker);
            localStorage.setItem('iiq-last-ticker', ticker);
        }
        return window.dash_clientside.no_update;
    },

    initReceiver: function(n) {
        if (!window._iiqChannel) {
            window._iiqChannel = new BroadcastChannel('iiq-ticker-sync');
            window._iiqChannel.onmessage = function(e) {
                window._iiqIncomingTicker = e.data;
                document.getElementById('iiq-remote-trigger').click();
            };
            const last = localStorage.getItem('iiq-last-ticker');
            if (last) {
                window._iiqIncomingTicker = last;
                document.getElementById('iiq-remote-trigger').click();
            }
        }
        return window.dash_clientside.no_update;
    },

    pushIncoming: function(n) {
        if (window._iiqIncomingTicker) {
            const t = window._iiqIncomingTicker;
            window._iiqIncomingTicker = null;
            return t;
        }
        return window.dash_clientside.no_update;
    },

    popOut: function(n) {
        if (n) { window.open(window.location.href, '_blank'); }
        return window.dash_clientside.no_update;
    }

};
