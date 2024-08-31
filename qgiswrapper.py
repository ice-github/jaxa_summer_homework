import os, math
from qgis.core import (
    QgsApplication,
    QgsMapLayer,
    QgsVectorLayer,
    QgsRasterLayer,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsTextBufferSettings,
    QgsTextFormat,
    QgsProject,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
    QgsFeature,
    QgsMarkerSymbol,
    QgsSingleSymbolRenderer,
    QgsMapSettings,
    QgsMapRendererParallelJob,
)
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtCore import QSize
from qgis.PyQt import QtGui


class QGisWrapper:

    def _get_point_and_label_layer(self) -> QgsVectorLayer:
        point_and_label_layer = QgsVectorLayer("Point?crs=epsg:6668&field=id:integer&field=name:string(20)", "Point Layer", "memory")

        # point setting
        symbol = QgsMarkerSymbol.createSimple({"name": "circle", "color": "255,0,0", "size": "1"})
        point_and_label_layer.setRenderer(QgsSingleSymbolRenderer(symbol))

        # label setting
        point_and_label_layer.setLabelsEnabled(True)
        label_settings = QgsPalLayerSettings()
        label_settings.drawLabels = True
        label_settings.fieldName = "name"  # indicated by crs
        label_settings.placement = QgsPalLayerSettings.Placement.AroundPoint
        labeling = QgsVectorLayerSimpleLabeling(label_settings)
        point_and_label_layer.setLabeling(labeling)
        point_and_label_layer.triggerRepaint()

        return point_and_label_layer

    def __init__(self) -> None:
        QgsApplication.setPrefixPath("/usr/bin/qgis", True)
        self._qgs = QgsApplication([], False)
        self._qgs.initQgis()
        self._project = QgsProject.instance()
        self._project.clear()

        self._point_and_label_layer: QgsVectorLayer = None
        self._number_of_point = 0
        self._shp_layers: list[QgsVectorLayer] = []
        self._geotiff_layers: list[QgsRasterLayer] = []

    def __del__(self) -> None:
        self._qgs.exitQgis()

    def add_point_and_label(self, point: QgsPointXY, label: str) -> bool:

        if self._point_and_label_layer is None:
            self._point_and_label_layer = self._get_point_and_label_layer()
            self._project.addMapLayer(self._point_and_label_layer)

        provider = self._point_and_label_layer.dataProvider()
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        feature.setAttributes([self._number_of_point + 1, label])
        self._number_of_point += 1

        self._point_and_label_layer.triggerRepaint()
        return provider.addFeature(feature)

    def add_shp(self, shp_path: str) -> bool:

        layer_number = len(self._shp_layers)
        layer = QgsVectorLayer(shp_path, "Shp Layer " + str(layer_number), "ogr")

        if not layer.isValid():
            print("Layer failed to load!")
            return False

        # add map layer
        self._project.addMapLayer(layer)
        self._shp_layers.append(layer)
        return True

    def add_geotiff(self, tif_path: str) -> int:  # output layer number

        layer_number = len(self._geotiff_layers)
        layer = QgsRasterLayer(tif_path, "Geotiff Layer " + str(layer_number))

        if not layer.isValid():
            print("Layer failed to load!")
            return -1

        # add map layer
        self._project.addMapLayer(layer)
        self._geotiff_layers.append(layer)
        return layer_number

    def get_geotiff_layer_value(self, point: QgsPointXY, layer_index: int) -> float:
        pass

    def get_shp_layers_extent(self) -> QgsRectangle:
        shp_layers_len = len(self._shp_layers)

        if shp_layers_len == 0:
            print("no shp layer!")
            return None

        extent = self._shp_layers[0].extent()
        # combine extent()
        for i in range(1, shp_layers_len):
            extent.combineExtentWith(self._shp_layers[i].extent())

        return extent

    def render_to_file(self, output_path: str, width: int, height: int) -> bool:

        render_layers: list[QgsMapLayer] = []

        if self._point_and_label_layer:
            render_layers.append(self._point_and_label_layer)

        for geotiff_layer in self._geotiff_layers:
            render_layers.append(geotiff_layer)

        for shp_layer in self._shp_layers:
            render_layers.append(shp_layer)

        extent = self.get_shp_layers_extent()
        if extent is None:
            extent = QgsRectangle(122, 20, 154, 46)  # japan

        if len(render_layers) == 0:
            print("no layer!")
            return False

        settings = QgsMapSettings()
        settings.setLayers(render_layers)
        settings.setBackgroundColor(QColor(255, 255, 255))  # white
        settings.setOutputSize(QSize(width, height))
        settings.setExtent(extent)
        renderer = QgsMapRendererParallelJob(settings)

        def finished():
            img: QtGui.QImage = renderer.renderedImage()
            img.save(output_path)
            print("Image saved at:", output_path)

        renderer.finished.connect(finished)
        renderer.start()
        renderer.waitForFinished()

        return True


def test():

    shp_path = "workspace/N03-20240101_23_GML/N03-20240101_23.shp"
    point = QgsPointXY(136.8855, 35.1077)  # minato, nagoya
    lst_path = "workspace/GC1SG1_20240801A01D_T0529_L2SG_LST_Q_3000.LST.tif"

    wrapper = QGisWrapper()
    print(wrapper.add_shp(shp_path))
    print(wrapper.add_point_and_label(point, "minato, nagoya"))
    print(wrapper.add_geotiff(lst_path))
    print(wrapper.render_to_file("workspace/output.png", 900, 900))


# test()
