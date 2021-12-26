from pydantic import BaseModel


class Coordinate(BaseModel):
    longitude: float
    latitude: float


class Location(BaseModel):
    id: int
    name: str
    coordinate: Coordinate
