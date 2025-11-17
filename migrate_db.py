"""
Database migration script to add Deck table
Run this once to update your existing database
"""

from app import app, db

with app.app_context():
    # Create all tables (will only create missing ones)
    db.create_all()
    print("Database updated successfully!")
    print("New tables created if they didn't exist.")
