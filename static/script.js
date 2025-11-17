// Global state
let currentCollection = [];
let currentCardId = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    loadCollection();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    // Add card button
    document.getElementById('addCardBtn').addEventListener('click', openAddCardModal);
    
    // Import deck button
    document.getElementById('importDeckBtn').addEventListener('click', openImportDeckModal);
    
    // Refresh prices button
    document.getElementById('refreshPricesBtn').addEventListener('click', refreshPrices);
    
    // Stats button
    document.getElementById('statsBtn').addEventListener('click', openStatsModal);
    
    // Decks button
    document.getElementById('decksBtn').addEventListener('click', openDecksModal);
    
    // Search and filter controls
    document.getElementById('searchInput').addEventListener('input', debounce(loadCollection, 500));
    document.getElementById('sortSelect').addEventListener('change', loadCollection);
    document.getElementById('orderSelect').addEventListener('change', loadCollection);
    document.getElementById('colorFilter').addEventListener('change', loadCollection);
    document.getElementById('rarityFilter').addEventListener('change', loadCollection);
    document.getElementById('typeFilter').addEventListener('input', debounce(loadCollection, 500));
    
    // Card search in modal
    document.getElementById('cardSearchInput').addEventListener('input', debounce(searchCards, 500));
    
    // Edit card form
    document.getElementById('editCardForm').addEventListener('submit', handleEditCardSubmit);
    document.getElementById('deleteCardBtn').addEventListener('click', handleDeleteCard);
    
    // Import deck form
    document.getElementById('importDeckForm').addEventListener('submit', handleImportDeck);
    
    // Modal close buttons
    document.querySelectorAll('.close').forEach(closeBtn => {
        closeBtn.addEventListener('click', closeModals);
    });
    
    // Close modals when clicking outside
    window.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
            closeModals();
        }
    });
}

// Load collection from API
async function loadCollection() {
    const params = new URLSearchParams({
        search: document.getElementById('searchInput').value,
        sort: document.getElementById('sortSelect').value,
        order: document.getElementById('orderSelect').value,
        color: document.getElementById('colorFilter').value,
        rarity: document.getElementById('rarityFilter').value,
        type: document.getElementById('typeFilter').value,
    });
    
    showLoading(true);
    
    try {
        const response = await fetch(`/api/collection?${params}`);
        const data = await response.json();
        currentCollection = data.cards;
        displayCards(data.cards);
        updateStats(data.total_count, data.cards.length, data.total_value);
    } catch (error) {
        console.error('Error loading collection:', error);
        showError('Failed to load collection');
    } finally {
        showLoading(false);
    }
}

