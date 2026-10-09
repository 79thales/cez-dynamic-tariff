"""Traffic-light presentation, independent of prices and automation states."""

BAND_SYMBOLS = {
    "super_cheap": "🟢",
    "cheap": "⚪",
    "normal": "🔘",
    "expensive": "🟠",
    "very_expensive": "🔴",
}
BAND_COLORS = {
    "super_cheap": "green",
    "cheap": "white",
    "normal": "gray",
    "expensive": "orange",
    "very_expensive": "red",
}


def band_presentation(level):
    return {"display_token": BAND_SYMBOLS[level], "color": BAND_COLORS[level]}


def traffic_light_map(schedule):
    return " ".join(
        f"`{row.get('display_token', row['token'])} {row['start']}–{row['end']} "
        f"({row['modifier_percent']:+d} %)`"
        for row in schedule
    )
