import sqlite3
from io import StringIO
from sqlite3 import Cursor
from typing import Any

from bs4 import BeautifulSoup

from folium import Element, Icon, Map, Marker

import pandas as pd
from pandas import DataFrame

from plotly.graph_objects import Figure, Scatter

from requests import Response, Session


def analyse_results(athlete_id: str) -> None:
    print(f"Anaylsing Parkrun athlete {athlete_id}")

    athlete_name, data_frame = _get_athlete_data(athlete_id)

    print(f"Parsed {len(data_frame)} results")

    print("Generating graph")

    _generate_graph(data_frame, athlete_id, athlete_name)


def generate_map(athlete_id: str) -> None:
    print(f"Generating map for Parkrun athlete {athlete_id}")

    athlete_name, data_frame = _get_athlete_data(athlete_id)

    events: pd.arrays.StringArray = data_frame['Event'].unique()

    map = Map(location=(30, 10), zoom_start=3, tiles="cartodb positron")

    title_html: str = f"<h3 align=\"center\" style=\"font-size:16px\"><b>{athlete_name}'s Parkruns</b></h3>"
    map.get_root().html.add_child(Element(title_html))

    with sqlite3.connect("ParkrunEventData.sqlite") as con:
        cur: Cursor = con.cursor()

        for event in events:
            location_data: tuple[float, float] | None = _get_event_location(cur, event)

            if not location_data:
                print(f"Failed to find location for event: {event}")
                continue

            Marker(
                    location=[location_data[0], location_data[1]],
                    popup=event,
                    icon=Icon(color="blue")
                ).add_to(map)

    output_file_name: str = f"{athlete_id}-map.html"

    print(f"Writing output to {output_file_name}")

    map.save(output_file_name)


def _generate_graph(data_frame: DataFrame, athlete_id: str, athlete_name: str) -> None:
    pb_time: int = data_frame["time_seconds"].min()

    # Build arrays for conditional styling
    symbols: list[str] = ["circle" if v != pb_time else "star" for v in data_frame["time_seconds"]]
    sizes: list[int] = [8 if v != pb_time else 18 for v in data_frame["time_seconds"]]
    colors: list[str] = ["blue" if v != pb_time else "red" for v in data_frame["time_seconds"]]

    figure: Figure = Figure()

    # Add a trace for the overall results.
    figure.add_trace(
        Scatter(
            x=data_frame["Run Date"],
            y=data_frame["time_seconds"],
            mode="lines+markers",
            marker={"symbol": symbols, "size": sizes, "color": colors},
            customdata=data_frame[["Event"]],
            name="Total",
            visible=True,
            hovertemplate=(
                "Run Date: %{x|%d/%m/%y}<br>"
                "Time: %{y}<br>"
                "Event: %{customdata[0]}<br>"
                "<extra></extra>"
            ),
        )
    )

    # Add a trace for each event.
    for event, group in data_frame.groupby("Event"):
        figure.add_trace(
            Scatter(
                x=group["Run Date"],
                y=group["time_seconds"],
                mode="lines",
                name=event,
                visible="legendonly",
            )
        )

    figure.update_layout(
        title=f"{athlete_name}'s Parkrun results",
        xaxis_title="Date",
        yaxis_title="Time (minute:seconds)",
    )

    # Add a tick on the Y axis for each time interval.
    figure.update_yaxes(
        tickvals=data_frame["time_seconds"],
        ticktext=[f"{v//60:02d}:{v % 60:02d}" for v in data_frame["time_seconds"]],
    )

    output_file_name: str = f"{athlete_id}-results.html"

    print(f"Writing output to {output_file_name}")

    figure.write_html(output_file_name)


def _get_athlete_data(athlete_id: str) -> tuple[str, DataFrame]:
    response: Response = _request_results_page(athlete_id)

    if response.status_code != 200:
        if response.status_code == 202:
            raise RuntimeError("Load page manually and try again")
        else:
            raise RuntimeError(
                f"Failed to load page, error code: {response.status_code}"
            )

    return _parse_results_page(response.text)


def _get_event_location(cur: Cursor, event: str) -> tuple[float, float] | None:
    res = cur.execute(f"SELECT Lat,Lon FROM Events WHERE Name IS \"{event}\" LIMIT 1")
    location_data: tuple[str, str] | None = res.fetchone()
    locations: tuple[float, float] | None = None

    if location_data:
        locations = (float(location_data[0]), float(location_data[1]))

    return locations


def _normalise_time_string(time_str: str) -> str:
    # Check if the string only has one colon.
    if time_str.count(":") == 1:
        # Append 00: to string to add hour value.
        time_str = "00:" + time_str

    return time_str


def _request_results_page(athlete_id: str) -> Response:
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

        # Note that the athlete URL doesn't include the leading 'A' from the athlete ID.
        url: str = f"https://www.parkrun.org.uk/parkrunner/{athlete_id[1:]}/all/"

        print(f"Requesting data from {url}")

        response: Response = session.get(url=url, timeout=10)
        response.raise_for_status()

        return response


def _parse_results_page(page_contents: str) -> tuple[str, DataFrame]:
    # Read the html of the page to get the athlete's name.
    bs_page_contents: BeautifulSoup = BeautifulSoup(page_contents, "html.parser")
    header: Any = bs_page_contents.find("h2")
    athlete_name: str = header.find(string=True, recursive=False).strip().title()

    # Convert the page contents to a file like object for pandas to read.
    buffer: StringIO = StringIO(page_contents)

    tables: list[DataFrame] = pd.read_html(buffer)

    for df in tables:
        if {"Event", "Run Date", "Time"}.issubset(df.columns):
            results_df = df
            break
    else:
        raise RuntimeError("Could not find results table")

    # By default the data in the DataFrame will be strings so convert data to
    # types as required.
    results_df["Run Date"] = pd.to_datetime(results_df["Run Date"], format="%d/%m/%Y")

    # Convert time to seconds as timedelta can't be used in plotly
    results_df["time_seconds"] = (
        pd.to_timedelta(results_df["Time"].apply(_normalise_time_string))
        .dt.total_seconds()
        .astype(int)
    )

    return (athlete_name, results_df[["Event", "Run Date", "time_seconds"]])


def _validate_athlete_id(athlete_id: str) -> None:
    # First check that the ID starts with the letter A.
    if not athlete_id[0] == "A" and not athlete_id[0] == "a":
        raise RuntimeError("Athlete ID must start with the letter A")

    # Make sure the ID is either 8 or 9 characters long.
    if len(athlete_id) < 8 or len(athlete_id) > 9:
        raise RuntimeError("Athlete ID must be 8 or 9 characters long")

    # Make sure the ID after the 'A' is all numbers.
    if not athlete_id[1:].isnumeric():
        raise RuntimeError("Athlete ID must be all numbers after the starting 'A'")


if __name__ == "__main__":
    from argparse import ArgumentParser, Namespace

    parser: ArgumentParser = ArgumentParser(
        prog="Parkrun analyser", description="Analyser a Parkrun athletes results"
    )

    parser.add_argument(
        "--athlete_id", required=True, help="The Parkrun athlete's ID number"
    )
    parser.add_argument("--map", action='store_true', help="Generate map of Parkrun locations")

    args: Namespace = parser.parse_args()

    _validate_athlete_id(args.athlete_id)

    if args.map:
        generate_map(args.athlete_id)
    else:
        analyse_results(args.athlete_id)
