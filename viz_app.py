import pickle
import yaml

from vizro import Vizro
import vizro.models as vm
import vizro.plotly.express as px


def plot_poi(gdf, plot_config):
    fig = px.scatter_mapbox(gdf, lat="lat", lon="lon", color="category",
                            labels={'category'},
                            # size="size",
                            color_discrete_map=plot_config['colors'],
                            size_max=8, zoom=8,
                            hover_data=hover_data)

    return fig


if __name__=="__main__":
    config = yaml.safe_load(open("config/config.yaml"))
    data = pickle.load(open("data/dataset.pkl", 'rb'))

    plot_config = config['plots']
    hover_data = ['poi', 'name']

    px.set_mapbox_access_token(plot_config['mapbox_token'])

    fig = plot_poi(data, plot_config)

    page = vm.Page(
        title="Map POI",
        components=[
            vm.Graph(figure=fig)
        ],
        controls=[
            vm.Filter(column="category"),
            vm.Filter(column="poi")
        ]
    )

    Vizro().build(vm.Dashboard(pages=[page])).run()