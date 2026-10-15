const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
}[c]));

const PREVIEW_LIMIT = 3;

const list = (s) => s.split(",").map((x) => x.trim()).filter(Boolean);
const num = (id) => {
    const value = $(id).value;
    return value === "" ? null : Number(value);
};

async function api(url, opts) {
    const response = await fetch(url, opts);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
}

const post = (url, body) => api(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
});

function setMsg(id, text, ok) {
    $(id).innerHTML = '<span class="' + (ok ? "ok" : "err") + '">' + esc(text) + "</span>";
}

function renderRow(r, opts) {
    const facilityItems = (r.facilities || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean)
        .slice(0, 3)
        .map((facility) => '<span class="facility-pill">' + esc(facility) + "</span>")
        .join("");

    const hoverInfo = [
        r.address ? '<div class="meta-row"><span class="meta-label">Address</span><span>' + esc(r.address) + '</span></div>' : "",
        r.contact ? '<div class="meta-row"><span class="meta-label">Contact</span><span>' + esc(r.contact) + '</span></div>' : "",
        '<div class="meta-row"><span class="meta-label">Facilities</span><span>' + esc((r.facilities || "").split(",").join(", ")) + '</span></div>',
    ].join("");

    return "<tr class=\"listing-row\">" + (opts.pick ? '<td><input type="checkbox" class="pick" value="' + r.id + '"></td>' : "") +
        '<td class="title-cell"><div class="title-stack"><strong>' + esc(r.title) + '</strong>' +
        '<div class="hover-card">' + hoverInfo + "</div></div></td>" +
        "<td>" + Number(r.price).toLocaleString() + "</td><td>" + esc(r.distance_km) + " km</td>" +
        '<td><div class="facility-list">' + (facilityItems || '<span class="facility-pill muted">No details</span>') + "</div></td>" +
        (opts.score ? "<td>" + esc(r.score) + "</td>" : "") +
        (opts.report ? '<td><button class="danger" data-report="' + r.id + '">Report outdated</button></td>' : "") +
        "</tr>";
}

function table(rows, opts) {
    if (!rows.length) return '<p class="hint">No listings found.</p>';

    const previewRows = rows.slice(0, PREVIEW_LIMIT);
    const remainingRows = rows.slice(PREVIEW_LIMIT);
    const colCount = (opts.pick ? 1 : 0) + 4 + (opts.score ? 1 : 0) + (opts.report ? 1 : 0);

    let html = "<table><tr>" + (opts.pick ? "<th></th>" : "") + "<th>Title</th><th>Price</th><th>Distance</th><th>Facilities</th>" +
        (opts.score ? "<th>Score</th>" : "") + (opts.report ? "<th></th>" : "") + "</tr>";

    previewRows.forEach((r) => {
        html += renderRow(r, opts);
    });

    if (remainingRows.length) {
        html += '<tr><td colspan="' + colCount + '"><details class="remaining-menu"><summary>Show remaining listings (' + remainingRows.length + ')</summary><div class="remaining-menu-body">' +
            remainingRows.map((r) => '<div class="remaining-item"><strong>' + esc(r.title) + '</strong><span>' + Number(r.price).toLocaleString() + ' • ' + esc(r.distance_km) + ' km</span></div>').join("") +
            '</div></details></td></tr>';
    }

    return html + "</table>";
}

async function search() {
    const params = new URLSearchParams();
    [["min_price", "s_min"], ["max_price", "s_max"], ["max_distance", "s_dist"]].forEach(([key, id]) => {
        if ($(id).value !== "") params.append(key, $(id).value);
    });

    try {
        const rows = await api("/api/listings?" + params.toString());
        $("searchMsg").textContent = rows.length + " listing(s) found";
        $("results").innerHTML = table(rows, { pick: true, report: true });
        $("compare").innerHTML = "";
    } catch (error) {
        setMsg("searchMsg", error.message, false);
    }
}

async function addListing() {
    try {
        const payload = {
            title: $("a_title").value,
            address: $("a_address").value,
            price: num("a_price"),
            distance_km: num("a_dist"),
            facilities: $("a_fac").value,
            contact: $("a_contact").value,
        };

        const result = await post("/api/listings", payload);
        setMsg("addMsg", "Listing added (id " + result.id + ")", true);
        ["a_title", "a_address", "a_price", "a_dist", "a_fac", "a_contact"].forEach((id) => { $(id).value = ""; });
        search();
    } catch (error) {
        setMsg("addMsg", error.message, false);
    }
}

async function compareSelected() {
    const ids = [...document.querySelectorAll(".pick:checked")].map((checkbox) => checkbox.value);
    if (ids.length < 2) {
        setMsg("searchMsg", "Tick at least two listings to compare.", false);
        return;
    }

    try {
        const data = await api("/api/compare?ids=" + ids.join(","));
        let html = "<h3>Facility comparison</h3><table><tr><th>Facility</th>" +
            data.listings.map((listing) => "<th>" + esc(listing.title) + "<br>" + Number(listing.price).toLocaleString() + " / " + esc(listing.distance_km) + " km</th>").join("") +
            "</tr>";

        Object.keys(data.facility_matrix).forEach((facility) => {
            html += "<tr><td>" + esc(facility) + "</td>" +
                data.listings.map((listing) => data.facility_matrix[facility][listing.id] ? '<td class="yes">&#10003;</td>' : '<td class="no">&#10007;</td>').join("") +
                "</tr>";
        });

        html += "</table>";
        if (data.shared_by_all.length) {
            html += '<p class="hint">Offered by all: ' + esc(data.shared_by_all.join(", ")) + "</p>";
        }

        $("compare").innerHTML = html;
    } catch (error) {
        setMsg("searchMsg", error.message, false);
    }
}

async function reportListing(event) {
    const id = event.target.getAttribute("data-report");
    if (!id) return;

    const reason = prompt("Why is this listing outdated? (optional)");
    if (reason === null) return;

    try {
        const response = await post("/api/listings/" + id + "/report", { reason });
        setMsg("searchMsg", response.hidden ? "Reported. This listing is now hidden as outdated." : "Thanks, reported (" + response.reports + " report(s) so far).", true);
        if (response.hidden) search();
    } catch (error) {
        setMsg("searchMsg", error.message, false);
    }
}

async function recommendListings() {
    try {
        const payload = {
            budget: num("r_budget"),
            max_distance: num("r_dist"),
            required: list($("r_req").value),
            preferred: list($("r_pref").value),
            weights: {
                price: num("w_price") || 0,
                distance: num("w_dist") || 0,
                facilities: num("w_fac") || 0,
            },
        };

        const rows = await post("/api/recommend", payload);
        $("recMsg").textContent = rows.length ? "Best match first (higher score is better)" : "";
        $("recResults").innerHTML = table(rows, { score: true });
    } catch (error) {
        setMsg("recMsg", error.message, false);
    }
}

function initRevealEffects() {
    document.querySelectorAll(".topbar, .hero-card, .quick-nav, .panel").forEach((element) => {
        element.classList.add("reveal");
    });

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("visible");
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.18 });

    document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
}

document.addEventListener("DOMContentLoaded", () => {
    $("addBtn").addEventListener("click", addListing);
    $("searchBtn").addEventListener("click", search);
    $("compareBtn").addEventListener("click", compareSelected);
    document.addEventListener("click", (event) => {
        if (event.target.matches("[data-report]")) {
            reportListing(event);
        }
    });
    $("recBtn").addEventListener("click", recommendListings);
    initRevealEffects();
    search();
    recommendListings();
});
