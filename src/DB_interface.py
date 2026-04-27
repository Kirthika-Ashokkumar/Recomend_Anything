"""
DB_interface.py  —  SQLite database interface for Recommend Anything.
Requires: model.py  (same directory)
 
Tables
  users             stores user accounts (hashed passwords, roles)
  recommendations   recommendation posts
  follows           follow relationships between users
  recommends        direct recommendation sends to specific users
  tags              tags attached to recommendations
  multimedia_urls   media URLs attached to recommendations
 
Roles
  ROLE_USER  = 0   standard user
  ROLE_ADMIN = 1   admin — can list/delete all recommendations
 
Key Methods
  User management   create_user, verify_login, get_user_by_username
  Feed              get_recommendations_for_user, get_recommendations_by_tag
  Posting           create_recommendation
  Social            add_follower, is_follower, list_followers, send_reqs
  Admin             list_recommendations, list_recommendations_tags,
                    delete_recommendation, has_permission
 
Password Security
  Passwords are hashed with PBKDF2-HMAC-SHA256 + 16-byte random salt.
  The salt is prepended to the hash and stored together as a BLOB.
  Plain-text passwords are never stored.
"""
import sqlite3
import hashlib
import os
import time
from model import FullRecommendationModel
import logging

# Simple role system (can be expanded later)
ROLE_USER = 0
ROLE_ADMIN = 1

