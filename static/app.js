const form = document.getElementById("query-form");
const resultsContainer = document.getElementById("results-container");
const lastUpdated = document.getElementById("last-updated");
const resetButton = document.getElementById("reset-button");
const cardTemplate = document.getElementById("card-template");

const DEFAULT_TIMEFRAMES = window.DEFAULT_TIMEFRAMES ?? ["1d", "4h", "1h", "15m"];

const HYPERLIQUID_COIN_IMAGE_BASE = "https://app.hyperliquid.xyz/coins";

function getCoinImageUrl(symbol) {
    return `${HYPERLIQUID_COIN_IMAGE_BASE}/${symbol.toUpperCase()}.svg`;
}

function setStatus(message, tone = "default") {
    // Status indicator removed - could add loading state to button instead
    console.log(`Status: ${message} (${tone})`);
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
            const coinIcon = node.querySelector(".coin-icon");
            const title = node.querySelector(".signal-title");
            const badge = node.querySelector(".direction-badge");
            const formatted = node.querySelector(".formatted");
            const indicatorsContainer = node.querySelector(".indicators");
            const priceActionContainer = node.querySelector(".price-action");

            coinIcon.src = getCoinImageUrl(symbol);
            coinIcon.alt = `${symbol} icon`;
            coinIcon.onerror = () => {
                coinIcon.style.display = "none";
            };

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
    const submitButton = form.querySelector('button[type="submit"]');
    const originalText = submitButton.textContent;

    submitButton.disabled = true;
    submitButton.textContent = "Loading...";

    try {
        const response = await fetch(queryUrl);
        if (!response.ok) {
            throw new Error(`Request failed (${response.status})`);
        }
        const payload = await response.json();
        renderResults(payload);
    } catch (error) {
        console.error(error);
        renderError(error.message ?? "Failed to load signals.");
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = originalText;
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
});

// Price Ticker
const tickerContent = document.getElementById("ticker-content");
const TICKER_SYMBOLS = ["BTC", "ETH", "SOL", "ARB", "AVAX", "MATIC", "DOGE", "XRP", "ADA", "DOT"];
let baselinePrices = {}; // 5-minute baseline for comparison
let currentPrices = {};
let isFirstLoad = true;

function getCoinLogoUrl(symbol) {
    return `https://app.hyperliquid.xyz/coins/${symbol.toUpperCase()}.svg`;
}

async function fetchPrices() {
    try {
        const response = await fetch("https://api.hyperliquid.xyz/info", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: "allMids" })
        });

        if (!response.ok) return null;

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Failed to fetch prices:", error);
        return null;
    }
}

function formatPrice(priceNum) {
    if (priceNum >= 1000) {
        return priceNum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } else if (priceNum >= 1) {
        return priceNum.toFixed(4);
    } else {
        return priceNum.toFixed(6);
    }
}

function getPriceChange(symbol, currentPrice) {
    if (!baselinePrices[symbol]) {
        return { change: 0, direction: 'neutral' };
    }

    const baseline = parseFloat(baselinePrices[symbol]);
    const current = parseFloat(currentPrice);
    const changePercent = ((current - baseline) / baseline) * 100;

    return {
        change: changePercent,
        direction: changePercent > 0.01 ? 'positive' : changePercent < -0.01 ? 'negative' : 'neutral'
    };
}

function updateTickerContent(prices) {
    if (!prices) return;

    const items = TICKER_SYMBOLS.map(symbol => {
        const price = prices[symbol];
        if (!price) return "";

        const priceNum = parseFloat(price);
        const formatted = formatPrice(priceNum);
        const { change, direction } = getPriceChange(symbol, price);

        // Only show change if we have baseline price data
        const changeHtml = baselinePrices[symbol] && Math.abs(change) > 0.01
            ? `<span class="ticker-change ${direction}">${change > 0 ? '+' : ''}${change.toFixed(2)}%</span>`
            : '';

        return `
            <span class="ticker-item">
                <img class="ticker-logo" src="${getCoinLogoUrl(symbol)}" alt="${symbol}" onerror="this.style.display='none'">
                <span class="ticker-symbol">${symbol}</span>
                <span class="ticker-price">$${formatted}</span>
                ${changeHtml}
            </span>
        `;
    }).filter(Boolean).join("");

    // Update content without restarting animation
    const wasScrolling = tickerContent.classList.contains('scrolling');
    if (wasScrolling) {
        tickerContent.classList.remove('scrolling');
    }

    // Duplicate content for seamless loop
    tickerContent.innerHTML = items + items;

    // Restart animation on next frame
    if (wasScrolling || isFirstLoad) {
        requestAnimationFrame(() => {
            tickerContent.classList.add('scrolling');
            isFirstLoad = false;
        });
    }
}

async function updateTicker() {
    const prices = await fetchPrices();
    if (!prices) return;

    // Store current prices
    TICKER_SYMBOLS.forEach(symbol => {
        if (prices[symbol]) {
            currentPrices[symbol] = prices[symbol];
        }
    });

    updateTickerContent(prices);
}

async function initTicker() {
    // Initial fetch
    await updateTicker();

    // Set baseline prices (for 5-minute comparison)
    baselinePrices = { ...currentPrices };

    // Update prices every 3 seconds
    setInterval(updateTicker, 3000);

    // Reset baseline every 5 minutes
    setInterval(() => {
        baselinePrices = { ...currentPrices };
        console.log('Baseline prices updated for 5-minute comparison');
    }, 5 * 60 * 1000);
}

// Header scroll effect
const header = document.querySelector('.header');
let lastScroll = 0;

window.addEventListener('scroll', () => {
    const currentScroll = window.pageYOffset;

    if (currentScroll > 50) {
        header.classList.add('scrolled');
    } else {
        header.classList.remove('scrolled');
    }

    lastScroll = currentScroll;
});

window.addEventListener("DOMContentLoaded", () => {
    initTicker();
    fetchSignals();
});

