import enum


class Attribute(enum.Enum):
    AIR_TEMPERATURE = "air temperature"
    AIR_TEMPERATURE_MIN = "air temperature min"
    AIR_TEMPERATURE_MAX = "air temperature max"
    HUMIDITY = "humidity"
    AIR_PRESSURE = "air pressure"
    CLOUD_COVER = "cloud cover"
    CLOUD_COVER_LOW = "cloud cover low"
    CLOUD_COVER_MEDIUM = "cloud cover medium"
    CLOUD_COVER_HIGH = "cloud cover high"
    PRECIPITATION_AMOUNT = "precipitation amount"
    PRECIPITATION_AMOUNT_MIN = "precipitation amount min"
    PRECIPITATION_AMOUNT_MAX = "precipitation amount max"
    ENERGY = "energy"
    POWER = "power"