class DatabaseInterface:
    filepath: str

    def __init__(self, filepath: str):
        # Store database file path and ensure tables exist
        self.filepath = filepath
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        self._create_tables()
    
    def _create_tables(self):
        """Create all required tables if they do not already exist."""
        with self._connection() as connection:
            self.logger.info("Creating tables")
            # Users table:
            # - username is UNIQUE to prevent duplicate logins
            # - password stored as BLOB (hashed + salted, not plaintext)
            connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT NOT NULL UNIQUE,
                password    BLOB NOT NULL,
                role        INTEGER NOT NULL
            )
            """)
            connection.commit()
            
            # Remaining tables support recommendation system features
            connection.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                recommendation_id   INTEGER PRIMARY KEY,
                poster_id           INTEGER NOT NULL,
                title               TEXT NOT NULL,
                description         TEXT NOT NULL,
                rating              INTEGER NOT NULL,
                date                INTEGER NOT NULL,
                FOREIGN KEY (poster_id) REFERENCES users(user_id)
                ON DELETE CASCADE
            )
            """)
            
            connection.execute("""
            CREATE TABLE IF NOT EXISTS follows (
                target_user_id      INTEGER NOT NULL,
                follower_user_id    INTEGER NOT NULL,
                PRIMARY KEY (target_user_id, follower_user_id),
                FOREIGN KEY (target_user_id) REFERENCES users(user_id),
                FOREIGN KEY (follower_user_id) REFERENCES users(user_id)
            )
            """)
            
            connection.execute("""
            CREATE TABLE IF NOT EXISTS recommends (
                recommendation_id       INTEGER NOT NULL,
                receiver_id             INTEGER NOT NULL,
                PRIMARY KEY (recommendation_id, receiver_id),
                FOREIGN KEY (recommendation_id) REFERENCES recommendations(recommendation_id),
                FOREIGN KEY (receiver_id) REFERENCES users(user_id)
            )
            """)
            
            connection.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                recommendation_id       INTEGER NOT NULL,
                tag                     TEXT NOT NULL,
                PRIMARY KEY (recommendation_id, tag),
                FOREIGN KEY (recommendation_id) REFERENCES recommendations(recommendation_id) ON DELETE CASCADE
            )
            """)
            
            connection.execute("""
            CREATE TABLE IF NOT EXISTS multimedia_urls (
                recommendation_id       INTEGER NOT NULL,
                multimedia_url          TEXT NOT NULL,
                PRIMARY KEY (recommendation_id, multimedia_url),
                FOREIGN KEY (recommendation_id) REFERENCES recommendations(recommendation_id) ON DELETE CASCADE
            )
            """)
    
    def _connection(self) -> sqlite3.Connection:
        """Create a new database connection."""
        return sqlite3.connect(self.filepath)
    
    
    def get_hydrated_recommendation(self, recommendation_id: int) -> FullRecommendationModel:
        """
        Retrieve a recommendation and "hydrate" it with related data:
        - tags
        - multimedia URLs

        Note: No permission checks here (any caller can fetch anything).
        """
        
        with self._connection() as connection:
            # Get main recommendation row
            cursor = connection.execute("""
            SELECT r.* FROM recommendations r 
                WHERE r.recommendation_id = ?
            """, (recommendation_id,))
            recommendation_id, poster_id, title, description, rating, date = cursor.fetchone()
            
            # Fetch associated tags
            cursor = connection.execute("""
            SELECT tag FROM tags
                WHERE tags.recommendation_id = ?
            """, (recommendation_id,))
            tags = [tag for (tag,) in cursor.fetchall()]
            
            # Fetch associated media URLs
            cursor = connection.execute("""
            SELECT multimedia_url FROM multimedia_urls
                WHERE multimedia_urls.recommendation_id = ?
            """, (recommendation_id,))
            multimedia_urls = [url for (url,) in cursor.fetchall()]
            
            self.logger.info(f"Fetched hydrated recommendation. R\"{recommendation_id}\" - {title}")
            
            return FullRecommendationModel(
                recommendation_id, poster_id, title,
                description, rating, date,
                tags=tags, multimedia_urls=multimedia_urls
            )
        
    
    def get_recommendations_for_user(self, user_id: int, offset:int = 0, limit: int = 10) -> list[FullRecommendationModel]:
        """
        Get recommendations visible to a user:
        - From users they follow
        - Directly recommended to them

        Uses pagination (limit + offset).
        """
        with self._connection() as connection:
            cursor = connection.execute("""
            SELECT r.recommendation_id FROM recommendations r 
                JOIN follows f ON r.poster_id = f.target_user_id
                WHERE f.follower_user_id = ?
            UNION
            SELECT r.recommendation_id FROM recommendations r 
                JOIN recommends m ON r.recommendation_id = m.recommendation_id
                WHERE m.receiver_id = ?
            LIMIT ?
            OFFSET ?
            """, (user_id, user_id, limit, offset))
            
            recommendation_ids = [
                recommendation_id
                for (recommendation_id,) in cursor.fetchall()
            ]
            
            self.logger.info(f"Fetched recommendations for user U\"{user_id}\". {len(recommendation_ids)} matches.")
        
        # Convert IDs into full objects
        return [
            self.get_hydrated_recommendation(recommendation_id)
            for recommendation_id in recommendation_ids
        ]
    
    def get_recommendations_by_tag(self, tag: str, user_id: int, offset: int = 0, limit: int = 50) -> list[FullRecommendationModel]:
        """
        Get recommendations visible to the user, filtered by tag.
        Visible = from followed users OR directly sent to them.
        """
        with self._connection() as connection:
            cursor = connection.execute("""
            SELECT r.recommendation_id FROM recommendations r
                JOIN tags t ON r.recommendation_id = t.recommendation_id
                WHERE t.tag = ?
                AND r.recommendation_id IN (
                    SELECT r2.recommendation_id FROM recommendations r2
                        JOIN follows f ON r2.poster_id = f.target_user_id
                        WHERE f.follower_user_id = ?
                    UNION
                    SELECT m.recommendation_id FROM recommends m
                        WHERE m.receiver_id = ?
                )
            LIMIT ?
            OFFSET ?
            """, (tag, user_id, user_id, limit, offset))

            recommendation_ids = [
                recommendation_id
                for (recommendation_id,) in cursor.fetchall()
            ]
            
            self.logger.info(f"Fetched recommendation with tag T\"{tag}\" for user U\"{user_id}\". {len(recommendation_ids)} matches.")

        return [
            self.get_hydrated_recommendation(recommendation_id)
            for recommendation_id in recommendation_ids
        ]

    # -------------------------
    # Follower FUNCTIONS
    # -------------------------

    def add_follower(self, target_user_id: int, follower_user_id: int):
        with self._connection() as connection:
            connection.execute("""
            INSERT INTO follows(target_user_id, follower_user_id) VALUES (?, ?)
            """, (target_user_id, follower_user_id))
            connection.commit() 
            self.logger.info(f"U\"{follower_user_id}\" follows U\"{target_user_id}\"")
    
    def send_reqs(self, recommendation_id: int, receiver_id: int):
        """Recommend specific followers"""
        with self._connection() as connection:
            connection.execute("""
            INSERT INTO recommends(recommendation_id, receiver_id) VALUES (?, ?)
            """, (recommendation_id, receiver_id))
            connection.commit()
            self.logger.info(f"Recommend R\"{recommendation_id}\" to U\"{receiver_id}\"")

    def list_followers(self, target_user_id: int) -> list[str]:
        """
        list  followers
        """
        with self._connection() as connection:
            cursor = connection.execute("""
            SELECT u.username FROM follows f
                JOIN users u ON f.follower_user_id = u.user_id
                WHERE target_user_id = ?
            """, (target_user_id,))
            
            usernames = []
            for row in cursor.fetchall():
                username = row[0]
                usernames.append(username)

            self.logger.info(f"U\"{target_user_id}\" has {len(usernames)} followers.")

            return usernames
    
    def is_follower(self, target_user_id: int, follower_user_id: int) -> bool:
        """
        Check if follower_user_id follows target_user_id.
        Returns True if the follow relationship exists, False otherwise.
        """
        with self._connection() as connection:
            cursor = connection.execute("""
                SELECT COUNT(*) FROM follows
                WHERE target_user_id = ? AND follower_user_id = ?
            """, (target_user_id, follower_user_id))
            return cursor.fetchone()[0] > 0


    # -------------------------
    # ADMIN FUNCTIONS
    # -------------------------
    def has_permission(self, user_id: int, role: int):
        with self._connection() as connection:
            cursor = connection.execute('''
                SELECT COUNT(*) 
                FROM users u
                WHERE u.user_id = ? AND u.role = ?
            ''', (user_id, role))
        if cursor.fetchone()[0] > 0:
            return True
        return False

    def list_recommendations(self, role: int, user_id: int, offset: int = 0, limit: int = 50) -> list[FullRecommendationModel]:
        """
        Get recommendations for specific user
        Uses pagination (limit + offset) to be consistent
        """
        if self.has_permission(user_id, role):
            with self._connection() as connection:
                cursor = connection.execute("""
                SELECT r.recommendation_id FROM recommendations r
                LIMIT ?
                OFFSET ?
                """, (limit, offset))

                recommendation_ids = [
                    recommendation_id
                    for (recommendation_id,) in cursor.fetchall()
                ]
            
            # Convert IDs into full objects
            return [
                self.get_hydrated_recommendation(recommendation_id)
                for recommendation_id in recommendation_ids
            ]
        self.logger.error(f"U\"{user_id}\" attempted to use a admin function, however they were not an admin.")
        return []

    def delete_recommendation(self, role: int, user_id: int, recommendation_id: int):
        """
        Delete recommendations from specific recommendation_id
        
        """
        try:
            if self.has_permission(user_id, role):
                with self._connection() as connection:
                    cursor = connection.execute("""
                    DELETE FROM recommendations
                    WHERE recommendation_id = ?
                    """, (recommendation_id,))
                    connection.commit()
                return True
            self.logger.error(f"U\"{user_id}\" attempted to use a admin function, however they were not an admin.")
        except sqlite3.IntegrityError:
            self.logger.error(f"Failed to delete R\"{user_id}\"")
            # Triggered by violations of DELETE constraints
            return False
        
    def list_recommendations_tags(self, role: int, user_id: int, tag: str, offset: int = 0, limit: int = 50) -> list[FullRecommendationModel]:
        """
        Get recommendations for specific tag
        Uses pagination (limit + offset) to be consistent
        """
        if self.has_permission(user_id, role):
            with self._connection() as connection:
                cursor = connection.execute("""
                SELECT r.recommendation_id FROM recommendations r
                JOIN tags t ON r.recommendation_id = t.recommendation_id 
                WHERE t.tag = ?
                LIMIT ?
                OFFSET ?
                """, (tag, limit, offset))

                recommendation_ids = [
                    recommendation_id
                    for (recommendation_id,) in cursor.fetchall()
                ]
            
            # Convert IDs into full objects
            return [
                self.get_hydrated_recommendation(recommendation_id)
                for recommendation_id in recommendation_ids
            ]
        self.logger.error(f"U\"{user_id}\" attempted to use a admin function, however they were not an admin.")
        return []


    # Create recommendation
    def create_recommendation(
        self,
        poster_id: int,
        title: str,
        description: str,
        rating: int,
        tags: list[str] | None = None,
        multimedia_urls: list[str] | None = None
    ) -> FullRecommendationModel:
        """
        Create a new recommendation post with tags and multimedia URLs.

        This is the functionality:
        - Insert the main recommendation into recommendations
        - Insert tags into tags
        - Insert multimedia URLs into multimedia_urls
        - Return the full hydrated recommendation
        """

        if tags is None:
            tags = []

        if multimedia_urls is None:
            multimedia_urls = []

        if title.strip() == "":
            raise ValueError("Title cannot be empty.")

        if description.strip() == "":
            raise ValueError("Description cannot be empty.")

        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5.")

        date = int(time.time())

        with self._connection() as connection:
            cursor = connection.execute("""
                INSERT INTO recommendations
                (poster_id, title, description, rating, date)
                VALUES (?, ?, ?, ?, ?)
            """, (poster_id, title, description, rating, date))

            recommendation_id = cursor.lastrowid

            for tag in tags:
                cleaned_tag = tag.strip().lower()

                if cleaned_tag != "":
                    connection.execute("""
                        INSERT INTO tags
                        (recommendation_id, tag)
                        VALUES (?, ?)
                    """, (recommendation_id, cleaned_tag))

            for url in multimedia_urls:
                cleaned_url = url.strip()

                if cleaned_url != "":
                    connection.execute("""
                        INSERT INTO multimedia_urls
                        (recommendation_id, multimedia_url)
                        VALUES (?, ?)
                    """, (recommendation_id, cleaned_url))

            connection.commit()
            
            self.logger.info(f"Created Recommendation R\"{recommendation_id}\"")

        return self.get_hydrated_recommendation(recommendation_id)
    

    # -------------------------
    # PASSWORD HANDLING
    # -------------------------

    def _hash_password(self, password: str) -> bytes:
        """
        Hash a password using PBKDF2 + SHA-256.

        - Generates a random salt
        - Returns: salt + hash (stored together in DB)
        """
        salt = os.urandom(16)

        hashed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000  # iteration count (slows brute-force attacks)
        )

        return salt + hashed


    def _check_password(self, password: str, stored_password: bytes) -> bool:
        """
        Verify a password against stored (salt + hash).

        Steps:
        1. Extract salt from stored value
        2. Recompute hash with same salt
        3. Compare results
        """
        salt = stored_password[:16]
        stored_hash = stored_password[16:]

        test_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            100000
        )

        return test_hash == stored_hash


    # -------------------------
    # USER MANAGEMENT
    # -------------------------

    def create_user(self, username: str, password: str, role: int = 0) -> bool:
        """
        Create a new user.

        - Hashes password before storing
        - Returns False if username already exists
        """
        hashed_password = self._hash_password(password)

        try:
            with self._connection() as connection:
                connection.execute("""
                    INSERT INTO users (username, password, role)
                    VALUES (?, ?, ?)
                """, (username, hashed_password, role))
                connection.commit()
            return True

        except sqlite3.IntegrityError:
            # Triggered by UNIQUE constraint on username
            self.logger.warning(f"\"{username}\" already exists.")
            return False


    def verify_login(self, username: str, password: str) -> int | None:
        """
        Verify login credentials.

        Returns:
        - user_id if login is successful
        - None if username not found or password incorrect
        """
        with self._connection() as connection:
            cursor = connection.execute("""
                SELECT user_id, password FROM users
                WHERE username = ?
            """, (username,))
            row = cursor.fetchone()

        if row is None:
            return None

        user_id, stored_password = row

        if self._check_password(password, stored_password):
            return user_id

        self.logger.warning(f"Failed log in attempt for U\"{username}\"")
        return None


    def get_user_by_username(self, username: str):
        """
        Fetch basic user info (no password).

        Useful after login to get role or display name.
        """
        with self._connection() as connection:
            cursor = connection.execute("""
                SELECT user_id, username, role
                FROM users
                WHERE username = ?
            """, (username,))
        return cursor.fetchone()


# -------------------------
# SIMPLE CLI TEST INTERFACE
# -------------------------

if __name__ == "__main__":
    logging.basicConfig(filename="logs/test.log",
                    filemode='a',
                    format='%(asctime)s,%(msecs)03d %(name)s %(levelname)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    level=logging.DEBUG)
    db = DatabaseInterface("./test.db")

    # Basic command-line interaction for testing
    action = input("Choose action (register/login): ").strip().lower()
    username = input("Username: ").strip()
    password = input("Password: ").strip()

    if action == "register":
        created = db.create_user(username, password, ROLE_USER)

        if created:
            print("User created successfully.")
        else:
            print("Username already exists.")

    elif action == "login":
        user_id = db.verify_login(username, password)

        if user_id is not None:
            print(f"Login successful. User ID: {user_id}")
        else:
            print("Invalid username or password.")

    else:
        print("Invalid action.")
