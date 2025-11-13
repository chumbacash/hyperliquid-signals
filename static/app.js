const statusIndicator = document.getElementById("status-indicator");
const form = document.getElementById("query-form");
const resultsContainer = document.getElementById("results-container");
const lastUpdated = document.getElementById("last-updated");
const resetButton = document.getElementById("reset-button");
const cardTemplate = document.getElementById("card-template");

const DEFAULT_TIMEFRAMES = window.DEFAULT_TIMEFRAMES ?? ["1d", "4h", "1h", "15m"];

function setStatus(message, tone = "default") {
    statusIndicator.textContent = message;
    statusIndicator.dataset.tone = tone;
}

function serializeForm() {
    const symbolsInput = form.elements["symbols"].value
        .split(",")
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);

    const timeframeNodes = form.querySelectorAll('input[name="timeframes"]:checked');
    const timeframes = Array.from(timeframeNodes).map((node) => node.value);

    const apiUrl = form.elements["api-url"].value.trim();

    if (!symbolsInput.length) {
        throw new Error("Please specify at least one symbol.");
    }
    if (!timeframes.length) {
        throw new Error("Select at least one timeframe.");
    }

    return { symbols: symbolsInput, timeframes, apiUrl };
}

function buildQueryUrl({ symbols, timeframes, apiUrl }) {
    const params = new URLSearchParams();
    symbols.forEach((symbol) => params.append("symbols", symbol));
    timeframes.forEach((timeframe) => params.append("timeframes", timeframe));

    let base = apiUrl || window.location.origin;
    if (!base.endsWith("/")) {
        base += "/";
    }
    const url = new URL("signals", base);
    url.search = params.toString();
    return url.toString();
}

function renderIndicators(container, indicators) {
    container.textContent = "";
    if (!indicators) {
        container.textContent = "No indicator data available.";
        return;
    }

    Object.entries(indicators).forEach(([key, value]) => {
        if (key === "close") {
            return;
        }
        const row = document.createElement("div");
        row.innerHTML = `<strong>${key}</strong>: ${Number(value).toFixed(4)}`;
        container.appendChild(row);
    });
}

function renderPriceAction(container, priceAction) {
    container.textContent = "";
    if (!priceAction) {
        container.textContent = "No price action context.";
        return;
    }

    if (priceAction.summary) {
        const summary = document.createElement("div");
        summary.innerHTML = `<strong>Summary:</strong> ${priceAction.summary}`;
        container.appendChild(summary);
    }

    if (priceAction.pattern) {
        const pattern = document.createElement("div");
        pattern.innerHTML = `<strong>Pattern:</strong> ${priceAction.pattern.name} (${priceAction.pattern.bias})`;
        container.appendChild(pattern);
    }

    const levels = document.createElement("div");
    levels.innerHTML = `<strong>Support:</strong> ${formatMaybe(priceAction.support)} &nbsp; <strong>Resistance:</strong> ${formatMaybe(priceAction.resistance)}`;
    container.appendChild(levels);

    const trends = document.createElement("div");
    trends.innerHTML = `<strong>Trend:</strong> ${priceAction.timeframeTrend ?? "n/a"} &nbsp; <strong>Higher TF:</strong> ${priceAction.higherTimeframeTrend ?? "n/a"}`;
    container.appendChild(trends);

    const volume = document.createElement("div");
    volume.innerHTML = `<strong>Volume Ratio:</strong> ${Number(priceAction.volumeRatio || 0).toFixed(2)}x`;
    container.appendChild(volume);
}

function formatMaybe(value) {
    if (value === null || value === undefined || Number.isNaN(value)) {
        return "n/a";
    }
    return Number(value).toFixed(2);
}

function renderResults(payload) {
    resultsContainer.textContent = "";

    if (!payload || !payload.symbols || !Object.keys(payload.symbols).length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No signals returned for the current selection.";
        resultsContainer.appendChild(empty);
        return;
    }

    Object.entries(payload.symbols).forEach(([symbol, signals]) => {
        signals.forEach((signal) => {
            const node = cardTemplate.content.cloneNode(true);
            const card = node.querySelector(".signal-card");
            const title = node.querySelector(".signal-title");
            const badge = node.querySelector(".direction-badge");
            const formatted = node.querySelector(".formatted");
            const indicatorsContainer = node.querySelector(".indicators");
            const priceActionContainer = node.querySelector(".price-action");

            title.textContent = `${symbol} · ${signal.timeframe.toUpperCase()}`;
            formatted.textContent = signal.formatted;
            badge.textContent = signal.direction;
            badge.classList.add(signal.direction.toLowerCase() === "long" ? "long" : "short");

            renderIndicators(indicatorsContainer, signal.indicators);
            renderPriceAction(priceActionContainer, signal.priceAction);

            resultsContainer.appendChild(node);
        });
    });

    const now = new Date();
    lastUpdated.textContent = `Last updated: ${now.toLocaleString()}`;
}

async function fetchSignals() {
    let params;
    try {
        params = serializeForm();
    } catch (error) {
        renderError(error.message);
        return;
    }

    const queryUrl = buildQueryUrl(params);
    setStatus("Fetching signals…", "loading");
    try {
        const response = await fetch(queryUrl);
        if (!response.ok) {
            throw new Error(`Request failed (${response.status})`);
        }
        const payload = await response.json();
        renderResults(payload);
        setStatus("Signals updated", "success");
    } catch (error) {
        console.error(error);
        renderError(error.message ?? "Failed to load signals.");
        setStatus("Error fetching signals", "error");
    }
}

function renderError(message) {
    resultsContainer.textContent = "";
    const errorNode = document.createElement("div");
    errorNode.className = "error-message";
    errorNode.textContent = message;
    resultsContainer.appendChild(errorNode);
    lastUpdated.textContent = "Last updated: —";
}

function resetForm() {
    const defaults = Array.isArray(window.DEFAULT_SYMBOLS) && window.DEFAULT_SYMBOLS.length
        ? window.DEFAULT_SYMBOLS
        : ["BTC"];
    form.elements["symbols"].value = defaults.join(",");
    form.elements["api-url"].value = "";
    form
        .querySelectorAll('input[name="timeframes"]')
        .forEach((checkbox) => (checkbox.checked = DEFAULT_TIMEFRAMES.includes(checkbox.value)));
}

form.addEventListener("submit", (event) => {
    event.preventDefault();
    fetchSignals();
});

resetButton.addEventListener("click", () => {
    resetForm();
    resultsContainer.textContent = "";
    lastUpdated.textContent = "Awaiting data…";
    setStatus("Ready");
});

window.addEventListener("DOMContentLoaded", () => {
    fetchSignals();
});

