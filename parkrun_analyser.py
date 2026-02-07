from io import StringIO

import pandas as pd
from pandas import DataFrame

import plotly.express as px
from plotly.graph_objects import Figure

from requests import Response, Session


def analyse_results(athlete_id: str) -> None:
    print(f"Anaylsing Parkrun athlete {athlete_id}")

    response: Response = _request_results_page(athlete_id)

    if response.status_code != 200:
        if response.status_code == 202:
            raise RuntimeError("Load page manually and try again")
        else:
            raise RuntimeError(f"Failed to load page, error code: {response.status_code}")

    data_frame: DataFrame = _parse_results_page(response.text)

    print(f"Parsed {len(data_frame)} results")

    print("Generating graph")

    _generate_graph(data_frame)


def _generate_graph(data_frame: DataFrame) -> None:
    fig: Figure = px.line(data_frame, x="Run Date", y="time_seconds", title="Parkrun results")
    fig.update_layout(xaxis_title="Date", yaxis_title="Time (minute:seconds)")

    # Update the y axis to show the time in mm:ss format.
    fig.update_yaxes(tickvals=data_frame["time_seconds"], ticktext=[f"{v//60:02d}:{v % 60:02d}" for v in data_frame["time_seconds"]])

    output_file_name: str = "results.html"

    print(f"Writing output to {output_file_name}")

    fig.write_html(output_file_name)


def _normalise_time_string(time_str: str) -> str:
    # Check if the string only has one colon.
    if time_str.count(':') == 1:
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
            "Sec-Fetch-User": "?1"
        }

        url: str = f"https://www.parkrun.org.uk/parkrunner/{athlete_id}/all/"

        print(f"Requesting data from {url}")

        response: Response = session.get(url=url, timeout=10)
        response.raise_for_status()

        return response


def _parse_results_page(page_contents: str) -> pd.DataFrame:
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
    results_df["time_seconds"] = pd.to_timedelta(results_df["Time"].apply(_normalise_time_string)).dt.total_seconds().astype(int)

    return results_df[["Event", "Run Date", "time_seconds"]]


if __name__ == "__main__":
    from argparse import ArgumentParser, Namespace

    parser: ArgumentParser = ArgumentParser(
                    prog='Parkrun analyser',
                    description='Analyser a Parkrun athletes results')

    parser.add_argument("--athlete_id", required=True, help="The Parkrun athlete's ID number")

    args: Namespace = parser.parse_args()

    analyse_results(args.athlete_id)
