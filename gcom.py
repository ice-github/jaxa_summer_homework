import os, requests, time, json
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from selenium import webdriver


class JPortalLogin:
    pass


class CSWWrapper:
    def __init__(self) -> None:
        self._base_url = "https://gportal.jaxa.jp/csw/csw"

    def _create_query_url(self, dataset_id: str, start_time: str, end_time: str, bbox: str):

        params = {
            "service": "CSW",
            "version": "3.0.0",
            "request": "GetRecords",
            "outputFormat": "application/json",
            "datasetId": dataset_id,
            "startTime": start_time,
            "endTime": end_time,
            "bbox": bbox,
        }
        encoded_query = urlencode(params)
        full_url = f"{self._base_url}?{encoded_query}"
        return full_url

    def _fetch_data(self, url) -> json:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": "Request failed with status code {}".format(response.status_code)}

    def _get_string_from_date(self, utc_date: datetime) -> str:
        formatted_date = utc_date.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        return formatted_date

    def _get_date_from_string(self, date_str: str) -> datetime:
        dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
        return dt

    def get_hdf5_urls(self, dataset_id: str, utc_start: datetime, utc_end: datetime, bbox: list[float]) -> list[str]:

        if len(bbox) != 4:
            print("error: bbox is [left-down lon, left-down, lat, right-up lon, right-up lat]")
            return ""

        # query
        start_str = self._get_string_from_date(utc_start)
        end_str = self._get_string_from_date(utc_end)
        bbox_str = ",".join(str(v) for v in bbox)
        url = self._create_query_url(dataset_id, start_str, end_str, bbox_str)

        # request
        data = self._fetch_data(url)

        # parse
        h5_urls: list[str] = []
        for feature in data["features"]:
            h5_url = feature["properties"]["product"]["fileName"]
            h5_urls.append(h5_url)

        return h5_urls


def convert_utc_to_jst(utc_date: datetime) -> datetime:

    dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    dt_jst = dt_utc.astimezone(timezone(timedelta(hours=9)))

    return dt_jst


def test():
    # https://gportal.jaxa.jp/gpr/assets/mng_upload/COMMON/upload/GCOM-C_FAQ_datasetID_jp.pdf
    dataset_id = "10002019"  # LST

    start = datetime(2021, 7, 7)
    end = datetime(2021, 7, 8)
    bbox = [130, 40, 140, 30]

    csw = CSWWrapper()
    urls = csw.get_hdf5_urls(dataset_id, start, end, bbox)

    for url in urls:
        print(url)


# test()
