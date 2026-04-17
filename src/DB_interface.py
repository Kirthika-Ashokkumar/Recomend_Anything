import sqlite3
from model import FullRecommendationModel

class DatabaseInterface:
    filepath: str
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._create_tables()
    
    def _create_tables(self):
        """ Create tables, if they do not already exist """
        with self._connection() as connection:
            connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT NOT NULL,
                password    BLOB NOT NULL,
                role        INTEGER NOT NULL
            )
            """)
            connection.commit()
            
            connection.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                recommendation_id   INTEGER PRIMARY KEY,
                poster_id           INTEGER NOT NULL,
                title               TEXT NOT NULL,
                description         TEXT NOT NULL,
                rating              INTEGER NOT NULL,
                date                INTEGER NOT NULL,
                FOREIGN KEY (poster_id) REFERENCES users(user_id)
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
        """Create a connection

        Returns:
            sqlite3.Connection: Connection to the configured database
        """
        return sqlite3.connect(self.filepath)
    
    
    def get_hydrated_recommendation(self, recommendation_id: int) -> FullRecommendationModel:
        """ 
            Get hydrated recommendation, including the list of tags and multimedia urls.
            Probably shouldn't expose. This makes no checks if the user is even supposed to be able to see this recommendation.
        """
        
        with self._connection() as connection:
            cursor = connection.execute("""
            SELECT r.* FROM recommendations r 
                WHERE r.recommendation_id = ?
            """, (recommendation_id,))
            recommendation_id, poster_id, title, description, rating, date = cursor.fetchone()
            
            cursor = connection.execute("""
            SELECT tag FROM tags
                WHERE tags.recommendation_id = ?
            """, (recommendation_id,))
            tags = [ tag for (tag,) in cursor.fetchall()]
            
            cursor = connection.execute("""
            SELECT multimedia_url FROM multimedia_urls
                WHERE multimedia_urls.recommendation_id = ?
            """, (recommendation_id,))
            multimedia_urls = [ multimedia_url for (multimedia_url,) in cursor.fetchall()]
            
            return FullRecommendationModel(recommendation_id, poster_id, title, description, rating, date, tags=tags, multimedia_urls=multimedia_urls)
        
    
    def get_recommendations_for_user(self, user_id: int, offset:int = 0, limit: int = 10) -> list[FullRecommendationModel]:
        """
            Return a list of hydrated recommendations for a given user. 
            This combines recommendations of the user that they follow plus the recommendations sent by another user.
            Includes a simple pagination scheme.
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
        
        return [
            self.get_hydrated_recommendation(recommendation_id)
            for recommendation_id in recommendation_ids
        ]


if __name__ == "__main__":
    # Test code
    db = DatabaseInterface("./test.db")
    results = db.get_recommendations_for_user(1)
    print(results)