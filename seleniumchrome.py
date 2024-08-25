import os, requests, zipfile, time
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


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

        # chmod
        os.chmod(self.get_chromedriver_path(), 0o777)
        os.chmod(self.get_chrome_path(), 0o777)

        return True


class SeleniumChromeWrapper:

    def _prepare(self, download_dir: str, workspace_dir: str) -> tuple[str, str]:
        dl = ChromeDownloader(download_dir)

        if not dl.download():
            raise Exception("couldn't download files")

        ex = ChromeExtractor(workspace_dir)
        if not ex.extract(dl.get_chromedriver_zip_path(), dl.get_chrome_zip_path()):
            raise Exception("could'n extract files")

        return ex.get_chromedriver_path(), ex.get_chrome_path()

    def __init__(self, download_dir: str, workspace_dir: str) -> None:

        chromedriver_dir, chrome_dir = self._prepare(download_dir, workspace_dir)

        self._download_path = download_dir
        self._chromedriver_path = os.path.join(chromedriver_dir, "chromedriver")
        self._chrome_path = os.path.join(chrome_dir, "chrome")

        # chmod
        os.chmod(self._chromedriver_path, 0o777)
        os.chmod(self._chrome_path, 0o777)

    def get_driver(self) -> webdriver.Chrome:

        # options
        chrome_options = Options()
        chrome_options.binary_location = self._chrome_path
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_settings.popups": 0,
                "download.default_directory": os.path.abspath(self._download_path),
                "safebrowsing.enabled": True,
            },
        )

        # webdriver
        service = Service(executable_path=self._chromedriver_path)

        # instance
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver

    def _get_filename_from_url(self, url: str) -> str:
        filename = url.split("/")[-1]
        return filename

    def download_sync(self, driver: webdriver.Chrome, url) -> str:

        # target path
        filename = self._get_filename_from_url(url)
        path = os.path.join(self._download_path, filename)

        if os.path.exists(path):
            print("file already exists: ", path)
            return path

        # download
        driver.get(url)
        print("start downloading: ", url)

        # check if file exists
        while not os.path.exists(path):
            time.sleep(1)
        time.sleep(1)

        return path


def test():

    dl = ChromeDownloader("download")
    print("download: ", dl.download())

    ex = ChromeExtractor("workspace")
    print("extract: ", ex.extract(dl.get_chromedriver_zip_path(), dl.get_chrome_zip_path()))


# test()


def test2():

    url = "https://storage.googleapis.com/chrome-for-testing-public/128.0.6613.84/mac-arm64/chromedriver-mac-arm64.zip"

    wrapper = SeleniumChromeWrapper("download", "workspace")
    driver = wrapper.get_driver()
    downloaded_path = wrapper.download_sync(driver, url)
    print("finished: ", downloaded_path)


# test2()
