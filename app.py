"""
Flask application for MTG Collection Manager
"""

from flask import Flask, render_template, request, jsonify
from models import db, Card, Deck, card_deck_association
from scryfall_api import ScryfallAPI
from datetime import datetime
import os
import requests
import re

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mtg_collection.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

db.init_app(app)
scryfall = ScryfallAPI()


@app.route('/')
def index():
    """Main page - display collection"""
    return render_template('index.html')


@app.route('/api/collection')
def get_collection():
    """Get all cards in the collection with sorting and filtering"""
    # Get query parameters
    sort_by = request.args.get('sort', 'name')
    order = request.args.get('order', 'asc')
    secondary_sort = request.args.get('secondary_sort', 'name')
    secondary_order = request.args.get('secondary_order', 'asc')
    search = request.args.get('search', '')
    color_filter = request.args.get('color', '')
    rarity_filter = request.args.get('rarity', '')
    type_filter = request.args.get('type', '')
    
    # Build query
    query = Card.query
    
    # Apply filters
    if search:
        from sqlalchemy import or_
        search_term = f'%{search}%'
        query = query.filter(or_(
            Card.name.ilike(search_term),
            Card.type_line.ilike(search_term),
            Card.oracle_text.ilike(search_term)
        ))
    
    if color_filter:
        if color_filter == 'C':
            # Colorless cards have empty or null colors
            query = query.filter((Card.colors == '') | (Card.colors == None))
        else:
            query = query.filter(Card.colors.like(f'%{color_filter}%'))
    
    if rarity_filter:
        query = query.filter(Card.rarity == rarity_filter)
    
    if type_filter:
        query = query.filter(Card.type_line.ilike(f'%{type_filter}%'))
    
    # Apply sorting (comprehensive for all types)
    from sqlalchemy import cast, Float, case
    order_by_clauses = []

    # Handle primary sort
    if sort_by == 'price_usd':
        price_to_use = case(
            (Card.foil & (Card.price_usd_foil != None), Card.price_usd_foil),
            else_=Card.price_usd
        )
        primary_column = cast(price_to_use, Float)
    elif sort_by == 'rarity':
        primary_column = case(
            (Card.rarity == 'mythic', 4),
            (Card.rarity == 'rare', 3),
            (Card.rarity == 'uncommon', 2),
            (Card.rarity == 'common', 1),
            else_=0
        )
    else:
        primary_column = getattr(Card, sort_by, Card.name)

    # Handle secondary sort
    if secondary_sort == 'price_usd':
        secondary_price_to_use = case(
            (Card.foil & (Card.price_usd_foil != None), Card.price_usd_foil),
            else_=Card.price_usd
        )
        secondary_column = cast(secondary_price_to_use, Float)
    elif secondary_sort == 'rarity':
        secondary_column = case(
            (Card.rarity == 'mythic', 4),
            (Card.rarity == 'rare', 3),
            (Card.rarity == 'uncommon', 2),
            (Card.rarity == 'common', 1),
            else_=0
        )
    else:
        secondary_column = getattr(Card, secondary_sort, Card.name)

    # Build order by clauses
    if order == 'desc':
        order_by_clauses.append(primary_column.desc())
    else:
        order_by_clauses.append(primary_column.asc())

    if secondary_order == 'desc':
        order_by_clauses.append(secondary_column.desc())
    else:
        order_by_clauses.append(secondary_column.asc())

    query = query.order_by(*order_by_clauses)
    
    cards = query.all()
    
    # Calculate total collection value
    total_value = sum(card.total_value for card in cards)
    
    return jsonify({
        'cards': [card.to_dict() for card in cards],
        'total_count': len(cards),
        'total_value': f'{total_value:.2f}'
    })


@app.route('/api/card/<int:card_id>')
def get_card(card_id):
    """Get a specific card by ID"""
    card = Card.query.get_or_404(card_id)
    return jsonify(card.to_dict())


