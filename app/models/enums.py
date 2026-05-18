from enum import Enum


class AdFormat(str, Enum):
    SINGLE_IMAGE = "SINGLE_IMAGE"
    SINGLE_VIDEO = "SINGLE_VIDEO"
    CAROUSEL = "CAROUSEL"


class AdObjective(str, Enum):
    OUTCOME_AWARENESS = ("OUTCOME_AWARENESS", "Awareness")
    OUTCOME_TRAFFIC = ("OUTCOME_TRAFFIC", "Traffic")
    OUTCOME_ENGAGEMENT = ("OUTCOME_ENGAGEMENT", "Engagement")
    OUTCOME_LEADS = ("OUTCOME_LEADS", "Leads")
    OUTCOME_SALES = ("OUTCOME_SALES", "Sales")
    OUTCOME_APP_PROMOTION = ("OUTCOME_APP_PROMOTION", "App Promotion")

    def __new__(cls, api_value: str, label: str):
        obj = str.__new__(cls, api_value)
        obj._value_ = api_value
        obj.label = label
        return obj

    @classmethod
    def from_label(cls, label: str) -> "AdObjective":
        for member in cls:
            if member.label == label:
                return member
        raise ValueError(f"No AdObjective with label {label!r}")

    @classmethod
    def labels(cls) -> list:
        return [m.label for m in cls]


class AdStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DELETED = "DELETED"
    ARCHIVED = "ARCHIVED"


class BidStrategy(str, Enum):
    LOWEST_COST_WITHOUT_CAP = ("LOWEST_COST_WITHOUT_CAP", "Highest volume (Lowest cost)")
    LOWEST_COST_WITH_BID_CAP = ("LOWEST_COST_WITH_BID_CAP", "Bid cap")
    COST_CAP = ("COST_CAP", "Cost per result goal (Cost cap)")
    LOWEST_COST_WITH_MIN_ROAS = ("LOWEST_COST_WITH_MIN_ROAS", "ROAS goal (Minimum ROAS)")
    TARGET_COST = ("TARGET_COST", "Target cost (deprecated)")

    def __new__(cls, api_value: str, label: str):
        obj = str.__new__(cls, api_value)
        obj._value_ = api_value
        obj.label = label
        return obj

    @classmethod
    def from_label(cls, label: str) -> "BidStrategy":
        for member in cls:
            if member.label == label:
                return member
        raise ValueError(f"No BidStrategy with label {label!r}")

    @classmethod
    def labels(cls) -> list:
        return [m.label for m in cls]


class OptimizationGoal(str, Enum):
    NONE = "NONE"
    REACH = "REACH"
    IMPRESSIONS = "IMPRESSIONS"
    LINK_CLICKS = "LINK_CLICKS"
    LANDING_PAGE_VIEWS = "LANDING_PAGE_VIEWS"
    CONVERSIONS = "CONVERSIONS"
    LEAD_GENERATION = "LEAD_GENERATION"
    QUALITY_LEAD = "QUALITY_LEAD"
    APP_INSTALLS = "APP_INSTALLS"
    VIDEO_VIEWS = "VIDEO_VIEWS"
    THRUPLAY = "THRUPLAY"
    ENGAGEMENT = "ENGAGEMENT"
    VALUE = "VALUE"
    OFFSITE_CONVERSIONS = "OFFSITE_CONVERSIONS"
    AD_RECALL_LIFT = "AD_RECALL_LIFT"
    ENGAGED_USERS = "ENGAGED_USERS"
    EVENT_RESPONSES = "EVENT_RESPONSES"
    PAGE_LIKES = "PAGE_LIKES"
    POST_ENGAGEMENT = "POST_ENGAGEMENT"
    QUALITY_CALL = "QUALITY_CALL"
    VISIT_INSTAGRAM_PROFILE = "VISIT_INSTAGRAM_PROFILE"
    DERIVED_EVENTS = "DERIVED_EVENTS"
    CONVERSATIONS = "CONVERSATIONS"
    IN_APP_VALUE = "IN_APP_VALUE"
    MESSAGING_PURCHASE_CONVERSION = "MESSAGING_PURCHASE_CONVERSION"
    SUBSCRIBERS = "SUBSCRIBERS"
    REMINDERS_SET = "REMINDERS_SET"
    MEANINGFUL_CALL_ATTEMPT = "MEANINGFUL_CALL_ATTEMPT"
    PROFILE_VISIT = "PROFILE_VISIT"


# Ordered UI options for Optimization Goal. Two entries intentionally share an
# API value (REACH, OFFSITE_CONVERSIONS); value_to_label() returns the first match.
OPTIMIZATION_GOAL_UI_OPTIONS: list[tuple[str, str]] = [
    ("Reach", "REACH"),
    ("Impressions", "IMPRESSIONS"),
    ("Ad Recall Lift", "AD_RECALL_LIFT"),
    ("Link Clicks", "LINK_CLICKS"),
    ("Landing Page Views", "LANDING_PAGE_VIEWS"),
    ("Daily Unique Reach", "REACH"),
    ("Post Engagement", "POST_ENGAGEMENT"),
    ("Page Likes", "PAGE_LIKES"),
    ("ThruPlay", "THRUPLAY"),
    ("Conversations (Messages)", "CONVERSATIONS"),
    ("Leads", "LEAD_GENERATION"),
    ("Quality Calls", "QUALITY_CALL"),
    ("Conversions (Pixel/CAPI event)", "OFFSITE_CONVERSIONS"),
    ("Value", "VALUE"),
    ("App Installs", "APP_INSTALLS"),
    ("App Events", "OFFSITE_CONVERSIONS"),
]


