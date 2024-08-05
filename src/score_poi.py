import osmnx as ox
import h3
import math
import pandas as pd
import geopandas as gpd
import logging
logging.getLogger().setLevel(logging.INFO)
ox.config(use_cache=True, log_console=True)
ox.settings.overpass_rate_limit = False


class ScorePoi():
    def __init__(self, dataframe, k=1000, d=2000):
        """
        dataframe must have columns [lat, lon]
        k: distance till score is considered one.
        d: distance for the exponential decay to bring value to exp(-1)
        """
        self.k = k
        self.d = d
        self.data = gpd.GeoDataFrame(dataframe)
        self.hexagons = None
        self.poi_contributions = None
        self.__geometry()
        self.__circle_of_interest()

    def __geometry(self):
        """
        make dataframe as geoDataFrame with geometry being pair lat,lon. (in shapely geometries, it's inverted as
        Point(lon,lat)
        """
        logging.info("Computing geometry from lat, lon")
        if not {'lat', 'lon'}.issubset(self.data.columns):
            raise ValueError("['lat', 'lon'] not present in input data")
        else:
            self.data.dropna(subset=['lat', 'lon'], inplace=True)
            self.data['coordinates'] = self.data.apply(lambda x: [x.lat, x.lon], axis=1)

            self.data = gpd.GeoDataFrame(self.data, geometry=gpd.points_from_xy(self.data['lon'], self.data['lat']))

    def __circle_of_interest(self):
        logging.info(f"Computing circles of interest based on parameters k and d. \n \
                     current values: k = {self.k}, d = {self.d}")
        self.data['centroid'] = self.data.geometry.centroid
        self.data = self.data.set_geometry('centroid', crs=4326)

        self.data = self.data.to_crs(3035)

        self.data['circle_of_interest'] = self.data.apply(lambda x: x['centroid'].buffer(2 * self.d), axis=1)
        self.data = self.data.set_geometry("circle_of_interest")

    def score_poi(self, hexagons, poi_name='poi', aggregation='sum'):
        if hexagons.index.name == 'hex_id':
            hexagons.reset_index(inplace=True)

        logging.info("getting hexagons influenced by POI according to distances k and d...")
        candidate_hexes = gpd.sjoin(hexagons.to_crs(3035), self.data[['circle_of_interest']])
        candidate_hexes.drop_duplicates(subset=["hex_id"], inplace=True)
        candidate_hexes.drop(columns=['index_right'], inplace=True)

        logging.info("filtering POIs matching hexes...")
        candidate_poi = gpd.sjoin(self.data, hexagons[['geometry']].to_crs(3035), how='inner')
        candidate_poi.drop_duplicates(subset=['circle_of_interest'], inplace=True)
        candidate_poi.drop(columns=['index_right'], inplace=True)

        candidate_hexes['hex_centroid'] = candidate_hexes.geometry.centroid
        candidate_hexes = candidate_hexes.set_geometry("hex_centroid")
        candidate_hexes = candidate_hexes.to_crs(epsg=3035)
        candidate_hexes['circle_of_interest_hex'] = candidate_hexes.apply(lambda x: x.hex_centroid.buffer(self.d + self.k), axis=1)
        candidate_hexes = candidate_hexes.set_geometry("circle_of_interest_hex")

        logging.info("computing scores for data...")
        data_feasible = gpd.sjoin(candidate_poi, candidate_hexes[['circle_of_interest_hex', 'hex_id', 'geometry']])
        data_feasible.drop_duplicates(subset=['hex_id', 'lat', 'lon'], inplace=True)

        logging.info("getting distances between poi and hexagon centroids...")
        data_feasible['distance_km'] = data_feasible.apply(
            lambda x: h3.point_dist(h3.h3_to_geo(x.hex_id), x.coordinates, unit='km'), axis=1)

        D = self.d/1000
        K = self.k/1000

        data_feasible[f'score_{poi_name}'] = data_feasible.apply(lambda x: math.exp(-((max(x.distance_km - D, 0)) / (D-K))), axis=1)
        hex_scores = getattr(data_feasible.groupby(['hex_id'])[[f'score_{poi_name}']], aggregation)().reset_index()
        hex_scores = pd.merge(hexagons, hex_scores, how='left', on='hex_id').fillna(0)
        hex_scores = hex_scores.loc[:, ~hex_scores.columns.str.startswith('index')]

        self.poi_contributions = data_feasible[['lat', 'lon', 'coordinates', 'hex_id', f'score_{poi_name}']]

        return hex_scores
