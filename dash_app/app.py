import dash
from dash import html, dcc
from dash_bootstrap_templates import ThemeChangerAIO, template_from_url
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc
from dash_iconify import DashIconify
from project_package.dash_utilities import modals,filters

dbc_css = "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates/dbc.min.css"

app = dash.Dash(
    __name__, 
    use_pages=True,
    suppress_callback_exceptions=True,
    # add custom boostrap style so we can use theme changer for dcc components using className = 'dbc'
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc_css]  
)

theme_change = ThemeChangerAIO(aio_id="dbc_theme")

mode_switch = dmc.ColorSchemeToggle(
    lightIcon=DashIconify(icon="radix-icons:sun", width=20),
    darkIcon=DashIconify(icon="radix-icons:moon", width=20),
    color="yellow",
    size="sm",
    variant="filled",
    m=None,
)

# register modals
login_modal,login_button,login_info = modals.create_login_modal(login_id = "login")
profile_modal,profile_store = modals.user_profile_modal(login_id = "login")

# register filters
shared_filter,share_filter_store = filters.shared_filters("filter_search","shared_filter_store")
recommendation_components = filters.recommendation_filters("filter_search","login_profile_store","shared_filter_store")

footer = html.Small("© 2026 A MADS Capstone Project",className="text-center")

app.layout = dmc.MantineProvider(
    dmc.AppShell([
        dcc.Location(id="url",refresh="callback-nav"),

        dmc.Grid(
            children = [
                dmc.GridCol(dmc.Group([theme_change,mode_switch]), span=2),
                dmc.GridCol(span=7),
                dmc.GridCol(
                    dmc.Group(login_button,justify='flex-end'),
                    span=2),
                dmc.GridCol(dmc.Title(f"Meal Discovery - A cooking recipe recommendation system"),span=12)
            ],
            px='xs', py= 'xs',
            justify="space-between"
        ),

        dbc.NavbarSimple(
            [
                dbc.NavItem(dbc.NavLink("Recipe name search", href="/",active="exact")),
                dbc.NavItem(dbc.NavLink("Recipe instruction search", href="/description_search",active="exact")),
                dbc.NavItem(dbc.NavLink("Recipe Image search", href="/image_search",active="exact"))
            ],
            links_left = True,
            fluid = True
        ),

        dmc.AppShellMain(dmc.ScrollArea(
            html.Div(
                [
                    dbc.Row(
                        [
                            dbc.Col(shared_filter, width=5),
                            dbc.Col(
                                dbc.Card(
                                    [dash.page_container,
                                    recommendation_components]),
                                width=7
                                ),
                        ],
                        className="g-0",
                    ) 
                ]
            ),
            scrollbars="y"
            )
            ),

        dmc.AppShellFooter(dmc.Center(footer), p="sm"),

        # listing modals here
        login_modal,
        profile_modal,

        # list store object here
        login_info,
        profile_store,
        share_filter_store

    ],
    footer={"height": 40}
    ),
    id="mantine-provider"
)


if __name__ == '__main__':
    app.run(
        debug=True
        )