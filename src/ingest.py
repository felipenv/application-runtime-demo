import pandas as pd
import geopandas as gpd

from src.fetch_poi import FetchPoi
from src.hexes import Hexes


def fetch(config):
    fetch = FetchPoi(config['location'], osm_endpoint=config['overpass_endpoint'])
    datasets = {}
    for dataset in config['datasets']:
        print(f'fetching {dataset}')
        if dataset not in datasets:
            tag = config['datasets'][dataset]['tag']
            values = config['datasets'][dataset]['values']
            _, datasets[dataset] = fetch.fetch_data(tag=tag, values=values)
            datasets[dataset]['lat'] = datasets[dataset]['centroid'].apply(lambda x: x.y)
            datasets[dataset]['lon'] = datasets[dataset]['centroid'].apply(lambda x: x.x)
            datasets[dataset].dropna(subset=tag, inplace=True)
            datasets[dataset] = datasets[dataset].loc[:, datasets[dataset].isnull().mean() < .3]

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

    hexes = Hexes(place=config['location'])
    hexes.get_place_hex(h3_resolution=config['h3_resolution'])

    return data_within_boundaries, hexes.place_hexes
