import enum


class Attribute(str, enum.Enum):
    AIR_PRESSURE = "air pressure"
    AIR_TEMPERATURE = "air temperature"
    AIR_TEMPERATURE_MAX = "air temperature max"
    AIR_TEMPERATURE_MIN = "air temperature min"
    CLOUD_COVER = "cloud cover"
    CLOUD_COVER_HIGH = "cloud cover high"
    CLOUD_COVER_LOW = "cloud cover low"
    CLOUD_COVER_MEDIUM = "cloud cover medium"
    ENERGY = "energy"
    HUMIDITY = "humidity"
    POWER = "power"
    POWER_STATE = "power state"
    PRECIPITATION_AMOUNT = "precipitation amount"
    PRECIPITATION_AMOUNT_MAX = "precipitation amount max"
    PRECIPITATION_AMOUNT_MIN = "precipitation amount min"
