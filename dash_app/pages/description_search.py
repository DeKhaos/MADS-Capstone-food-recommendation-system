import dash
from dash import html, dcc
from dash_iconify import DashIconify
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

dash.register_page(__name__, path="/description_search")

layout = html.Div(
    [
        dmc.Text("Cooking description", fw=700),
        dbc.Textarea(size="lg", placeholder="Give a brief description of the cooking steps or requirements")
        ],
    className="m-2 dbc"
)