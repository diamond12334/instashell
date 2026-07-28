/*! coi-serviceworker v0.1.7 - Guido Zuidhof and contributors, licensed under MIT */
// Reloads the page through a service worker that injects COOP/COEP headers, so
// SharedArrayBuffer (needed for the game's blocking stdin) works on static hosts
// like GitHub Pages that cannot set those headers themselves.
let coepCredentialless = false;
if (typeof window === "undefined") {
    self.addEventListener("install", () => self.skipWaiting());
    self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

    self.addEventListener("message", (ev) => {
        if (!ev.data) return;
        if (ev.data.type === "deregister") {
            self.registration.unregister().then(() => self.clients.matchAll())
                .then((clients) => clients.forEach((c) => c.navigate(c.url)));
        } else if (ev.data.type === "coepCredentialless") {
            coepCredentialless = ev.data.value;
        }
    });

    self.addEventListener("fetch", (event) => {
        const r = event.request;
        if (r.cache === "only-if-cached" && r.mode !== "same-origin") return;
        const request = (coepCredentialless && r.mode === "no-cors")
            ? new Request(r, { credentials: "omit" }) : r;
        event.respondWith(fetch(request).then((response) => {
            if (response.status === 0) return response;
            const headers = new Headers(response.headers);
            headers.set("Cross-Origin-Embedder-Policy",
                coepCredentialless ? "credentialless" : "require-corp");
            headers.set("Cross-Origin-Opener-Policy", "same-origin");
            return new Response(response.body, {
                status: response.status, statusText: response.statusText, headers,
            });
        }).catch((e) => console.error(e)));
    });
} else {
    (() => {
        const reloadedBySelf = window.sessionStorage.getItem("coiReloadedBySelf");
        window.sessionStorage.removeItem("coiReloadedBySelf");
        const coep = reloadedBySelf ? window.sessionStorage.getItem("coiCoepHasFailed") : null;
        const coi = {
            shouldRegister: () => !reloadedBySelf,
            shouldDeregister: () => false,
            coepCredentialless: () => true,
            coepDegrade: () => true,
            doReload: () => window.location.reload(),
            quiet: false,
        };
        if (!window.crossOriginIsolated && !window.sessionStorage.getItem("coiReloadedBySelf")) {
            if (!navigator.serviceWorker) return;
            navigator.serviceWorker.register(window.document.currentScript.src)
                .then((registration) => {
                    registration.addEventListener("updatefound", () => {
                        window.sessionStorage.setItem("coiReloadedBySelf", "true");
                        window.location.reload();
                    });
                    if (registration.active && !navigator.serviceWorker.controller) {
                        window.sessionStorage.setItem("coiReloadedBySelf", "true");
                        window.location.reload();
                    }
                    registration.active && registration.active.postMessage(
                        { type: "coepCredentialless", value: coi.coepCredentialless() });
                }, (err) => !coi.quiet && console.error("COOP/COEP SW failed:", err));
        }
    })();
}
