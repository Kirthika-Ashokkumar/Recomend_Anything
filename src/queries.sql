CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    password    BLOB NOT NULL,
    role        INTEGER NOT NULL
)

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id   INTEGER PRIMARY KEY,
    poster_id           INTEGER NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    rating              INTEGER NOT NULL,
    date                INTEGER NOT NULL,
    FOREIGN KEY (poster_id) REFERENCES users(user_id)
)

CREATE TABLE IF NOT EXISTS follows (
    target_user_id      INTEGER NOT NULL,
    follower_user_id    INTEGER NOT NULL,
    PRIMARY KEY (target_user_id, follower_user_id),
    FOREIGN KEY (target_user_id) REFERENCES users(user_id),
    FOREIGN KEY (follower_user_id) REFERENCES users(user_id)
)

CREATE TABLE IF NOT EXISTS recommends (
    recommendation_id       INTEGER NOT NULL,
    receiver_id             INTEGER NOT NULL,
    PRIMARY KEY (recommendation_id, receiver_id),
    FOREIGN KEY (recommendation_id) REFERENCES
        recommendations(recommendation_id),
    FOREIGN KEY (receiver_id) REFERENCES users(user_id)
)

CREATE TABLE IF NOT EXISTS tags (
    recommendation_id       INTEGER NOT NULL,
    tag                     TEXT NOT NULL,
    PRIMARY KEY (recommendation_id, tag),
    FOREIGN KEY (recommendation_id) REFERENCES recommendations(recommendation_id) ON DELETE CASCADE
)

CREATE TABLE IF NOT EXISTS multimedia_urls (
     recommendation_id       INTEGER NOT NULL,
     multimedia_url          TEXT NOT NULL,
     PRIMARY KEY (recommendation_id, multimedia_url),
     FOREIGN KEY (recommendation_id) REFERENCES recommendations(recommendation_id) ON DELETE CASCADE
)

-- Get all recommendations with a given id.
SELECT r.* FROM recommendations r 
    WHERE r.recommendation_id = ?;

-- Get all tags for a given recommendation
SELECT tag FROM tags
    WHERE tags.recommendation_id = ?

-- Get all urls for a given recommendation
SELECT multimedia_url FROM multimedia_urls
    WHERE multimedia_urls.recommendation_id = ?

-- Get all recommendations from users a user follows or is recommended to a user, with pagination
SELECT r.recommendation_id FROM recommendations r 
    JOIN follows f ON r.poster_id = f.target_user_id
    WHERE f.follower_user_id = ?
UNION
SELECT r.recommendation_id FROM recommendations r 
    JOIN recommends m ON r.recommendation_id = m.recommendation_id
    WHERE m.receiver_id = ?
    LIMIT ?
    OFFSET ?

-- Same as last query, but filter by tags
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

-- Add follower
INSERT INTO follows(target_user_id, follower_user_id) VALUES (?, ?)

-- Recommend recommendation
INSERT INTO recommends(recommendation_id, receiver_id) VALUES (?, ?)

-- Get all followers for a giver user
SELECT u.username FROM follows f
    JOIN users u ON f.follower_user_id = u.user_id
    WHERE target_user_id = ?

-- Check if a given user is following another user
SELECT COUNT(*) FROM follows
    WHERE target_user_id = ? AND follower_user_id = ?

-- List all recommendations
SELECT r.recommendation_id FROM recommendations r
    LIMIT ?
    OFFSET ?

-- Delete a given recommendation
DELETE FROM recommendations
    WHERE recommendation_id = ?

-- List all recommendations with a given tag
SELECT r.recommendation_id FROM recommendations r
    JOIN tags t ON r.recommendation_id = t.recommendation_id 
    WHERE t.tag = ?
    LIMIT ?
    OFFSET ?

-- Post recommendation
INSERT INTO recommendations
    (poster_id, title, description, rating, date)
    VALUES (?, ?, ?, ?, ?)

-- Add tags to a recommendation
INSERT INTO tags
    (recommendation_id, tag)
    VALUES (?, ?)

-- Add urls to a recommendation
INSERT INTO multimedia_urls
    (recommendation_id, multimedia_url)
    VALUES (?, ?)
-- Create user
INSERT INTO users (username, password, role)
    VALUES (?, ?, ?)

-- Get user and hashed password
SELECT user_id, password FROM users
    WHERE username = ?

-- Get user and user information
SELECT user_id, username, role
    FROM users
    WHERE username = ?