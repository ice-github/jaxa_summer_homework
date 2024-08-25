import os, math
from osgeo import gdal


class GcomHdf5:

    def _get_rect(self, metadata: dict) -> list[float]:
        upper_left_lon = float(metadata["Geometry_data_Upper_left_longitude"])
        upper_left_lat = float(metadata["Geometry_data_Upper_left_latitude"])
        lower_right_lon = float(metadata["Geometry_data_Lower_right_longitude"])
        lower_right_lat = float(metadata["Geometry_data_Lower_right_latitude"])

        r = 6371000  # meter
        coeff = 0.017453292519943295
        # x = r * lon * cos(lat) * coeff
        # y = r * lat * coeff
        x_upper_left = r * upper_left_lon * math.cos(upper_left_lat * math.pi / 180) * coeff
        y_upper_left = r * upper_left_lat * coeff
        x_lower_right = r * lower_right_lon * math.cos(lower_right_lat * math.pi / 180) * coeff
        y_lower_right = r * lower_right_lat * coeff

        return [x_upper_left, y_upper_left, x_lower_right, y_lower_right]

    def __init__(self, path: str) -> None:

        if not os.path.exists(path):
            raise Exception("file not found")

        self._dataset: gdal.Dataset = gdal.Open(path)
        self._rect = self._get_rect(self._dataset.GetMetadata())

    def get_sub_image_path(self, sub_key: str, output_geotiff_path: str) -> bool:

        if os.path.exists(output_geotiff_path):
            print("geotiff already exists: ", output_geotiff_path)
            return True

        target_sub_dataset_name = ""
        for sub_dataset, info in self._dataset.GetSubDatasets():
            # print(sub_dataset)
            if sub_key in sub_dataset:
                target_sub_dataset_name = sub_dataset
                break

        if len(target_sub_dataset_name) == 0:
            print("couldn't find sub_key: ", sub_key)
            return False

        # translate to 53008
        gdal.Translate(
            "temp.tif",
            target_sub_dataset_name,
            format="GTiff",
            outputSRS="ESRI:53008",
            outputBounds=self._rect,
            noData=65535,
            creationOptions=["COMPRESS=LZW"],
        )

        # warp to 6668
        gdal.Warp(
            output_geotiff_path,
            "temp.tif",
            dstSRS="EPSG:6668",
        )

        os.remove("temp.tif")

        return True


def test():
    hdf = GcomHdf5("download/GC1SG1_20240801A01D_T0529_L2SG_LST_Q_3000.h5")

    path = "workspace/GC1SG1_20240801A01D_T0529_L2SG_LST_Q_3000.LST.tif"
    print(hdf.get_sub_image_path("Image_data/LST", path))


# test()