@app.route('/api/search')
def search_scryfall():
    """Search Scryfall for cards with fuzzy name matching"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'cards': []})
    
    # Use fuzzy name search for better matching
    # This searches card names more intelligently than a general search
    fuzzy_query = f'name:/{query}/'
    results = scryfall.search_cards(fuzzy_query)
    
    # Sort results by relevance on the server side as well
    def relevance_score(card):
        name_lower = card.get('name', '').lower()
        query_lower = query.lower()
        
        # Exact match
        if name_lower == query_lower:
            return 0
        # Starts with
        if name_lower.startswith(query_lower):
            return 1
        # Contains as word
        if f' {query_lower} ' in f' {name_lower} ':
            return 2
        # Contains anywhere
        if query_lower in name_lower:
            return 3 + name_lower.index(query_lower)
        # Fallback
        return 1000
    
    results.sort(key=relevance_score)
    
    return jsonify({
        'cards': [ScryfallAPI.extract_card_info(card) for card in results[:20]]
    })


@app.route('/api/autocomplete')
def autocomplete():
    """Get autocomplete suggestions from Scryfall"""
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify({'suggestions': []})
    
    suggestions = scryfall.autocomplete(query)
    return jsonify({'suggestions': suggestions})


@app.route('/api/printings')
def get_printings():
    """Get all printings of a specific card"""
    card_name = request.args.get('name', '')
    if not card_name:
        return jsonify({'printings': []})
    
    printings = scryfall.get_all_printings(card_name)
    return jsonify({
        'printings': [ScryfallAPI.extract_card_info(card) for card in printings]
    })


@app.route('/api/card', methods=['POST'])
def add_card():
    """Add a card to the collection"""
    data = request.json
    scryfall_id = data.get('scryfall_id')
    
    if not scryfall_id:
        return jsonify({'error': 'scryfall_id is required'}), 400
    
    # Check if card already exists in collection
    existing_card = Card.query.filter_by(
        scryfall_id=scryfall_id,
        foil=data.get('foil', False)
    ).first()
    
    if existing_card:
        # Update quantity instead of creating duplicate
        existing_card.quantity += data.get('quantity', 1)
        existing_card.updated_date = datetime.utcnow()
        db.session.commit()
        return jsonify(existing_card.to_dict())
    
    # Fetch fresh data from Scryfall
    card_data = scryfall.get_card_by_id(scryfall_id)
    if not card_data:
        return jsonify({'error': 'Card not found on Scryfall'}), 404
    
    # Extract card info
    card_info = ScryfallAPI.extract_card_info(card_data)
    
    # Create new card entry
    card = Card(
        scryfall_id=card_info['scryfall_id'],
        name=card_info['name'],
        set_code=card_info['set_code'],
        set_name=card_info['set_name'],
        collector_number=card_info['collector_number'],
        rarity=card_info['rarity'],
        mana_cost=card_info['mana_cost'],
        cmc=card_info['cmc'],
        type_line=card_info['type_line'],
        oracle_text=card_info['oracle_text'],
        colors=card_info['colors'],
        color_identity=card_info['color_identity'],
        image_small=card_info['image_small'],
        image_normal=card_info['image_normal'],
        image_large=card_info['image_large'],
        image_art_crop=card_info['image_art_crop'],
        price_usd=card_info['price_usd'],
        price_usd_foil=card_info['price_usd_foil'],
        scryfall_uri=card_info['scryfall_uri'],
        quantity=data.get('quantity', 1),
        foil=data.get('foil', False),
        condition=data.get('condition', 'NM'),
        notes=data.get('notes', '')
    )
    
    db.session.add(card)
    db.session.commit()
    
    return jsonify(card.to_dict()), 201


@app.route('/api/card/<int:card_id>', methods=['PUT'])
def update_card(card_id):
    """Update a card in the collection"""
    card = Card.query.get_or_404(card_id)
    data = request.json
    
    # Update allowed fields
    if 'quantity' in data:
        card.quantity = data['quantity']
    if 'condition' in data:
        card.condition = data['condition']
    if 'notes' in data:
        card.notes = data['notes']
    if 'foil' in data:
        card.foil = data['foil']
    
    card.updated_date = datetime.utcnow()
    db.session.commit()
    
    return jsonify(card.to_dict())


@app.route('/api/card/<int:card_id>', methods=['DELETE'])
def delete_card(card_id):
    """Remove a card from the collection"""
    card = Card.query.get_or_404(card_id)
    db.session.delete(card)
    db.session.commit()
    
    return jsonify({'message': 'Card deleted successfully'})


@app.route('/api/prices/refresh', methods=['POST'])
def refresh_prices():
    """Refresh prices for all cards in collection"""
    cards = Card.query.all()
    updated_count = 0
    
    for card in cards:
        try:
            card_data = scryfall.get_card_by_id(card.scryfall_id)
            if card_data:
                prices = card_data.get('prices', {})
                card.price_usd = prices.get('usd') or prices.get('usd_foil')
                card.price_usd_foil = prices.get('usd_foil')
                card.price_updated = datetime.utcnow()
                updated_count += 1
        except Exception as e:
            print(f"Error updating price for {card.name}: {e}")
            continue
    
    db.session.commit()
    
    return jsonify({
        'message': f'Updated prices for {updated_count} cards',
        'updated_count': updated_count
    })


@app.route('/api/stats')
def get_stats():
    """Get collection statistics"""
    cards = Card.query.all()
    
    total_cards = sum(card.quantity for card in cards)
    total_value = sum(card.total_value for card in cards)
    unique_cards = len(cards)
    
    # Calculate average price
    cards_with_price = [card for card in cards if card.total_value > 0]
    avg_price = total_value / sum(card.quantity for card in cards_with_price) if cards_with_price else 0
    
    # Count by rarity
    rarity_counts = {}
    for card in cards:
        rarity = card.rarity or 'unknown'
        rarity_counts[rarity] = rarity_counts.get(rarity, 0) + card.quantity
    
    # Count by color
    color_counts = {'W': 0, 'U': 0, 'B': 0, 'R': 0, 'G': 0, 'C': 0}
    for card in cards:
        if card.colors:
            for color in card.colors.split(','):
                if color in color_counts:
                    color_counts[color] += card.quantity
        else:
            color_counts['C'] += card.quantity
    
    # Count by mana value (CMC)
    mana_value_counts = {}
    for card in cards:
        cmc = int(card.cmc) if card.cmc is not None else 0
        mana_value_counts[cmc] = mana_value_counts.get(cmc, 0) + card.quantity
    
    # Count by color combinations
    color_combo_counts = {}
    for card in cards:
        if card.colors:
            colors = ','.join(sorted(card.colors.split(',')))
            color_combo_counts[colors] = color_combo_counts.get(colors, 0) + card.quantity
        else:
            color_combo_counts['Colorless'] = color_combo_counts.get('Colorless', 0) + card.quantity
    
    # Sort and get top color combinations
    sorted_combos = sorted(color_combo_counts.items(), key=lambda x: x[1], reverse=True)
    # Keep as list of tuples to preserve order, convert to list of dicts for JSON
    top_combos = [{'name': combo, 'count': count} for combo, count in sorted_combos[:10]]
    
    # Count by card type
    type_counts = {}
    for card in cards:
        if card.type_line:
            # Extract main card types from type line
            type_line = card.type_line.lower()
            
            # Check for each major type
            if 'creature' in type_line:
                type_counts['Creature'] = type_counts.get('Creature', 0) + card.quantity
            if 'planeswalker' in type_line:
                type_counts['Planeswalker'] = type_counts.get('Planeswalker', 0) + card.quantity
            if 'instant' in type_line:
                type_counts['Instant'] = type_counts.get('Instant', 0) + card.quantity
            if 'sorcery' in type_line:
                type_counts['Sorcery'] = type_counts.get('Sorcery', 0) + card.quantity
            if 'enchantment' in type_line:
                type_counts['Enchantment'] = type_counts.get('Enchantment', 0) + card.quantity
            if 'artifact' in type_line:
                type_counts['Artifact'] = type_counts.get('Artifact', 0) + card.quantity
            if 'land' in type_line:
                type_counts['Land'] = type_counts.get('Land', 0) + card.quantity
            if 'battle' in type_line:
                type_counts['Battle'] = type_counts.get('Battle', 0) + card.quantity
    
    return jsonify({
        'total_cards': total_cards,
        'unique_cards': unique_cards,
        'total_value': f'{total_value:.2f}',
        'avg_price': f'{avg_price:.2f}',
        'rarity_counts': rarity_counts,
        'color_counts': color_counts,
        'mana_value_counts': dict(sorted(mana_value_counts.items())),
        'color_combo_counts': top_combos,
        'type_counts': type_counts
    })


@app.route('/api/decks')
def get_decks():
    """Get all decks"""
    decks = Deck.query.all()
    return jsonify({
        'decks': [deck.to_dict() for deck in decks]
    })


@app.route('/api/deck/<int:deck_id>')
def get_deck(deck_id):
    """Get a specific deck"""
    deck = Deck.query.get_or_404(deck_id)
    return jsonify(deck.to_dict())


@app.route('/api/deck/import', methods=['POST'])
def import_deck():
    """Import a deck from Archidekt"""
    data = request.json
    archidekt_url = data.get('url', '')
    
    if not archidekt_url:
        return jsonify({'error': 'URL is required'}), 400
    
    # Extract deck ID from URL
    # Archidekt URLs look like: https://archidekt.com/decks/123456
    match = re.search(r'archidekt\.com/decks/(\d+)', archidekt_url)
    if not match:
        return jsonify({'error': 'Invalid Archidekt URL'}), 400
    
    deck_id = match.group(1)
    
    try:
        # Fetch deck data from Archidekt API
        api_url = f'https://archidekt.com/api/decks/{deck_id}/'
        response = requests.get(api_url, headers={'User-Agent': 'MTG Collection Manager'})
        response.raise_for_status()
        deck_data = response.json()
        
        # Check if deck already exists
        existing_deck = Deck.query.filter_by(archidekt_id=deck_id).first()
        if existing_deck:
            deck = existing_deck
            deck.updated_date = datetime.utcnow()
            # Clear existing card associations for re-import by directly deleting from association table
            db.session.execute(
                card_deck_association.delete().where(
                    card_deck_association.c.deck_id == existing_deck.id
                )
            )
            db.session.commit()
        else:
            # Create new deck
            deck = Deck(
                name=deck_data.get('name', 'Untitled Deck'),
                archidekt_id=deck_id,
                archidekt_url=archidekt_url,
                format=deck_data.get('format'),
                description=deck_data.get('description'),
            )
            db.session.add(deck)
            # Commit the deck so it has an ID before we add card associations
            db.session.commit()
        
        # Get commander if it exists
        commanders = [card for card in deck_data.get('cards', []) if card.get('categories', []) and 'Commander' in card['categories']]
        if commanders:
            deck.commander = commanders[0].get('card', {}).get('name')
        
        # Import cards
        cards_added = 0
        cards_data = deck_data.get('cards', [])
        
        # Track which cards we've already added to this deck in this import
        cards_in_this_deck = set()
        
        for card_entry in cards_data:
            card_info = card_entry.get('card', {})
            oracle_card = card_info.get('oracleCard', {})
            
            card_name = oracle_card.get('name')
            if not card_name:
                continue
            
            quantity = card_entry.get('quantity', 1)
            
            # Check if the card is foil from Archidekt data
            # Archidekt stores modifier as 'Foil' for foil cards
            is_foil = card_entry.get('modifier') == 'Foil'
            
            # Get the specific printing info from Archidekt
            # Archidekt provides set code and collector number for the exact printing
            edition = card_info.get('edition', {})
            set_code = edition.get('editioncode', '').lower()
            collector_number = card_info.get('collectorNumber', '')
            
            # Try to find the exact printing on Scryfall using set and collector number
            scryfall_card = None
            
            if set_code and collector_number:
                # Use Scryfall's set + collector number lookup for exact printing
                try:
                    endpoint = f"{scryfall.BASE_URL}/cards/{set_code}/{collector_number}"
                    scryfall._rate_limit()
                    response = scryfall.session.get(endpoint)
                    if response.status_code == 200:
                        scryfall_card = response.json()
                except Exception as e:
                    print(f"Could not find exact printing for {card_name} ({set_code} #{collector_number}): {e}")
            
            # Fallback: if we couldn't find the exact printing, try by name
            if not scryfall_card:
                scryfall_card = scryfall.get_card_by_name(card_name)
            
            if not scryfall_card:
                print(f"Could not find card: {card_name}")
                continue
            
            card_details = ScryfallAPI.extract_card_info(scryfall_card)
            
            # Create a unique key for this card (scryfall_id + foil status)
            card_key = (card_details['scryfall_id'], is_foil)
            
            # Check if this exact printing already exists in collection
            # Match by scryfall_id (unique to each printing) and foil status
            existing_card = Card.query.filter_by(
                scryfall_id=card_details['scryfall_id'],
                foil=is_foil
            ).first()
            
            if existing_card:
                # Exact same printing exists, add to deck only if we haven't already in this import
                if card_key not in cards_in_this_deck:
                    existing_card.decks.append(deck)
                    cards_in_this_deck.add(card_key)
                    cards_added += 1
            else:
                # Create new card (different printing or not in collection)
                new_card = Card(
                    scryfall_id=card_details['scryfall_id'],
                    name=card_details['name'],
                    set_code=card_details['set_code'],
                    set_name=card_details['set_name'],
                    collector_number=card_details['collector_number'],
                    rarity=card_details['rarity'],
                    mana_cost=card_details['mana_cost'],
                    cmc=card_details['cmc'],
                    type_line=card_details['type_line'],
                    oracle_text=card_details['oracle_text'],
                    colors=card_details['colors'],
                    color_identity=card_details['color_identity'],
                    image_small=card_details['image_small'],
                    image_normal=card_details['image_normal'],
                    image_large=card_details['image_large'],
                    image_art_crop=card_details['image_art_crop'],
                    price_usd=card_details['price_usd'],
                    price_usd_foil=card_details['price_usd_foil'],
                    scryfall_uri=card_details['scryfall_uri'],
                    quantity=1,  # Start with 1, user can update quantity later
                    foil=is_foil,
                    condition='NM'
                )
                new_card.decks.append(deck)
                db.session.add(new_card)
                cards_in_this_deck.add(card_key)
                cards_added += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported deck "{deck.name}" with {cards_added} cards',
            'deck': deck.to_dict()
        }), 201
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch deck from Archidekt: {str(e)}'}), 500
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to import deck: {str(e)}'}), 500


@app.route('/api/deck/<int:deck_id>', methods=['DELETE'])
def delete_deck(deck_id):
    """Delete a deck (removes deck but keeps cards in collection)"""
    deck = Deck.query.get_or_404(deck_id)
    db.session.delete(deck)
    db.session.commit()
    return jsonify({'message': 'Deck deleted successfully'})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)
