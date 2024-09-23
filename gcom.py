import os, requests, time, json
from urllib.parse import urlencode
from datetime import datetime, timezone, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By


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


class JPortalLogin:
    def __init__(self) -> None:
        self._login_url = "https://gportal.jaxa.jp/gpr/auth?"

    def login(self, driver: webdriver.Chrome, username: str, password: str) -> bool:

        driver.get(self._login_url)

        # input username
        user_input = driver.find_element("id", "auth_account")
        user_input.send_keys(username)

        # input password
        password_input = driver.find_element("id", "auth_password")
        password_input.send_keys(password)

        # click button
        login_button = driver.find_element("id", "auth_login_submit")
        login_button.click()

        # wait for page transition
        time.sleep(3)

        if driver.title != "G-PortalTop":
            return False

        print("title: ", driver.title)
        return True


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

from seleniumchrome import SeleniumChromeWrapper


class GcomDownloader:

    def __init__(
        self,
        download_dir: str,
        workspace_dir: str,
        username: str,
        password: str,
    ) -> None:
        self._selenium = SeleniumChromeWrapper(download_dir, workspace_dir)
        self._driver = self._selenium.get_driver()

        login = JPortalLogin()
        if not login.login(self._driver, username, password):
            print("failed to login to jportal")

    def get_downloaded_file_paths(self, urls: list[str]) -> list[str]:

        file_paths: list[str] = []
        for url in urls:
            file_paths.append(self._selenium.download_sync(self._driver, url))

        return file_paths


def test2():

    username = "*****"
    password = "*****"
    downloader = GcomDownloader("download", "workspace", username, password)


# test2()
