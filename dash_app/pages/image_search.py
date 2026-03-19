import dash
from dash import html, dcc
from dash_iconify import DashIconify
import dash_mantine_components as dmc

dash.register_page(__name__, path="/image_search")

layout = dmc.Center(
    [   html.Br(),
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
    )],
    className="m-2 dbc"
)