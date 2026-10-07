from dataclasses import dataclass
from sqlite3 import Cursor, connect
from typing import Any, cast

from requests import Response, Session


@dataclass
class Event:
    name: str
    lat: float
    lon: float


def populate_db() -> None:
    response_data: dict[str, Any] = _request_data()
    events: list[Event] = _parse_data(response_data)

    # Now add events to the database.
    with connect("ParkrunEventData.sqlite") as con:
        cur: Cursor = con.cursor()

        for event in events:
            res: Cursor = cur.execute(f"SELECT * FROM Events WHERE Name IS \"{event.name}\" LIMIT 1")
            data: Any | None = res.fetchone()
            if not data:
                # This is a new entry so add it to the database. As we are reading
                # it directly from parkrun.com we can assume it is an active event.
                res = cur.execute(f"INSERT INTO Events(Name,Lat,Lon,Active) VALUES(\"{event.name}\",{event.lat},{event.lon},1)")

        con.commit()


def _parse_data(data: dict[str, Any]) -> list[Event]:
    events: list[Event] = []

    for feature in data["events"]["features"]:
        name: str = feature["properties"]["EventShortName"]
        lat: float = feature["geometry"]["coordinates"][1]
        lon: float = feature["geometry"]["coordinates"][0]

        events.append(Event(name, lat, lon))

    return events


def _request_data() -> dict[str, Any]:
    with Session() as session:
        session.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:93.0) Gecko/20100101 Firefox/93.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

        url: str = "https://images.parkrun.com/events.json"

        print(f"Requesting data from {url}")

        response: Response = session.get(url=url, timeout=10)
        response.raise_for_status()

        response.encoding = "utf-8"

        return cast(dict[str, Any], response.json())


if __name__ == "__main__":
    populate_db()