// Display cards in grid
function displayCards(cards) {
    const grid = document.getElementById('cardGrid');
    
    if (cards.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <h2>No cards in your collection</h2>
                <p>Click "Add Card" to start building your collection!</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = cards.map(card => createCardElement(card)).join('');
    
    // Add click listeners to cards
    grid.querySelectorAll('.card-item').forEach(cardEl => {
        cardEl.addEventListener('click', () => {
            const cardId = parseInt(cardEl.dataset.cardId);
            openEditCardModal(cardId);
        });
    });
}

// Create HTML for a single card
function createCardElement(card) {
    const price = card.foil && card.price_usd_foil ? card.price_usd_foil : card.price_usd;
    const priceDisplay = price ? `$${parseFloat(price).toFixed(2)}` : 'N/A';
    const imageUrl = card.image_normal || card.image_small || '';
    
    const deckTags = card.decks && card.decks.length > 0 
        ? `<div class="card-decks">${card.decks.map(deck => `<span class="deck-tag">${deck.name}</span>`).join('')}</div>`
        : '';
    
    return `
        <div class="card-item" data-card-id="${card.id}">
            ${card.foil ? '<div class="foil-indicator">✨ FOIL</div>' : ''}
            <div class="card-rarity rarity-${card.rarity}">${card.rarity}</div>
            <img src="${imageUrl}" alt="${card.name}" class="card-image" loading="lazy">
            <div class="card-info">
                <div class="card-name">${card.name}</div>
                <div class="card-set">${card.set_name} (${card.set_code.toUpperCase()})</div>
                ${deckTags}
                <div class="card-details">
                    <span class="card-price">${priceDisplay}</span>
                    <span class="card-quantity">×${card.quantity}</span>
                </div>
            </div>
        </div>
    `;
}

// Update stats banner
function updateStats(totalCards, uniqueCards, totalValue) {
    document.getElementById('totalCards').textContent = totalCards;
    document.getElementById('uniqueCards').textContent = uniqueCards;
    document.getElementById('totalValue').textContent = `$${totalValue}`;
}

// Open add card modal
function openAddCardModal() {
    document.getElementById('addCardModal').style.display = 'block';
    document.getElementById('cardSearchInput').value = '';
    document.getElementById('searchResults').innerHTML = '';
}

// Search for cards on Scryfall
async function searchCards() {
    const query = document.getElementById('cardSearchInput').value.trim();
    const resultsContainer = document.getElementById('searchResults');
    
    if (query.length < 2) {
        resultsContainer.innerHTML = '';
        return;
    }
    
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.cards.length === 0) {
            resultsContainer.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">No cards found</div>';
            return;
        }
        
        // Sort results by relevance (how well they match the query)
        const sortedCards = sortByRelevance(data.cards, query);
        
        resultsContainer.innerHTML = sortedCards.map(card => {
            const price = card.price_usd ? `$${parseFloat(card.price_usd).toFixed(2)}` : 'N/A';
            const imageUrl = card.image_small || '';
            
            return `
                <div class="search-result-item" data-card-name="${card.name}">
                    <img src="${imageUrl}" alt="${card.name}">
                    <div class="search-result-info">
                        <div class="search-result-name">${card.name}</div>
                        <div class="search-result-set">Click to see all printings</div>
                    </div>
                    <div class="search-result-price">${price}</div>
                </div>
            `;
        }).join('');
        
        // Add click listeners to search results
        resultsContainer.querySelectorAll('.search-result-item').forEach(item => {
            item.addEventListener('click', () => {
                const cardName = item.dataset.cardName;
                showPrintings(cardName);
            });
        });
    } catch (error) {
        console.error('Error searching cards:', error);
        showError('Failed to search cards');
    }
}

// Sort cards by relevance to search query
function sortByRelevance(cards, query) {
    const queryLower = query.toLowerCase();
    
    return cards.sort((a, b) => {
        const aName = a.name.toLowerCase();
        const bName = b.name.toLowerCase();
        
        // Exact match comes first
        if (aName === queryLower) return -1;
        if (bName === queryLower) return 1;
        
        // Starts with query comes next
        const aStarts = aName.startsWith(queryLower);
        const bStarts = bName.startsWith(queryLower);
        if (aStarts && !bStarts) return -1;
        if (bStarts && !aStarts) return 1;
        
        // Contains query as whole word (with word boundaries)
        const aWordMatch = new RegExp(`\\b${queryLower}\\b`).test(aName);
        const bWordMatch = new RegExp(`\\b${queryLower}\\b`).test(bName);
        if (aWordMatch && !bWordMatch) return -1;
        if (bWordMatch && !aWordMatch) return 1;
        
        // Earlier occurrence of query
        const aIndex = aName.indexOf(queryLower);
        const bIndex = bName.indexOf(queryLower);
        if (aIndex !== bIndex) return aIndex - bIndex;
        
        // Shorter names are more likely to be what you want
        if (aName.length !== bName.length) return aName.length - bName.length;
        
        // Fall back to alphabetical
        return aName.localeCompare(bName);
    });
}


