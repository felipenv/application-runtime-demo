import osmnx as ox
from tobler.util import h3fy
import os
import geopandas as gpd
import logging
logging.getLogger().setLevel(logging.INFO)
ox.config(use_cache=True, log_console=True)
ox.settings.overpass_rate_limit = False


class Hexes():
    def __init__(self, place, road_type_list=[], overpass_endpoint="https://overpass-api.de/api"):
        self.place = place
        self.road_type_list = "|".join(road_type_list)
        self.place_polygon = None
        self.place_map = None
        self.place_graph = None
        self.place_hexes = None
        self.place_roads_hex = None
        self.place_roads_thick = None
        ox.settings.overpass_endpoint = overpass_endpoint

    def __save_gdf(self, gdf, path, file_name):
        if not os.path.exists(f'{path}'):
            os.makedirs(f'{path}')

        gdf.to_file(f'{path}/{self.place.lower()}_{file_name}')

    def save_place_map(self, folder_to_save):
        self.__save_gdf(self.place_map, folder_to_save, file_name='polygon.shp')

    def save_hex_roads(self, folder_to_save):
        self.__save_gdf(self.place_roads_hex, folder_to_save, file_name='roads_hex.shp')

    def save_roads_thick(self, folder_to_save):
        self.__save_gdf(self.place_roads_thick, folder_to_save, file_name='roads_thick_hex.shp')

    def save_place_graph(self, folder_to_save):
        if not os.path.exists(f'{folder_to_save}'):
            os.makedirs(f'{folder_to_save}')

        ox.io.save_graph_shapefile(self.place_graph, filepath=f'{folder_to_save}')
        ox.io.save_graphml(self.place_graph, filepath=f'{folder_to_save}/graphml')

    def make_polygon(self):
        self.place_map = ox.geocode_to_gdf(self.place)

        if self.place_map['geometry'][0].geom_type == 'MultiPolygon':
            self.place_polygon = max(self.place_map['geometry'][0], key=lambda a: a.area)  # get the mainland polygon
        elif self.place_map['geometry'][0].geom_type == 'Polygon':
            self.place_polygon = self.place_map['geometry'][0]
        self.place_map['geometry'] = self.place_polygon

    def get_graph_place(self):

        logging.info(f"getting {self.place} roads..\n")

        self.make_polygon()
        if not self.road_type_list:
            print("attribute road_type_list is empty... won't fetch roads for this place")

        else :
            self.place_graph = ox.graph_from_polygon(self.place_polygon, truncate_by_edge=True, network_type='drive',
                                      custom_filter=f"['highway'~'{self.road_type_list}']")

    def get_place_hex(self, h3_resolution):
        if self.place_map is None:
            self.make_polygon()
        self.place_hexes = h3fy(self.place_map, resolution=h3_resolution)

    def get_hex_roads(self, h3_resolution):
        if self.place_hexes is None:
            if self.place_map is None:
                self.make_polygon()
            self.place_hexes = h3fy(self.place_map, resolution=h3_resolution)

        if self.place_graph is None:
            self.get_graph_place()
        if self.place_graph is not None:
            nodes, edges = ox.graph_to_gdfs(self.place_graph)

            self.place_roads_hex = gpd.sjoin(self.place_hexes, edges[["geometry"]])
            self.place_roads_hex.drop_duplicates(subset=['geometry'], inplace=True)

    def get_thick_hex_roads(self, width_m):
        if self.place_roads_hex is None:
            raise ValueError("please run get_hex_roads first...")

        nodes, edges = ox.graph_to_gdfs(self.place_graph)

        thick_edges_gdf = edges[['geometry']].copy()
        thick_edges_gdf = thick_edges_gdf.to_crs(epsg=3035)
        thick_edges_gdf['geometry'] = thick_edges_gdf['geometry'].apply(lambda x: x.buffer(width_m / 2))
        self.place_roads_thick = gpd.sjoin(self.place_hexes, thick_edges_gdf[['geometry']].to_crs(epsg=4326))
        self.place_roads_thick.drop_duplicates(subset=['geometry'], inplace=True)
