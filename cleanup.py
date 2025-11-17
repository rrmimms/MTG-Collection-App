"""
Cleanup script - removes all decks and optionally all cards
"""

from app import app, db, Deck, Card, card_deck_association

def cleanup_decks_only():
    """Remove all decks but keep cards in collection"""
    with app.app_context():
        # First delete all associations
        db.session.execute(card_deck_association.delete())
        
        # Then delete all decks
        decks = Deck.query.all()
        for deck in decks:
            db.session.delete(deck)
        
        db.session.commit()
        print(f"Deleted {len(decks)} decks. Cards remain in collection.")

def cleanup_everything():
    """Remove all decks AND all cards - fresh start"""
    with app.app_context():
        deck_count = Deck.query.count()
        card_count = Card.query.count()
        
        # Delete associations FIRST
        db.session.execute(card_deck_association.delete())
        
        # Then delete all decks
        Deck.query.delete()
        
        # Then delete all cards
        Card.query.delete()
        
        db.session.commit()
        print(f"Deleted {deck_count} decks and {card_count} cards.")
        print("Collection is now empty - fresh start!")

if __name__ == '__main__':
    print("Choose cleanup option:")
    print("1. Remove only decks (keep all cards)")
    print("2. Remove EVERYTHING (decks and cards)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        confirm = input("Remove all decks but keep cards? (yes/no): ").strip().lower()
        if confirm == "yes":
            cleanup_decks_only()
        else:
            print("Cancelled.")
    elif choice == "2":
        confirm = input("WARNING: This will delete ALL cards and decks. Are you sure? (yes/no): ").strip().lower()
        if confirm == "yes":
            cleanup_everything()
        else:
            print("Cancelled.")
    else:
        print("Invalid choice.")
