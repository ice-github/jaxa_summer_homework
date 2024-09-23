import os
from datetime import datetime
from dataclasses import dataclass

from japanmeteorologicalagency import AmedasStation, AmedasStationInfo, AmedasStationJson
from japanmeteorologicalagency import AmedasDaily, AmedasDailyInfo, AmedasDailyJson
from japanmlitnlftp import AdministrativeDivision
from japanmlitnlftp import AdministrativeDivisionInfo

from qgiswrapper import QGisWrapper
from gcom import CSWWrapper, GcomDownloader
from hdf5togeotiff import GcomHdf5

from qgis.core import QgsPointXY


def gportal_username_and_password_from_env() -> tuple[str, str]:
    username = os.environ.get("GPORTAL_USERNAME")
    password = os.environ.get("GPORTAL_PASSWORD")
    return username, password


def analysis1():

    # get point from meteorological agency
    amedas_station_info = AmedasStationInfo("workspace")
    amedas_stations_in_aichi = amedas_station_info.get_amedas_stations("愛知県")

    # enumulate amedas stations as target points
    target_points: list[tuple[str, AmedasStation]] = []
    for name, station in amedas_stations_in_aichi.items():
        if not station.is_valid:
            continue
        if not station.has_temperature:
            continue
        target_points.append((name, station))

    # get aichi shp
    administrative_division_info = AdministrativeDivisionInfo("download", "workspace")
    prec_names = administrative_division_info.get_prec_names()
    aichi_prec_name = ""
    for prec_name in prec_names:
        if "愛知" in prec_name:
            aichi_prec_name = prec_name
            break
    aichi_division = administrative_division_info.get_administrative_division(aichi_prec_name)

    # get aichi extent
    qgis_wrapper = QGisWrapper()
    qgis_wrapper.add_shp(aichi_division.shp_path)
    aichi_extent = qgis_wrapper.get_shp_layers_extent()

    # get gcom hdf5 urls
    # https://gportal.jaxa.jp/gpr/assets/mng_upload/COMMON/upload/GCOM-C_FAQ_datasetID_jp.pdf
    dataset_id = str("10002019")  # LST
    utc_start = datetime(2024, 8, 1)
    utc_end = datetime(2024, 8, 3)
    bbox = [aichi_extent.xMinimum(), aichi_extent.yMaximum(), aichi_extent.xMaximum(), aichi_extent.yMinimum()]
    csw_wrapper = CSWWrapper()
    hdf5_urls = csw_wrapper.get_hdf5_urls(dataset_id, utc_start, utc_end, bbox)

    # download hdf5 files
    username, password = gportal_username_and_password_from_env()
    gcom_downloader = GcomDownloader("download", "workspace", username, password)
    hdf5_file_paths = gcom_downloader.get_downloaded_file_paths(hdf5_urls)

    # geotiff
    @dataclass
    class LSTGeoTiff:
        lst_image_path: str
        qa_flag_image_path: str
        jst_average_date: datetime

    # convert to geotiff
    geo_tiffs: list[LSTGeoTiff] = []
    for path in hdf5_file_paths:

        # filepath to extract path
        filename_without_extension = os.path.splitext(os.path.basename(path))[0]
        lst_path = os.path.join("workspace", filename_without_extension + "_LST.tif")
        qa_flag_path = os.path.join("workspace", filename_without_extension + "_QA_flag.tif")

        gcom_hdf5 = GcomHdf5(path)
        # https://suzaku.eorc.jaxa.jp/GCOM_C/data/update/Algorithm_LST_ja.html
        gcom_hdf5.get_sub_image_path("Image_data/LST", lst_path)
        gcom_hdf5.get_sub_image_path("Image_data/QA_flag", qa_flag_path)
        jst_start, jst_end = gcom_hdf5.get_jst_start_end()

        # averaging
        difference = jst_end - jst_start
        half_difference = difference / 2
        jst_average = jst_start + half_difference

        geo_tiffs.append(LSTGeoTiff(lst_path, qa_flag_path, jst_average))

    @dataclass
    class GeoTiffTargetPointsValue:
        lst_values: list[float]
        qa_flag_values: list[float]
        geotiff_date: datetime

    # apply to qgis
    geotiff_target_points_values: list[GeoTiffTargetPointsValue] = []
    for geo_tiff in geo_tiffs:
        lst_index = qgis_wrapper.add_geotiff(geo_tiff.lst_image_path)
        qa_flag_index = qgis_wrapper.add_geotiff(geo_tiff.qa_flag_image_path)

        # get values against target points
        lst_values: list[float] = []
        qa_flag_values: list[float] = []
        hit = False
        for name, station in target_points:
            point = QgsPointXY(station.lon, station.lat)
            lst_value, lst_flag = qgis_wrapper.get_geotiff_layer_value(point, lst_index)
            qa_flag_value, qa_flag_flag = qgis_wrapper.get_geotiff_layer_value(point, qa_flag_index)
            lst_values.append(lst_value if lst_flag else 0.0)
            qa_flag_values.append(qa_flag_value if qa_flag_flag else 0.0)

            if lst_flag or qa_flag_flag:
                hit = True

        # check if hitting all target points
        if not hit:
            print("no station hit" + str(geo_tiff.jst_average_date))
            continue

        geotiff_target_points_values.append(
            GeoTiffTargetPointsValue(
                lst_values,
                qa_flag_values,
                geo_tiff.jst_average_date,
            )
        )

    # get index
    def get_daily_heading_index(daily: AmedasDaily, heading_name: str) -> int:
        target_index = -1
        for index, heading in enumerate(daily.table_headings):
            if heading_name in heading:
                target_index = index
                break
        return target_index

    # get precise value
    def get_daily_hour_minute_value(daily: AmedasDaily, heading_index: int, hour: int, minute: int) -> str:
        # 10 minute interval
        value_index = int((hour * 60 + minute) / 10)

        if value_index >= len(daily.table_lines):
            print("failed to get daily value")
            return 0.0

        return daily.table_lines[value_index][heading_index]

    # show stations
    for name, station in target_points:
        print(name + ",", end="")
    print("")

    # get temperatures from meteorological agency
    amedas_daily_info = AmedasDailyInfo("workspace")
    for value in geotiff_target_points_values:

        print(value.geotiff_date, end="")

        for i in range(len(target_points)):
            name, station = target_points[i]
            daily: AmedasDaily = amedas_daily_info.get_amedas_daily(
                station.as_type,
                station.prec_no,
                station.block_no,
                value.geotiff_date.year,
                value.geotiff_date.month,
                value.geotiff_date.day,
            )
            heading_index = get_daily_heading_index(daily, "気温")
            if heading_index < 0:
                continue
            temperature_str = get_daily_hour_minute_value(
                daily,
                heading_index,
                value.geotiff_date.hour,
                value.geotiff_date.minute,
            )
            temperature = float(temperature_str)

            # compare values
            lst_temperature = value.lst_values[i] * 0.02 - 273

            # print
            print(str(temperature) + ", " + str(lst_temperature) + ", ", end="")

        # newline
        print("")


analysis1()
