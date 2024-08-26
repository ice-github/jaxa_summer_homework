import os, requests, json
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup, element


@dataclass
class AmedasStation:
    as_type: str
    prec_no: int
    block_no: int
    is_valid: bool
    has_temperature: bool
    lon: float
    lat: float


class AmedasStationJson:

    @staticmethod
    def save_to_json(data, filename):
        def convert_to_dict(obj):
            if isinstance(obj, dict):
                return {k: convert_to_dict(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_dict(v) for v in obj]
            elif hasattr(obj, "__dataclass_fields__"):
                return asdict(obj)
            else:
                return obj

        converted_data = convert_to_dict(data)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(converted_data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def load_from_json(filename):
        def convert_to_dataclass(obj):
            if isinstance(obj, dict):
                if all(
                    key in obj
                    # AmedasStation properties
                    for key in [
                        "prec_no",
                        "block_no",
                        "is_valid",
                        "has_temperature",
                        "lon",
                        "lat",
                    ]
                ):
                    return AmedasStation(**obj)
                else:
                    return {k: convert_to_dataclass(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_dataclass(v) for v in obj]
            return obj

        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        return convert_to_dataclass(data)


class AmedasStationInfo:

    def _assign_values(self, data_str: str):
        # カンマで区切られた値をリストとして取得
        values = data_str.split(",")

        # 各変数に対応する値を割り当て
        as_ = values[0].strip("'")
        bk_no = values[1].strip("'")
        ch = values[2].strip("'")
        ch_kn = values[3].strip("'")
        lat_d = values[4].strip("'")
        lat_m = values[5].strip("'")
        lon_d = values[6].strip("'")
        lon_m = values[7].strip("'")
        height = values[8].strip("'")
        f_pre = values[9].strip("'")
        f_wsp = values[10].strip("'")
        f_tem = values[11].strip("'")
        f_sun = values[12].strip("'")
        f_snc = values[13].strip("'")
        f_hum = values[14].strip("'")
        ed_y = values[15].strip("'")
        ed_m = values[16].strip("'")
        ed_d = values[17].strip("'")
        bikou1 = values[18].strip("'")
        bikou2 = values[19].strip("'")
        bikou3 = values[20].strip("'")
        bikou4 = values[21].strip("'")
        bikou5 = values[22].strip("'")

        # 値をタプルとして返す
        return (as_, bk_no, ch, ch_kn, lat_d, lat_m, lon_d, lon_m, height, f_pre, f_wsp, f_tem, f_sun, f_snc, f_hum, ed_y, ed_m, ed_d, bikou1, bikou2, bikou3, bikou4, bikou5)

    def _get_all_prec_no(self) -> dict[str, int]:

        # get page
        url = "https://www.data.jma.go.jp/obd/stats/etrn/select/prefecture00.php"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to access page: {url} {response.status_code}")
            return {}
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        # areas
        div_main = soup.find("div", id="main")
        map_point = div_main.find("map", {"name": "point"})
        areas = map_point.find_all("area")

        all_prec_no = {}
        for area in areas:
            prec_name: str = area.get("alt")
            href: str = area.get("href")
            start_index = href.find("prec_no=") + len("prec_no=")
            end_index = href.find("&", start_index)
            prec_no_str = href[start_index:end_index]
            prec_no = int(prec_no_str)
            all_prec_no[prec_name] = prec_no

        return all_prec_no

    def _get_all_block_no(self, prec_no: int) -> dict[str, AmedasStation]:

        url = f"https://www.data.jma.go.jp/obd/stats/etrn/select/prefecture.php?prec_no={prec_no}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to access page: {url} {response.status_code}")
            return {}
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        # areas
        div_main = soup.find("div", id="contents_area2")
        map_point = div_main.find("map", {"name": "point"})
        areas = map_point.find_all("area")

        all_block_no = {}
        for area in areas:
            if not area.has_attr("onmouseover"):
                continue
            onmouseover_str: str = area["onmouseover"]

            start_index = onmouseover_str.find("viewPoint(") + len("viewPoint(")
            end_index = onmouseover_str.find(");", start_index)
            data_str = onmouseover_str[start_index:end_index]

            as_, bk_no, ch, ch_kn, lat_d, lat_m, lon_d, lon_m, height, f_pre, f_wsp, f_tem, f_sun, f_snc, f_hum, ed_y, ed_m, ed_d, bikou1, bikou2, bikou3, bikou4, bikou5 = self._assign_values(
                data_str
            )

            as_type = as_
            block_no = int(bk_no)
            name = ch
            lat = float(lat_d) + float(lat_m) / 60
            lon = float(lon_d) + float(lon_m) / 60
            att = height
            has_temp = int(f_tem) == 1
            is_valid = int(ed_y) == 9999

            all_block_no[name] = AmedasStation(as_type, prec_no, block_no, is_valid, has_temp, lon, lat)

        return all_block_no

    def __init__(self, workspace: str) -> None:

        self._prec_block_json_path = os.path.join(workspace, "prec_block.json")

        if not os.path.exists(self._prec_block_json_path):
            # parse
            self._data: dict[str, dict[str, AmedasStation]] = {}
            prec_nos = self._get_all_prec_no()
            for prec_name, prec_no in prec_nos.items():
                blocks = self._get_all_block_no(prec_no)
                self._data[prec_name] = blocks
                print(blocks)

            # save as json
            AmedasStationJson.save_to_json(self._data, self._prec_block_json_path)

        else:
            self._data = AmedasStationJson.load_from_json(self._prec_block_json_path)
            # print(self._data)

    def get_amedas_stations(self, prec_name: str) -> dict[str, AmedasStation]:
        if not prec_name in self._data:
            raise Exception("couldn't find prec_name")

        return self._data[prec_name]

    def get_amedas_station(self, prec_name: str, block_name: str) -> AmedasStation:
        blocks = self.get_amedas_stations(prec_name)

        if not block_name in blocks:
            raise Exception("couldn't find block_name")

        return blocks[block_name]


@dataclass
class AmedasDaily:
    pass


class AmedasDailyInfo:

    def _get_table_headings(self, headings: list[element.Tag]) -> list[str]:
        # check heading level
        def check_heading_level(heading: element.Tag) -> int:
            time_head = heading.find("th")
            level = 1
            if time_head.has_attr("rowspan"):
                level = int(time_head["rowspan"])
            return level

        # check if level mismatched
        level = check_heading_level(headings[0])
        if level != len(headings):
            raise Exception("level and heading mismatched!")

        # construct headings per level
        level_headings: list[list[dict]] = []
        for i in range(level):
            level_heading = []
            for th in headings[i].find_all("th"):
                item = {}
                item["text"] = th.text
                item_len = 1
                if th.has_attr("colspan"):
                    item_len = int(th["colspan"])
                item["len"] = item_len
                item["used"] = False
                level_heading.append(item)
            level_headings.append(level_heading)

        def get_heading_items(level_headings: list[list[dict]], level: int, count: int) -> list[str]:

            result: list[str] = []
            for item in level_headings[level]:
                if item["used"]:
                    continue
                item_len = item["len"]
                if item_len == 1:
                    result.append(item["text"])
                else:
                    sub_items = get_heading_items(level_headings, level + 1, item_len)
                    for sub_item in sub_items:
                        result.append(item["text"] + "-" + sub_item)
                item["used"] = True
                if len(result) == count:
                    break

            return result

        total_len = 0
        for item in level_headings[0]:
            total_len += item["len"]

        table_headings = get_heading_items(level_headings, 0, total_len)
        # print(table_headings)
        return table_headings

    def get_amedas_daily(self, as_type: str, prec_no: int, block_no: int, year: int, month: int, day: int):

        url = f"https://www.data.jma.go.jp/obd/stats/etrn/view/10min_{as_type}1.php?prec_no={prec_no}&block_no={block_no}&year={year}&month={month}&day={day}&view="

        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to access page: {url} {response.status_code}")
            return {}
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, "html.parser")

        # areas
        div_main = soup.find("div", id="main")
        table = div_main.find("table", id="tablefix1")
        trs = table.find_all("tr")

        # obtain headings and lines
        headings: list[element.Tag] = []
        lines: list[element.Tag] = []
        for tr in trs:
            if not tr.has_attr("style"):
                headings.append(tr)
            else:
                lines.append(tr)

        self._table_headings = self._get_table_headings(headings)

        print(self._table_headings)


def test():

    amedas = AmedasStationInfo("workspace")

    oobu = amedas.get_amedas_station("愛知県", "大府")
    nagoya = amedas.get_amedas_station("愛知県", "名古屋")

    daily = AmedasDailyInfo()
    daily.get_amedas_daily(oobu.as_type, oobu.prec_no, oobu.block_no, 2024, 8, 1)
    daily.get_amedas_daily(nagoya.as_type, nagoya.prec_no, nagoya.block_no, 2024, 8, 1)


test()
