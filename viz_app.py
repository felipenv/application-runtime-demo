import json
import pickle
import yaml

import pandas as pd
import plotly.graph_objects as go
import vizro.models as vm
import vizro.plotly.express as px

from geojson import Feature, Point, FeatureCollection, Polygon
from vizro import Vizro
from vizro.models.types import capture


def plot_poi(gdf, plot_config):
    fig = px.scatter_mapbox(gdf, lat="lat", lon="lon", color="category",
                            labels={'category'},
                            # size="size",
                            color_discrete_map=plot_config['colors'],
                            size_max=8, zoom=8,
                            hover_data=plot_config['hover_info'])

    return fig


def hexagons_dataframe_to_geojson(df_hex, hex_id_field, geometry_field, value_field, file_output=None):
    '''
    Helper function for plot choropleth to generate geojson file that is needed.
    '''
    # print(df_hex, hex_id_field, geometry_field, value_field, file_output)
    list_features = []

    for i, row in df_hex.iterrows():
        feature = Feature(geometry=row[geometry_field],
                          id=row[hex_id_field],
                          properties={"value": row[value_field]})
        list_features.append(feature)

    feat_collection = FeatureCollection(list_features)

    if file_output is not None:
        with open(file_output, "w") as f:
            json.dump(feat_collection, f)

    else:
        return feat_collection



def plot_hexes(geo_dataframe, hex_id, value_field, geometry_field, hover_data=None,
                    color_continuous_scale="RdYlGn", satellite=False, opacity=0.5, marker=None, mapbox_accesstoken=None):
    '''
    Main plotting function that uses plotly plot_choropleth function to produce the map.
    '''

    # print(geo_dataframe, hex_id, value_field, geometry_field, hover_data, color_continuous_scale, satellite, opacity)

    # create geojson object needed
    geojson_obj = hexagons_dataframe_to_geojson(geo_dataframe,
                                                hex_id_field=hex_id,
                                                value_field=value_field,
                                                geometry_field=geometry_field)


    # discrete coloring (e.g. truck stop areas) is triggered by string values
    if type(geo_dataframe[value_field].iloc[0]) == str:

        fig = px.choropleth_mapbox(
            geo_dataframe,
            geojson=geojson_obj,
            locations=hex_id,
            color=value_field,
            color_discrete_map={"stop": "cyan", "dealer": "#BF40BF", "hub": "#FF97FF"},
            mapbox_style='carto-positron',
            zoom=4,
            center={"lat": 53, "lon": 10},
            opacity=opacity,
            hover_data=hover_data)

    # continuous coloringis triggered by numeric values (e.g. choropleth function to plots hexes)
    else:
        fig = px.choropleth_mapbox(
            geo_dataframe,
            geojson=geojson_obj,
            locations=hex_id,
            color=value_field,
            color_continuous_scale=color_continuous_scale,
            mapbox_style='carto-positron',
            zoom=4,
            center={"lat": 53, "lon": 10},
            opacity=opacity,
            hover_data=hover_data,
            labels={value_field: value_field},
            custom_data=hover_data,)

        fig.update_coloraxes(cmin=0, cmax=geo_dataframe[value_field].max()) # only for continuous colorscale reset

        list_hover_data = [f"{name}:"+" %{customdata[" + f"{nr}" + "]}" for nr, name in enumerate(hover_data)]

        # add spaces to the hover data
        spaces = [1, 9, 17]
        for ix, i in enumerate(spaces):
            list_hover_data.insert(i+ix, '<br>')

        fig.update_traces(hovertemplate="<br>".join(list_hover_data))

    # shows satellite in background if desired
    if satellite:
        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, mapbox_accesstoken=mapbox_accesstoken, mapbox_style="satellite-streets")
    else:
        fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0}, mapbox_accesstoken=mapbox_accesstoken, mapbox_style='streets')

    return fig


def final_score(hexes, config):
    score_columns = hexes.columns[hexes.columns.str.startswith('score')]
    hexes[score_columns] = hexes[score_columns].clip(0, 2)
    for c in score_columns:
        category = c.split('_')[1]
        hexes[c] = hexes[c] * config['datasets'][category]['weight']

    hexes['score'] = hexes[score_columns].sum(axis=1)
    return hexes


@capture('graph')
def merge_graphs(data_frame, fig1, fig2):
    return go.Figure(data=fig1.data + fig2.data)


config = yaml.safe_load(open("config/config.yaml"))
pois = pickle.load(open("data/pois.pkl", 'rb'))
hexes = pickle.load(open("data/hexes.pkl", 'rb'))

hexes = final_score(hexes, config)

plot_config = config['plots']

px.set_mapbox_access_token(plot_config['mapbox_token'])

fig_pois = plot_poi(pois, plot_config['pois'])

hover_info = list(set(plot_config['hexes']['hover_info']) | set(
    hexes.columns[hexes.columns.str.startswith('score')]))
hex_fig = plot_hexes(geo_dataframe=hexes, hex_id="hex_id", value_field="score",
                      geometry_field= "geometry", hover_data=hover_info,
                     color_continuous_scale=plot_config['hexes']['palette'],
                     satellite=False,
                     mapbox_accesstoken=plot_config['mapbox_token'])

hex_fig.update_mapboxes(center=dict(plot_config['center']),
                        zoom=plot_config['zoom']
)

# for j in range(len(fig_pois.data)):
#     hex_fig.add_trace(fig_pois.data[j])
#     for i, frame in enumerate(hex_fig.frames):
#         hex_fig.frames[i].data += (fig_pois.frames[i].data[j],)

fig = merge_graphs(pd.DataFrame(), hex_fig, fig_pois)

page = vm.Page(
    title="Map POI",
    components=[
        vm.Graph(figure=fig)
    ],
    # controls=[
    #     vm.Filter(column="category"),
    #     vm.Filter(column="score")
    # ]
)

dashboard = vm.Dashboard(pages=[page], theme="vizro_light")
app = Vizro().build(dashboard)
server = app.dash.server


if __name__=="__main__":
    app.run()