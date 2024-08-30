import requests, os, zipfile
from urllib.parse import urljoin
from bs4 import BeautifulSoup, element
from dataclasses import dataclass, asdict

# 国土数値情報ダウンロードサイト


class TopInfo:
    def __init__(self) -> None:
        url = "https://nlftp.mlit.go.jp/ksj/index.html"

        # get html
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to access page: {url} {response.status_code}")
            return {}
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        # get categories
        main_tag = soup.find("main")
        collapsibles: list[element.Tag] = main_tag.find_all(class_="collapsible")

        data: dict[str, dict[str, list[tuple[str, str]]]] = {}
        for collapsible in collapsibles:

            header = collapsible.find("div", class_="collapsible-header")
            # without children
            category_name = "".join([str(item) for item in header.find("p").contents if isinstance(item, str)]).strip()

            body = collapsible.find("div", class_="collapsible-body")
            sub_category = body.find("div", class_="paddingAll")
            if sub_category is None:
                break

            sub_data: dict[str, list[tuple[str, str]]] = {}
            while True:
                sub_category_name = sub_category.find("span").text.strip()

                sub_category_top = sub_category.find_next("div", class_="row")
                sub_sub_categories: list[element.Tag] = sub_category_top.find_all("a")

                # actual urls
                sub_sub_data: list[tuple[str, str]] = []
                for sub_sub_category in sub_sub_categories:
                    item_name = sub_sub_category.text.strip()
                    item_url = sub_sub_category["href"]
                    sub_sub_data.append((item_name, urljoin(url, item_url)))
                sub_data[sub_category_name] = sub_sub_data

                sub_category = sub_category.find_next("div", class_="paddingAll")
                if sub_category is None:
                    break

            data[category_name] = sub_data

        # {category, {sub_category, [(name, url)]}}
        self._data = data

    def get_category_names(self) -> list[str]:
        return list(self._data.keys())

    def get_sub_category_names(self, category_name: str) -> list[str]:
        if not category_name in self._data:
            print("category_name not found: ", category_name)
            return []

        return list(self._data[category_name].keys())

    def get_items(self, category_name: str, sub_category_name: str) -> list[tuple[str, str]]:
        if not sub_category_name in self.get_sub_category_names(category_name):
            print("sub_category_name not found: ", sub_category_name)
            return []

        return self._data[category_name][sub_category_name]


@dataclass
class AdministrativeDivision:
    prec_name: str
    shp_path: str


class AdministrativeDivisionInfo:

    @dataclass
    class ZipFileInfo:
        prec_name: str
        url: str
        date_str: str
        size_str: str
        filename: str

    def _get_zip_url(self, data_str: str) -> str:
        values = data_str.split(",")

        # 各変数に対応する値を割り当て
        size_str = values[0].strip().strip("'")
        filename = values[1].strip().strip("'")
        url = values[2].strip().strip("'")

        return url

    def _parse_prefecture_urls(self, url) -> dict[str, ZipFileInfo]:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to access page: {url} {response.status_code}")
            return {}
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        # table
        main = soup.find("main")
        jmap = main.find(id="Jmap")
        table = jmap.find_next_sibling("table", class_="responsive-table")

        trs: list[element.Tag] = table.find_all("tr")
        trs_len = len(trs)
        zip_files: dict[str, list[self.ZipFileInfo]] = {}
        for i in range(1, trs_len):
            tds: list[element.Tag] = trs[i].find_all("td")
            tds_len = len(tds)
            if tds_len != 6:
                # print("tds_len mismatched!")
                continue

            prec_name = tds[0].text
            proj = tds[1].text
            date_str = tds[2].text
            size_str = tds[3].text
            filename = tds[4].text

            button = tds[5].find("a")
            if not button.has_attr("onclick"):
                print("onclick doesn't exist!")
                continue

            # url from javascript source
            onclick = button["onclick"]
            start_index = onclick.find("DownLd(") + len("DownLd(")
            end_index = onclick.find(");", start_index)
            data_str = onclick[start_index:end_index]
            zip_url = urljoin(url, self._get_zip_url(data_str))

            # insert
            zip_files[prec_name] = self.ZipFileInfo(prec_name, zip_url, date_str, size_str, filename)

        return zip_files

    def __init__(self, download_dir: str, workspace_dir: str) -> None:

        self._download_dir = download_dir
        self._workspace_dir = workspace_dir

        top_info = TopInfo()
        category_names = top_info.get_category_names()
        sub_category_names = top_info.get_sub_category_names(category_names[1])
        items = top_info.get_items(category_names[1], sub_category_names[0])
        name, url = items[0]

        self._zip_files = self._parse_prefecture_urls(url)

    def get_prec_names(self) -> list[str]:
        return list(self._zip_files.keys())

    def _download_file(self, zip_info: ZipFileInfo, save_path: str) -> bool:

        if os.path.exists(save_path):
            print("zip file already exists")
            return True

        print("start downloading file: " + zip_info.filename + ": " + zip_info.size_str)

        response = requests.get(zip_info.url)
        if response.status_code != 200:
            print("failed to download: ", zip_info.url)
            return False

        with open(save_path, "wb") as f:
            f.write(response.content)

        return True

    def _extract_file(self, zip_path: str, extract_path: str) -> bool:

        if not os.path.exists(zip_path):
            print("zip file doesn't exist: " + zip_path)
            return False

        with zipfile.ZipFile(zip_path, "r") as zip:
            zip.extractall(extract_path)
        return True

    def _find_files_in_dir(self, directory: str, extension: str):
        matches = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith(extension):
                    matches.append(os.path.join(root, file))
        return matches

    def get_administrative_division(self, prec_name: str) -> AdministrativeDivision:
        if not prec_name in self._zip_files:
            print("prec_name not found: " + prec_name)
            return ""

        zip_file_info = self._zip_files[prec_name]

        directory_name = os.path.splitext(zip_file_info.filename)[0]
        target_path = os.path.join(self._workspace_dir, directory_name)

        if not os.path.exists(target_path):
            zip_download_path = os.path.join(self._download_dir, zip_file_info.filename)

            if not self._download_file(zip_file_info, zip_download_path):
                return None

            if not self._extract_file(zip_download_path, target_path):
                return None

        # target to shp
        shp_paths = self._find_files_in_dir(target_path, ".shp")
        if len(shp_paths) == 0:
            print("doesn't contain shp file: " + target_path)

        return AdministrativeDivision(prec_name, shp_paths[0])


def test():
    top_info = TopInfo()

    category_names = top_info.get_category_names()
    print(category_names)
    sub_category_names = top_info.get_sub_category_names(category_names[1])
    print(sub_category_names)

    items = top_info.get_items(category_names[1], sub_category_names[0])
    for name, url in items:
        print(name + ": " + url)


# test()


def test2():
    info = AdministrativeDivisionInfo("download", "workspace")

    prec_names = info.get_prec_names()
    target_prec_name = ""
    for prec_name in prec_names:
        if "愛知" in prec_name:
            target_prec_name = prec_name
            break

    ad = info.get_administrative_division(target_prec_name)
    print(ad.prec_name)
    print(ad.shp_path)


# test2()