// Show all printings of a card
async function showPrintings(cardName) {
    try {
        const response = await fetch(`/api/printings?name=${encodeURIComponent(cardName)}`);
        const data = await response.json();
        
        if (data.printings.length === 0) {
            showError('No printings found for this card');
            return;
        }
        
        document.getElementById('printingsCardName').textContent = `Select Printing: ${cardName}`;
        
        const printingsList = document.getElementById('printingsList');
        printingsList.innerHTML = data.printings.map(card => {
            const price = card.price_usd ? `$${parseFloat(card.price_usd).toFixed(2)}` : 'N/A';
            const foilPrice = card.price_usd_foil ? `$${parseFloat(card.price_usd_foil).toFixed(2)} (F)` : '';
            const imageUrl = card.image_normal || card.image_small || '';
            const rarityClass = `rarity-${card.rarity}`;
            
            return `
                <div class="printing-item" data-scryfall-id="${card.scryfall_id}">
                    <img src="${imageUrl}" alt="${card.name}">
                    <div class="printing-info">
                        <div class="printing-name">${card.name}</div>
                        <div class="printing-set">${card.set_name} (${card.set_code.toUpperCase()})</div>
                        <div class="printing-details">
                            <span class="printing-rarity ${rarityClass}">${card.rarity}</span>
                            <span>#${card.collector_number}</span>
                        </div>
                    </div>
                    <div class="printing-price">
                        <div>${price}</div>
                        ${foilPrice ? `<div style="font-size: 12px; margin-top: 2px;">${foilPrice}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');
        
        // Add click listeners to printings
        printingsList.querySelectorAll('.printing-item').forEach(item => {
            item.addEventListener('click', () => {
                const scryfallId = item.dataset.scryfallId;
                addCardToCollection(scryfallId);
            });
        });
        
        // Close add card modal and open printings modal
        document.getElementById('addCardModal').style.display = 'none';
        document.getElementById('printingsModal').style.display = 'block';
        
    } catch (error) {
        console.error('Error loading printings:', error);
        showError('Failed to load printings');
    }
}

// Add card to collection
async function addCardToCollection(scryfallId) {
    try {
        const response = await fetch('/api/card', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                scryfall_id: scryfallId,
                quantity: 1,
                condition: 'NM',
                foil: false
            }),
        });
        
        if (response.ok) {
            closeModals();
            loadCollection();
            showSuccess('Card added to collection!');
        } else {
            throw new Error('Failed to add card');
        }
    } catch (error) {
        console.error('Error adding card:', error);
        showError('Failed to add card to collection');
    }
}

// Open edit card modal
function openEditCardModal(cardId) {
    const card = currentCollection.find(c => c.id === cardId);
    if (!card) return;
    
    currentCardId = cardId;
    
    document.getElementById('editCardId').value = card.id;
    document.getElementById('editQuantity').value = card.quantity;
    document.getElementById('editCondition').value = card.condition;
    document.getElementById('editFoil').checked = card.foil;
    document.getElementById('editNotes').value = card.notes || '';
    
    document.getElementById('editCardModal').style.display = 'block';
}

