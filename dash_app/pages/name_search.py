import dash
from dash import html, dcc
from dash_iconify import DashIconify
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

dash.register_page(__name__, path="/")

layout = html.Div(
    [
        dmc.Text("Recipe name", fw=700),
        dbc.Input(type='text',size="lg", placeholder="Input the recipe name")
        ],
    className="m-2 dbc"
)