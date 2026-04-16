import dash
from dash import html, dcc, callback,Input,Output,State
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

page_name = "text_search"

dash.register_page(__name__, path="/text_search")

layout = html.Div(
    [   dcc.Store(id={"page":"text_search","type":"input_store"},data={"recipe_name":"","recipe_description":""}),
        dmc.Text("Recipe name", fw=700,className="my-2"),
        dbc.Input(value='',id=f"{page_name}_recipe_name",type='text',size="lg", 
                  placeholder="Input the recipe name",debounce=True),
        dmc.Text("Recipe description", fw=700,className="my-2"),
        dbc.Textarea(
            value='',id=f"{page_name}_recipe_descript",debounce=True,
            size="lg", placeholder="Give a brief description of the recipe, cooking steps or requirements,etc.")
        ],
    className="m-2 dbc"
)

@callback(
    Output({"page":"text_search","type":"input_store"},"data"),
    Input(f"{page_name}_recipe_name","value"),
    Input(f"{page_name}_recipe_descript","value"),
    State({"page":"text_search","type":"input_store"},"data"),
    prevent_initial_call = True
)
def store_text_inputs(recipe_name,_recipe_descript,recipe_store):
    """
    Store text inputs for recommendation pipeline usage.
    """
    recipe_store["recipe_name"] = recipe_name
    recipe_store["recipe_description"] = _recipe_descript
    
    return recipe_store