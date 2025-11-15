/**
 * Main Application Entry Point
 * Initializes all components
 */

import { initHeader } from './components/header.js';
import { initTicker } from './components/ticker.js';
import { initSignals } from './components/signals.js';

window.addEventListener("DOMContentLoaded", () => {
    // Initialize all components
    initHeader();
    initTicker();
    initSignals();
    
    console.log('✓ Chumba Finance initialized');
});
