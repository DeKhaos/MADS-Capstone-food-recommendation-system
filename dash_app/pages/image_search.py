import os

import dash
from dash import html, dcc, callback, Input,Output,State
from dash_iconify import DashIconify
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc

from project_package.modeling.ingredient_predictor import predict_from_base64
from project_package.dash_utilities.in_memory_variables import _app_data

dash.register_page(__name__, path="/image_search")

page_name = "image_search"

layout = dmc.Stack( 
[   dcc.Store(id={"page":page_name,"type":"input_store"},data={"ingredient_predictions":[]}),
    dmc.Center(
    [   html.Br(),
        dcc.Upload(
            id = f"{page_name}_upload_image",
            children = html.Div(
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
    ]),

    dbc.Collapse(
        children = [
            dmc.Center(dmc.Text("Uploaded image:",fw=700)),
            dmc.Center(id=f"{page_name}_image_preview"),
            dmc.Divider(label="Ingredient prediction settings",size="sm"),

            dbc.Row(
                [
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Prediction threshold:",
                                id = f"{page_name}_ingre_threshold",
                                min=0, max=1,value=0.28, decimalScale=2,step=0.01,
                                className="w-75"
                            ),
                            dbc.Tooltip(
                                "Threshold for model predictions, consider to be an ingredient if pass threshold.",
                                target=f"{page_name}_ingre_threshold"
                            )
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Top ingredients:",
                                id = f"{page_name}_top_n_ingre",
                                min=1, max=35,value=10, className="w-75"
                            ),
                            dbc.Tooltip(
                                "Number of ingredients that cross threshold and have highest probability",
                                target=f"{page_name}_top_n_ingre"
                            )
                        ],
                        width=4,
                    )
                ],align="end"
            ),
            dbc.Button(
                "Run prediction", id = f'{page_name}_button', 
                color="primary", className="mt-3 w-25",n_clicks = 0)
        ],
        is_open = False,
        id = f'{page_name}_prediction_collapse1'
    ),
    dbc.Collapse(
        children = dcc.Loading(html.Div(id = f'{page_name}_ingre_pred_container')),
        is_open = False,
        id = f'{page_name}_prediction_collapse2'
    )
    ],
    className="m-2 dbc"
)

@callback(
    Output(f"{page_name}_image_preview", "children"),
    Output(f'{page_name}_prediction_collapse1',"is_open"),
    Output(f'{page_name}_prediction_collapse2',"is_open",allow_duplicate=True),
    Output(f'{page_name}_ingre_pred_container','children',allow_duplicate=True),
    Output({"page":page_name,"type":"input_store"},"data",allow_duplicate=True),
    Input(f"{page_name}_upload_image", "contents"),
    prevent_initial_call = True
)
def update_output(contents):
    """
    Display upload image and setting menu.
    """
    if contents is not None:
        img = dmc.Image(
            src=contents,
            radius="md",
            h=300,
            w="auto",
            fit="contain",
            alt="Uploaded recipe image"
        )
        return img,True,False,None,{"ingredient_predictions":[]}
    return "",False,False,None,{"ingredient_predictions":[]}

@callback(
    Output(f'{page_name}_ingre_pred_container', "children"),
    Output(f'{page_name}_prediction_collapse2',"is_open"),
    Output({"page":page_name,"type":"input_store"},'data'),
    Input(f'{page_name}_button', "n_clicks"),
    State(f"{page_name}_upload_image", "contents"),
    State(f"{page_name}_ingre_threshold","value"),
    State(f"{page_name}_top_n_ingre","value"),
    prevent_initial_call=True
)
def run_ingredient_prediction(click,contents,threshold,top_k):
    """
    Run ingredient prediction.
    """
    if contents is None:
        return None,False,{"ingredient_predictions":[]}

    # Run ingredient prediction
    predictions = predict_from_base64(
        contents, 
        _app_data['image_model'], 
        _app_data['idx_to_ingredient'], 
        device = os.environ.get("DEVICE","cpu"),
        threshold=threshold,
        topk = top_k
    )

    if not predictions:
        mess = dmc.Text("No ingredients detected. Try a different photo or change threshold.", c="red")
        return mess,True,{"ingredient_predictions":[]}

    badges = dmc.Group(
        [dmc.Badge(f"{name} ({conf:.0%})", variant="outline") 
         for name, conf in predictions],
        gap="xs"
    )
    return badges,True,{"ingredient_predictions":predictions}

@callback(
    Output({"page":page_name,"type":"input_store"},'data',allow_duplicate=True),
    Input('url',"pathname"),
    prevent_initial_call = True
)
def clear_data_when_switch_page(_):
    return {"ingredient_predictions":[]}