// Handle edit card form submission
async function handleEditCardSubmit(e) {
    e.preventDefault();
    
    const cardId = currentCardId;
    const data = {
        quantity: parseInt(document.getElementById('editQuantity').value),
        condition: document.getElementById('editCondition').value,
        foil: document.getElementById('editFoil').checked,
        notes: document.getElementById('editNotes').value,
    };
    
    try {
        const response = await fetch(`/api/card/${cardId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        
        if (response.ok) {
            closeModals();
            loadCollection();
            showSuccess('Card updated successfully!');
        } else {
            throw new Error('Failed to update card');
        }
    } catch (error) {
        console.error('Error updating card:', error);
        showError('Failed to update card');
    }
}

// Handle delete card
async function handleDeleteCard() {
    if (!confirm('Are you sure you want to remove this card from your collection?')) {
        return;
    }
    
    const cardId = currentCardId;
    
    try {
        const response = await fetch(`/api/card/${cardId}`, {
            method: 'DELETE',
        });
        
        if (response.ok) {
            closeModals();
            loadCollection();
            showSuccess('Card removed from collection!');
        } else {
            throw new Error('Failed to delete card');
        }
    } catch (error) {
        console.error('Error deleting card:', error);
        showError('Failed to delete card');
    }
}

// Refresh all prices
async function refreshPrices() {
    if (!confirm('This will update prices for all cards in your collection. Continue?')) {
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch('/api/prices/refresh', {
            method: 'POST',
        });
        
        if (response.ok) {
            loadCollection();
            showSuccess('Prices updated successfully!');
        } else {
            throw new Error('Failed to refresh prices');
        }
    } catch (error) {
        console.error('Error refreshing prices:', error);
        showError('Failed to refresh prices');
    } finally {
        showLoading(false);
    }
}

// Open stats modal
async function openStatsModal() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();
        
        const colorNames = {
            'W': 'White',
            'U': 'Blue',
            'B': 'Black',
            'R': 'Red',
            'G': 'Green',
            'C': 'Colorless'
        };
        
        const colorComboNames = {
            'W': 'White',
            'U': 'Blue',
            'B': 'Black',
            'R': 'Red',
            'G': 'Green',
            // Two-color (alphabetically sorted)
            'U,W': 'Azorius',
            'B,U': 'Dimir',
            'B,R': 'Rakdos',
            'G,R': 'Gruul',
            'G,W': 'Selesnya',
            'B,W': 'Orzhov',
            'R,U': 'Izzet',
            'B,G': 'Golgari',
            'R,W': 'Boros',
            'G,U': 'Simic',
            // Three-color (alphabetically sorted)
            'B,U,W': 'Esper',
            'B,R,U': 'Grixis',
            'B,G,R': 'Jund',
            'G,R,W': 'Naya',
            'G,U,W': 'Bant',
            'B,R,W': 'Mardu',
            'G,R,U': 'Temur',
            'B,G,W': 'Abzan',
            'R,U,W': 'Jeskai',
            'B,G,U': 'Sultai',
            // Four-color
            'B,G,R,U': 'No White',
            'B,G,R,W': 'No Blue',
            'B,R,U,W': 'No Green',
            'G,R,U,W': 'No Black',
            'B,G,U,W': 'No Red',
            // Five-color
            'B,G,R,U,W': 'Five-Color',
            'Colorless': 'Colorless'
        };
        
        const statsHTML = `
            <div class="stats-section">
                <h3>Collection Overview</h3>
                <div class="stats-grid">
                    <div class="stats-card">
                        <div class="stats-card-label">Total Cards</div>
                        <div class="stats-card-value">${stats.total_cards}</div>
                    </div>
                    <div class="stats-card">
                        <div class="stats-card-label">Unique Cards</div>
                        <div class="stats-card-value">${stats.unique_cards}</div>
                    </div>
                    <div class="stats-card">
                        <div class="stats-card-label">Total Value</div>
                        <div class="stats-card-value">$${stats.total_value}</div>
                    </div>
                    <div class="stats-card">
                        <div class="stats-card-label">Average Price</div>
                        <div class="stats-card-value">$${stats.avg_price}</div>
                    </div>
                </div>
            </div>
            
            <div class="stats-section">
                <h3>By Rarity</h3>
                <div class="stats-grid">
                    ${Object.entries(stats.rarity_counts).map(([rarity, count]) => `
                        <div class="stats-card">
                            <div class="stats-card-label">${rarity.charAt(0).toUpperCase() + rarity.slice(1)}</div>
                            <div class="stats-card-value">${count}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="stats-section">
                <h3>By Color</h3>
                <div class="stats-grid">
                    ${Object.entries(stats.color_counts).map(([color, count]) => `
                        <div class="stats-card">
                            <div class="stats-card-label">${colorNames[color]}</div>
                            <div class="stats-card-value">${count}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="stats-section">
                <h3>By Mana Value</h3>
                <div class="stats-grid">
                    ${Object.entries(stats.mana_value_counts).map(([mv, count]) => `
                        <div class="stats-card">
                            <div class="stats-card-label">MV ${mv}</div>
                            <div class="stats-card-value">${count}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="stats-section">
                <h3>By Card Type</h3>
                <div class="stats-grid">
                    ${Object.entries(stats.type_counts).sort((a, b) => b[1] - a[1]).map(([type, count]) => `
                        <div class="stats-card">
                            <div class="stats-card-label">${type}</div>
                            <div class="stats-card-value">${count}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div class="stats-section">
                <h3>Top Color Combinations</h3>
                <div class="stats-grid">
                    ${stats.color_combo_counts.map(combo => `
                        <div class="stats-card">
                            <div class="stats-card-label">${colorComboNames[combo.name] || combo.name}</div>
                            <div class="stats-card-value">${combo.count}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        
        document.getElementById('statsContent').innerHTML = statsHTML;
        document.getElementById('statsModal').style.display = 'block';
    } catch (error) {
        console.error('Error loading stats:', error);
        showError('Failed to load statistics');
    }
}

// Open import deck modal
function openImportDeckModal() {
    document.getElementById('importDeckModal').style.display = 'block';
    document.getElementById('archidektUrl').value = '';
    document.getElementById('importProgress').style.display = 'none';
}

// Handle import deck form submission
async function handleImportDeck(e) {
    e.preventDefault();
    
    const url = document.getElementById('archidektUrl').value.trim();
    if (!url) return;
    
    document.getElementById('importProgress').style.display = 'block';
    
    try {
        const response = await fetch('/api/deck/import', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url }),
        });
        
        const data = await response.json();
        
        if (response.ok) {
            closeModals();
            loadCollection();
            showSuccess(data.message);
        } else {
            throw new Error(data.error || 'Failed to import deck');
        }
    } catch (error) {
        console.error('Error importing deck:', error);
        showError(error.message || 'Failed to import deck');
    } finally {
        document.getElementById('importProgress').style.display = 'none';
    }
}

// Open decks modal
async function openDecksModal() {
    try {
        const response = await fetch('/api/decks');
        const data = await response.json();
        
        const decksList = document.getElementById('decksList');
        
        if (data.decks.length === 0) {
            decksList.innerHTML = `
                <div class="empty-decks">
                    <h3>No decks yet</h3>
                    <p>Click "Import Deck" to import a deck from Archidekt</p>
                </div>
            `;
        } else {
            decksList.innerHTML = data.decks.map(deck => `
                <div class="deck-item">
                    <div class="deck-header">
                        <div>
                            <div class="deck-name">${deck.name}</div>
                            ${deck.commander ? `<div class="deck-commander">Commander: ${deck.commander}</div>` : ''}
                        </div>
                        <div class="deck-actions">
                            ${deck.archidekt_url ? `<a href="${deck.archidekt_url}" target="_blank" class="btn btn-secondary btn-small">View on Archidekt</a>` : ''}
                            <button class="btn btn-danger btn-small" onclick="deleteDeck(${deck.id})">Delete</button>
                        </div>
                    </div>
                    <div class="deck-info">
                        ${deck.format ? `<span>Format: ${deck.format}</span>` : ''}
                        <span>Cards: ${deck.card_count}</span>
                    </div>
                </div>
            `).join('');
        }
        
        document.getElementById('decksModal').style.display = 'block';
    } catch (error) {
        console.error('Error loading decks:', error);
        showError('Failed to load decks');
    }
}

// Delete a deck
async function deleteDeck(deckId) {
    if (!confirm('Are you sure you want to delete this deck? Cards will remain in your collection.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/deck/${deckId}`, {
            method: 'DELETE',
        });
        
        if (response.ok) {
            openDecksModal(); // Refresh the list
            loadCollection(); // Refresh cards to remove deck tags
            showSuccess('Deck deleted successfully');
        } else {
            throw new Error('Failed to delete deck');
        }
    } catch (error) {
        console.error('Error deleting deck:', error);
        showError('Failed to delete deck');
    }
}

// Close all modals
function closeModals() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.style.display = 'none';
    });
}

// Utility functions
function showLoading(show) {
    document.getElementById('loadingSpinner').style.display = show ? 'block' : 'none';
}

function showSuccess(message) {
    alert(message); // You can replace this with a nicer notification system
}

function showError(message) {
    alert(`Error: ${message}`); // You can replace this with a nicer notification system
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