def opt_goal_labels() -> list[str]:
    return [label for label, _ in OPTIMIZATION_GOAL_UI_OPTIONS]


def opt_goal_label_to_value(label: str) -> str:
    for lbl, val in OPTIMIZATION_GOAL_UI_OPTIONS:
        if lbl == label:
            return val
    raise ValueError(f"No OptimizationGoal with label {label!r}")


def opt_goal_value_to_label(value: str) -> str:
    for lbl, val in OPTIMIZATION_GOAL_UI_OPTIONS:
        if val == value:
            return lbl
    return value


class BillingEvent(str, Enum):
    IMPRESSIONS = "IMPRESSIONS"
    LINK_CLICKS = "LINK_CLICKS"
    CLICKS = "CLICKS"
    POST_ENGAGEMENT = "POST_ENGAGEMENT"
    PAGE_LIKES = "PAGE_LIKES"
    APP_INSTALLS = "APP_INSTALLS"
    VIDEO_VIEWS = "VIDEO_VIEWS"
    THRUPLAY = "THRUPLAY"
    NONE = "NONE"
    OFFER_CLAIMS = "OFFER_CLAIMS"
    PURCHASE = "PURCHASE"
    LISTING_INTERACTION = "LISTING_INTERACTION"


class CallToAction(str, Enum):
    NO_BUTTON = "NO_BUTTON"
    LEARN_MORE = "LEARN_MORE"
    SHOP_NOW = "SHOP_NOW"
    SIGN_UP = "SIGN_UP"
    DOWNLOAD = "DOWNLOAD"
    BOOK_TRAVEL = "BOOK_TRAVEL"
    CONTACT_US = "CONTACT_US"
    APPLY_NOW = "APPLY_NOW"
    GET_OFFER = "GET_OFFER"
    GET_QUOTE = "GET_QUOTE"
    SUBSCRIBE = "SUBSCRIBE"
    WATCH_MORE = "WATCH_MORE"
    GET_DIRECTIONS = "GET_DIRECTIONS"
    CALL_NOW = "CALL_NOW"
    MESSAGE_PAGE = "MESSAGE_PAGE"
    SEND_MESSAGE = "SEND_MESSAGE"
    ORDER_NOW = "ORDER_NOW"
    ADD_TO_CART = "ADD_TO_CART"
    INSTALL_MOBILE_APP = "INSTALL_MOBILE_APP"
    USE_MOBILE_APP = "USE_MOBILE_APP"
    PLAY_GAME = "PLAY_GAME"
    OPEN_LINK = "OPEN_LINK"
    BUY_NOW = "BUY_NOW"
    BUY_TICKETS = "BUY_TICKETS"
    DONATE_NOW = "DONATE_NOW"
    GET_STARTED = "GET_STARTED"
    LISTEN_NOW = "LISTEN_NOW"
    LISTEN_MUSIC = "LISTEN_MUSIC"
    SAVE = "SAVE"
    SEE_MENU = "SEE_MENU"
    SEND_WHATSAPP_MESSAGE = "SEND_WHATSAPP_MESSAGE"
    GET_SHOWTIMES = "GET_SHOWTIMES"
    FIND_A_GROUP = "FIND_A_GROUP"
    REQUEST_TIME = "REQUEST_TIME"
    SEE_MORE = "SEE_MORE"
    EVENT_RSVP = "EVENT_RSVP"
    WHATSAPP_MESSAGE = "WHATSAPP_MESSAGE"
    PAY_TO_ACCESS = "PAY_TO_ACCESS"


class SpecialAdCategory(str, Enum):
    NONE = "NONE"
    HOUSING = "HOUSING"
    EMPLOYMENT = "EMPLOYMENT"
    CREDIT = "CREDIT"
    ISSUES_ELECTIONS_POLITICS = "ISSUES_ELECTIONS_POLITICS"
    ONLINE_GAMBLING_AND_GAMING = "ONLINE_GAMBLING_AND_GAMING"
    FINANCIAL_PRODUCTS_SERVICES = "FINANCIAL_PRODUCTS_SERVICES"


class PixelEvent(str, Enum):
    """Standard Meta Pixel / Conversions API event types for custom_event_type."""
    ADD_PAYMENT_INFO = "ADD_PAYMENT_INFO"
    ADD_TO_CART = "ADD_TO_CART"
    ADD_TO_WISHLIST = "ADD_TO_WISHLIST"
    COMPLETE_REGISTRATION = "COMPLETE_REGISTRATION"
    CONTACT = "CONTACT"
    CUSTOMIZE_PRODUCT = "CUSTOMIZE_PRODUCT"
    DONATE = "DONATE"
    FIND_LOCATION = "FIND_LOCATION"
    INITIATE_CHECKOUT = "INITIATE_CHECKOUT"
    LEAD = "LEAD"
    PURCHASE = "PURCHASE"
    SCHEDULE = "SCHEDULE"
    SEARCH = "SEARCH"
    START_TRIAL = "START_TRIAL"
    SUBMIT_APPLICATION = "SUBMIT_APPLICATION"
    SUBSCRIBE = "SUBSCRIBE"
    VIEW_CONTENT = "VIEW_CONTENT"
    OTHER = "OTHER"
