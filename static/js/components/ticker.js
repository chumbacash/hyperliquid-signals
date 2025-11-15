/**
 * Price Ticker Component
 * Displays live cryptocurrency prices with 5-minute baseline comparison
 */

const tickerContent = document.getElementById("ticker-content");
const TICKER_SYMBOLS = ["BTC", "ETH", "SOL", "HYPE", "XRP", "ASTER", "PUMP", "ZEC", "ADA", "BNB", "MET", "WIF", "JUP"];
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

        return `
            <span class="ticker-item">
                <img class="ticker-logo" src="${getCoinLogoUrl(symbol)}" alt="${symbol}" onerror="this.style.display='none'">
                <span class="ticker-symbol">${symbol}</span>
                <span class="ticker-price">$${formatted}</span>
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

export async function initTicker() {
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
