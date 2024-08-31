import os
from datetime import datetime
from dataclasses import dataclass

from japanmlitnlftp import AdministrativeDivision
from japanmlitnlftp import AdministrativeDivisionInfo

from qgiswrapper import QGisWrapper
from gcom import CSWWrapper, GcomDownloader
from hdf5togeotiff import GcomHdf5


def analysis1():

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
    dataset_id = "10002019"  # LST
    utc_start = datetime(2021, 8, 1)
    utc_end = datetime(2021, 8, 2)
    bbox = [aichi_extent.xMinimum, aichi_extent.yMaximum, aichi_extent.xMaximum, aichi_extent.yMinimum]
    # bbox = [130, 40, 140, 30]
    csw_wrapper = CSWWrapper()
    hdf5_urls = csw_wrapper.get_hdf5_urls(dataset_id, utc_start, utc_end, bbox)

    # download hdf5 files
    username = "*****"
    password = "*****"
    gcom_downloader = GcomDownloader("download", "workspace", username, password)
    hdf5_file_paths = gcom_downloader.get_downloaded_file_paths(hdf5_urls)

    # geotiff
    @dataclass
    class LSTGeoTiff:
        lst_image_path: str
        qa_flag_image_path: str
        jst_start_date: datetime
        jst_end_date: datetime

    # convert to geotiff
    list_geo_tiffs: list[LSTGeoTiff] = []
    for path in hdf5_file_paths:

        # filepath to extract path
        filename_without_extension = os.path.splitext(os.path.basename(path))[0]
        lst_path = os.path.join("workspace", filename_without_extension + "_LST.tif")
        qa_flag_path = os.path.join("workspace", filename_without_extension + "_QA_flag.tif")

        gcom_hdf5 = GcomHdf5(path)
        gcom_hdf5.get_sub_image_path("Image_data/LST", lst_path)
        gcom_hdf5.get_sub_image_path("Image_data/QA_flag", qa_flag_path)
        jst_start, jst_end = gcom_hdf5.get_jst_start_end()

        list_geo_tiffs.append(LSTGeoTiff(lst_path, qa_flag_path, jst_start, jst_end))

    # apply to qgis

    # get values

    # get temperatures from meteorological agency

    # compare values

    pass
