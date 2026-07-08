from enum import StrEnum, auto


class PlanName(StrEnum):
    GROWTH = "growth"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class MetricType(StrEnum):
    API_REQUEST = auto()
    LISTING = auto()


class HttpMethod(StrEnum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
