import pandas as pd

from src.fetch_poi import FetchPoi


def fetch(config):
    fetch = FetchPoi(config['location'],osm_endpoint=config['overpass_endpoint'])
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
        all_data = pd.concat([all_data, datasets[data]], ignore_index=True)
    
    all_data = all_data[['poi', 'place', 'geometry', 'shape', 'name', 'centroid', 'lat', 'lon', 'id']].drop_duplicates()
    
    return all_data