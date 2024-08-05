import pandas as pd
import geopandas as gpd

from src.fetch_poi import FetchPoi
from src.hexes import Hexes
from src.score_poi import ScorePoi


def fetch(config):
    # get hexes for location
    hexes = Hexes(place=config['location'])
    hexes.get_place_hex(h3_resolution=config['h3_resolution'])
    hex_scores = hexes.place_hexes

    fetcher = FetchPoi(config['location'], osm_endpoint=config['overpass_endpoint'])
    datasets = {}
    for dataset in config['datasets']:
        print(f'fetching {dataset}')
        if dataset not in datasets:
            tag = config['datasets'][dataset]['tag']
            values = config['datasets'][dataset]['values']
            _, datasets[dataset] = fetcher.fetch_data(tag=tag, values=values)
            datasets[dataset]['lat'] = datasets[dataset]['centroid'].apply(lambda x: x.y)
            datasets[dataset]['lon'] = datasets[dataset]['centroid'].apply(lambda x: x.x)
            datasets[dataset].dropna(subset=tag, inplace=True)
            datasets[dataset] = datasets[dataset].loc[:, datasets[dataset].isnull().mean() < .3]
            scoring = ScorePoi(datasets[dataset], k=100, d=500)
            hex_scores = scoring.score_poi(hex_scores, poi_name=dataset, aggregation='sum')

    all_data = pd.DataFrame()
    for data in datasets:
        datasets[data].rename(columns={data: 'poi'}, inplace=True)
        datasets[data]['category'] = data
        all_data = pd.concat([all_data, datasets[data]], ignore_index=True)

    all_data = all_data[
        ['category', 'poi', 'place', 'geometry', 'shape', 'name', 'centroid', 'lat',
         'lon', 'id']].drop_duplicates()

    data_within_boundaries = gpd.sjoin(all_data, fetch.place_map[['geometry']],
                                       how='inner').drop(columns=['index_right'])

    return data_within_boundaries, hex_scores
