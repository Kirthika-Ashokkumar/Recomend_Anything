class RecommendationModel:
    recommendation_id: int
    poster_id: int
    title: str
    description: str
    rating: int
    date: int
    def __init__(self,
        recommendation_id: int,
        poster_id: int,
        title: str,
        description: str,
        rating: int,
        date: int):
        self.recommendation_id = recommendation_id
        self.poster_id = poster_id
        self.title = title
        self.description = description
        self.rating = rating
        self.date = date
    
    def __repr__(self):
        return f"""Recommendation(recommendation_id={self.recommendation_id}, poster_id={self.poster_id}, title="{self.title}", description="{self.description}", rating={self.rating}, date={self.date})"""


class FullRecommendationModel:
    recommendation_id: int
    poster_id: int
    title: str
    description: str
    rating: int
    date: int
    tags: list[str]
    multimedia_urls: list[str]
    def __init__(self,
        recommendation_id: int,
        poster_id: int,
        title: str,
        description: str,
        rating: int,
        date: int,
        tags: list[str],
        multimedia_urls: list[str]
    ):
        self.recommendation_id = recommendation_id
        self.poster_id = poster_id
        self.title = title
        self.description = description
        self.rating = rating
        self.date = date
        self.tags = tags
        self.multimedia_urls = multimedia_urls
    
    def __repr__(self):
        return f"""FullRecommendation(recommendation_id={self.recommendation_id}, poster_id={self.poster_id}, title="{self.title}", description="{self.description}", rating={self.rating}, date={self.date}, tags=[{",".join([ f"\"{i}\"" for i in self.tags])}]), multimedia_urls=[{",".join([ f"\"{i}\"" for i in self.multimedia_urls])}])"""
        
