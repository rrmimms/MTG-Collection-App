"""
Database models for MTG Collection Manager
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


# Association table for many-to-many relationship between cards and decks
card_deck_association = db.Table('card_deck',
    db.Column('card_id', db.Integer, db.ForeignKey('cards.id'), primary_key=True),
    db.Column('deck_id', db.Integer, db.ForeignKey('decks.id'), primary_key=True),
    db.Column('quantity_in_deck', db.Integer, default=1)
)


class Deck(db.Model):
    """Model for decks"""
    
    __tablename__ = 'decks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    archidekt_id = db.Column(db.String(50), unique=True)
    archidekt_url = db.Column(db.String(500))
    format = db.Column(db.String(50))
    description = db.Column(db.Text)
    commander = db.Column(db.String(200))
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to cards
    cards = db.relationship('Card', secondary=card_deck_association, backref='decks', lazy='dynamic')
    
    def __repr__(self):
        return f'<Deck {self.name}>'
    
    def to_dict(self):
        """Convert deck to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'archidekt_id': self.archidekt_id,
            'archidekt_url': self.archidekt_url,
            'format': self.format,
            'description': self.description,
            'commander': self.commander,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'updated_date': self.updated_date.isoformat() if self.updated_date else None,
            'card_count': self.cards.count()
        }


class Card(db.Model):
    """Model for individual cards in the collection"""
    
    __tablename__ = 'cards'
    
    id = db.Column(db.Integer, primary_key=True)
    scryfall_id = db.Column(db.String(36), nullable=False)
    name = db.Column(db.String(200), nullable=False, index=True)
    set_code = db.Column(db.String(10), nullable=False)
    set_name = db.Column(db.String(200))
    collector_number = db.Column(db.String(20))
    rarity = db.Column(db.String(20))
    mana_cost = db.Column(db.String(50))
    cmc = db.Column(db.Float, default=0)
    type_line = db.Column(db.String(200))
    oracle_text = db.Column(db.Text)
    colors = db.Column(db.String(50))  # Comma-separated
    color_identity = db.Column(db.String(50))  # Comma-separated
    
    # Image URLs
    image_small = db.Column(db.String(500))
    image_normal = db.Column(db.String(500))
    image_large = db.Column(db.String(500))
    image_art_crop = db.Column(db.String(500))
    
    # Pricing
    price_usd = db.Column(db.String(20))
    price_usd_foil = db.Column(db.String(20))
    price_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Collection info
    quantity = db.Column(db.Integer, default=1)
    foil = db.Column(db.Boolean, default=False)
    condition = db.Column(db.String(20), default='NM')  # NM, LP, MP, HP, DMG
    notes = db.Column(db.Text)
    
    # External link
    scryfall_uri = db.Column(db.String(500))
    
    # Timestamps
    added_date = db.Column(db.DateTime, default=datetime.utcnow)
    updated_date = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Card {self.name} ({self.set_code})>'
    
    def to_dict(self):
        """Convert card to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'scryfall_id': self.scryfall_id,
            'name': self.name,
            'set_code': self.set_code,
            'set_name': self.set_name,
            'collector_number': self.collector_number,
            'rarity': self.rarity,
            'mana_cost': self.mana_cost,
            'cmc': self.cmc,
            'type_line': self.type_line,
            'oracle_text': self.oracle_text,
            'colors': self.colors.split(',') if self.colors else [],
            'color_identity': self.color_identity.split(',') if self.color_identity else [],
            'image_small': self.image_small,
            'image_normal': self.image_normal,
            'image_large': self.image_large,
            'image_art_crop': self.image_art_crop,
            'price_usd': self.price_usd,
            'price_usd_foil': self.price_usd_foil,
            'price_updated': self.price_updated.isoformat() if self.price_updated else None,
            'quantity': self.quantity,
            'foil': self.foil,
            'condition': self.condition,
            'notes': self.notes,
            'scryfall_uri': self.scryfall_uri,
            'added_date': self.added_date.isoformat() if self.added_date else None,
            'updated_date': self.updated_date.isoformat() if self.updated_date else None,
            'decks': [{'id': deck.id, 'name': deck.name} for deck in self.decks]
        }
    
    @property
    def total_value(self):
        """Calculate total value of this card entry"""
        price = self.price_usd_foil if self.foil and self.price_usd_foil else self.price_usd
        if price:
            try:
                return float(price) * self.quantity
            except (ValueError, TypeError):
                return 0
        return 0
