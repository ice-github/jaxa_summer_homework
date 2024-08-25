import os
import requests
from urllib import request
from bs4 import BeautifulSoup
import zipfile


class ChromeDownloader:
    def __init__(self, download_dir: str) -> None:

        # prepare workspace
        os.makedirs(name=download_dir, exist_ok=True)

        # set properties
        self._download_dir = download_dir
        self._chrome_labs_url = "https://googlechromelabs.github.io/chrome-for-testing/"
        self._chromedriver_zip_filename = "chromedriver-linux64.zip"
        self._chrome_zip_filename = "chrome-linux64.zip"

    def _get_chromedriver_zip_url(self, soup: BeautifulSoup) -> str:
        stable = soup.find(id="stable")
        code_texts: list[str] = [code_tag.text for code_tag in stable.find_all("code")]

        url = ""
        for code_text in code_texts:
            if self._chromedriver_zip_filename in code_text:
                url = code_text
                break

        return url

    def _get_chrome_zip_url(self, soup: BeautifulSoup) -> str:
        stable = soup.find(id="stable")
        code_texts: list[str] = [code_tag.text for code_tag in stable.find_all("code")]

        url = ""
        for code_text in code_texts:
            if self._chrome_zip_filename in code_text:
                url = code_text
                break

        return url

    def _get_chrome_labs_page(self) -> BeautifulSoup:
        response = requests.get(self._chrome_labs_url)

        if response.status_code != 200:
            print(f"Failed to access page: {self._chrome_labs_url} {response.status_code}")
            return

        soup = BeautifulSoup(response.text, "html.parser")
        return soup

    def _get_filename_from_url(self, url: str) -> str:
        filename = url.split("/")[-1]
        return filename

    def _download_file(self, url: str, save_path: str) -> bool:

        if os.path.exists(save_path):
            print("already exists: ", save_path)
            return True

        response = requests.get(url)
        if response.status_code != 200:
            print("failed to download: ", url)
            return False

        with open(save_path, "wb") as f:
            f.write(response.content)

        return True

    def get_chromedriver_zip_path(self) -> str:
        return os.path.join(self._download_dir, self._chromedriver_zip_filename)

    def get_chrome_zip_path(self) -> str:
        return os.path.join(self._download_dir, self._chrome_zip_filename)

    def download(self) -> bool:

        # parse page
        soup = self._get_chrome_labs_page()
        chromedriver_zip_url = self._get_chromedriver_zip_url(soup)
        chrome_zip_url = self._get_chrome_zip_url(soup)

        if len(chromedriver_zip_url) == 0:
            print("failed to get chromedriver zip url!")
            return False

        if len(chrome_zip_url) == 0:
            print("failed to get chrome zip url!")
            return False

        # download
        if not self._download_file(chromedriver_zip_url, self.get_chromedriver_zip_path()):
            return False

        if not self._download_file(chrome_zip_url, self.get_chrome_zip_path()):
            return False

        return True


class ChromeExtractor:
    def __init__(self, workspace_path: str) -> None:
        self._workspace_path = workspace_path
        self._chromedriver_path = "chromedriver-linux64"
        self._chrome_path = "chrome-linux64"

    def get_chromedriver_path(self) -> str:
        return os.path.join(self._workspace_path, self._chromedriver_path)

    def get_chrome_path(self) -> str:
        return os.path.join(self._workspace_path, self._chrome_path)

    def extract(self, chromedriver_zip_path, chrome_zip_path) -> bool:

        # check if chromedriver zip exists
        if not os.path.exists(chromedriver_zip_path):
            print("file not found: ", chromedriver_zip_path)
            return False

        # check if chrome zip exists
        if not os.path.exists(chrome_zip_path):
            print("file not found: ", chrome_zip_path)
            return False

        # chrome driver
        if os.path.exists(self.get_chromedriver_path()):
            print("already exists: ", self.get_chromedriver_path())
        else:
            with zipfile.ZipFile(chromedriver_zip_path, "r") as zip:
                zip.extractall(self._workspace_path)

        # chrome
        if os.path.exists(self.get_chrome_path()):
            print("already exists: ", self.get_chrome_path())
        else:
            with zipfile.ZipFile(chrome_zip_path, "r") as zip:
                zip.extractall(self._workspace_path)

        return True


def test():

    dl = ChromeDownloader("download")
    print("download: ", dl.download())

    ex = ChromeExtractor("workspace")
    print("extract: ", ex.extract(dl.get_chromedriver_zip_path(), dl.get_chrome_zip_path()))


# test()
