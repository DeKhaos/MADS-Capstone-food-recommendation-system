import dash
from dash import html, dcc
from dash_iconify import DashIconify
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc
from project_package.dash_utilities import filters

dash.register_page(__name__, path="/image_search")

image_filters,filter_store = filters.shared_filters("image_filter_search","image_filter_store")

output_components = filters.recommendation_filters("image_filter_search","login_profile_store","image_filter_store")

layout = html.Div(
    [
        dbc.Row(
            [
                dbc.Col(image_filters, width=5),
                dbc.Col(
                    dbc.Card(
                        [
                            dmc.Center(
                                dcc.Upload(
                                    html.Div(
                                        [
                                            "Drag and drop \n or select and image",
                                            html.Br(),
                                            DashIconify(
                                                icon="material-symbols:image-inset-sharp",
                                                height=100,
                                                width=100,
                                            ),
                                        ],
                                        className="p-3 d-flex flex-column justify-content-center align-items-center",
                                        style={"cursor": "pointer", "border": "1px dashed"},
                                    )
                                )
                            ),
                            output_components
                        ]
                    ),
                    width=7
                ),
            ],
            className="g-0",
        ),

        # list store object here
        filter_store
    ]
)
