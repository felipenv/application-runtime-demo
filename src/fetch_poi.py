import osmnx as ox
import os
import overpy
import pandas as pd
import geopandas as gpd
from shapely import geometry
from tqdm import tqdm
import numpy as np
import logging
import warnings
from shapely.errors import ShapelyDeprecationWarning
warnings.filterwarnings("ignore", category=ShapelyDeprecationWarning)
logging.getLogger().setLevel(logging.INFO)
ox.config(use_cache=True, log_console=True)
ox.settings.overpass_rate_limit = False


class FetchPoi():
    def __init__(self, place, osm_endpoint="https://overpass-api.de/api/interpreter"):
        self.place = place
        self.osm_endpoint = osm_endpoint
        self.place_map = None
        self.place_polygon = None
        self.overpass = overpy.Overpass()
        self.overpass.url = osm_endpoint

    def __save_gdf(self, gdf, path, file_name):
        if not os.path.exists(f'{path}'):
            os.makedirs(f'{path}')

        gdf.to_file(f'{path}/{self.place.lower()}_{file_name}')

    def save_place_map(self, folder_to_save):
        self.__save_gdf(self.place_map, folder_to_save, file_name='polygon.shp')

    def make_polygon(self):
        self.place_map = ox.geocode_to_gdf(self.place)

        if self.place_map['geometry'][0].geom_type == 'MultiPolygon':
            self.place_polygon = max(self.place_map['geometry'][0], key=lambda a: a.area)  # get the mainland polygon
        elif self.place_map['geometry'][0].geom_type == 'Polygon':
            self.place_polygon = self.place_map['geometry'][0]
        self.place_map['geometry'] = self.place_polygon

    def grid_country_polygon(self):
        xmin, ymin, xmax, ymax = np.round(self.place_map.total_bounds, 1)

        cell_width = max(0.1,(xmax-xmin)/10)
        cell_height = max(0.1,(ymax-ymin)/10)
        grid_cells = []
        for x0 in tqdm(np.arange(xmin, xmax + cell_width, cell_width)):
            for y0 in np.arange(ymin, ymax + cell_height, cell_height):
                x1 = x0 - cell_width
                y1 = y0 + cell_height
                new_cell = geometry.box(x0, y0, x1, y1)
                if new_cell.intersects(self.place_map['geometry'][0]):
                    grid_cells.append(new_cell)
                else:
                    pass
        grid_df = gpd.GeoDataFrame(grid_cells, columns=['geometry'], crs=4326)

        return grid_df

    def polygons_for_queries(self, grid_country):
        list_polygons_query = []
        for grid in grid_country['geometry']:
            l = [tuple(reversed(t)) for t in grid.exterior.coords[:]]  # list of reversed tuples
            opened_tuples_list = list(sum(list(l[:-1]), ()))
            opened_tuples_list = list(np.around(np.array(opened_tuples_list), 1))
            polygon_string = " ".join(map(str, opened_tuples_list))
            list_polygons_query.append(polygon_string)

        return list_polygons_query

    def fetch_data(self, tag, values, allow_same_area=True):
        if self.place_polygon is None:
            self.make_polygon()

        results = []
        grid_place = self.grid_country_polygon()
        list_polygons_query = self.polygons_for_queries(grid_place)
        place_df = pd.DataFrame()
        logging.info(f"getting data per grid for {self.place}....\n")

        for poly in tqdm(list_polygons_query):
            query = f"""
                    (
                      node[{tag}~"{"|".join(values)}"](poly:'{poly}');
                      way[{tag}~"{"|".join(values)}"](poly:'{poly}');
                      relation[{tag}~"{"|".join(values)}"](poly:'{poly}');
                    );
                    out body;
                    >;
                    out skel qt;

                    """

            result = self.overpass.query(query)
            results.append(result)
            df = self.build_place_df(result, allow_same_area)
            place_df = pd.concat([place_df, df], ignore_index=True)

        return results, place_df.reset_index(drop=True)

    def build_place_df(self, result, allow_same_area=True):
        # build country Data frame
        records_ways = []
        for way in result.ways:
            row = way.tags
            row['id'] = way.id
            row['place'] = self.place
            # convert list of coords to linestring
            list_coords = []
            for node in way.nodes:
                list_coords.append((node.lon, node.lat))  # create a list of node coordinates
            if list_coords[0] == list_coords[-1]:
                row['geometry'] = geometry.Polygon(list_coords)
                row['shape'] = 'Polygon'
            else:
                row['geometry'] = geometry.LineString(list_coords)
                row['shape'] = 'LineString'

            records_ways.append(row)

        place_df_ways = gpd.GeoDataFrame.from_records(records_ways)
        if 'geometry' in place_df_ways:
            place_df_ways.set_geometry('geometry', inplace=True)

        if not place_df_ways.empty:
            place_df_ways.set_crs(4326, inplace=True)
            place_df_ways.set_geometry('geometry', inplace=True)
            place_df_ways['centroid'] = place_df_ways.apply(lambda x: x.geometry.centroid, axis=1)

        records_nodes = []
        for node in result.nodes:
            row = node.tags
            row['lat'] = node.lat
            row['lon'] = node.lon
            row['place'] = self.place
            row['geometry'] = geometry.Point(node.lon, node.lat)
            row['shape'] = 'Point'

            records_nodes.append(row)

        place_df_nodes = gpd.GeoDataFrame.from_records(records_nodes)
        if 'geometry' in place_df_nodes:
            place_df_nodes.set_geometry('geometry', inplace=True)

        if not place_df_nodes.empty:
            place_df_nodes.set_crs(4326, inplace=True)
            place_df_nodes.set_geometry('geometry', inplace=True)
            place_df_nodes['centroid'] = place_df_nodes.apply(lambda x: x.geometry.centroid, axis=1)

        # check if node is inside a polygon considered above and remove it.
        if not allow_same_area:
            place_df_nodes = place_df_nodes.merge(place_df_ways[['geometry']], how='left', indicator=True)
            place_df_nodes = place_df_nodes[place_df_nodes['_merge'] == 'left_only'].drop(columns='_merge')

        place_df = pd.concat([place_df_ways, place_df_nodes], axis=0)

        place_df.reset_index(drop=True, inplace=True)
        return place_df

