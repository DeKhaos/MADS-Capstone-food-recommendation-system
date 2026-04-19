import os
from pathlib import Path
import ast

import dash_mantine_components as dmc
import dash_bootstrap_components as dbc
from dash import html, Output, Input, State, callback, ctx, dcc
from dash_iconify import DashIconify
import dash
import numpy as np
import pandas as pd

root_directory = Path(os.getcwd())

def create_login_modal(login_id: str):
    """
    Function which create logic components and callbacks logic which support it

    Parameters
    ----------

    login_id : str
        The custome login_id required to generate its children component ids.

    Returns
    ----------
    login_modal: dash component
        The hidden modal which we need to add to the layout.
    login_components: dash component
        The login component to add to the layout for clicking
    info_store: dcc.Store
        Session login information storage.
    """
    # PART 1: Modal logic

    info_store = dcc.Store(id=f"{login_id}_store", data={})  # use to store login info

    user_input = html.Div(
        [
            dbc.Label("User", html_for=f"{login_id}_username"),
            dbc.Input(type="text", id=f"{login_id}_username", placeholder="Enter username"),
        ],
        className="mb-3",
    )

    password_input = html.Div(
        [
            dbc.Label("Password", html_for=f"{login_id}_password"),
            dbc.Input(
                type="password",
                id=f"{login_id}_password",
                placeholder="Enter password",
            ),
        ],
        className="mb-3",
    )

    form_login = dbc.Form(
        [
            user_input,
            password_input,
            dbc.Alert(id=f"{login_id}_status", is_open=False),
            html.Div(
                [
                    dbc.Button("Login", id=f"{login_id}_confirm", className="me-2"),
                    dbc.Button("Create User", id=f"{login_id}_create"),
                ]
            ),
        ]
    )

    login_modal = dbc.Modal(
        id=f"{login_id}_modal",
        children=[dbc.ModalHeader("Login form"), dbc.ModalBody(form_login)],
        is_open=False,
    )

    @callback(
        Output(f"{login_id}_modal", "is_open"),
        Output(f"{login_id}_status", "is_open"),
        Input(login_id, "n_clicks"),
        State(f"{login_id}_modal", "is_open"),
        prevent_initial_call=True,
    )
    def open_login_modal(_, open_state):
        """
        Open the login modal when click login_id component
        """

        return not open_state, False

    @callback(
        Output(f"{login_id}_modal", "is_open", allow_duplicate=True),
        Output(f"{login_id}_status", "is_open", allow_duplicate=True),
        Output(f"{login_id}_status", "children"),
        Output(f"{login_id}_status", "color"),
        Output(f"{login_id}_store", "data"),
        Input(f"{login_id}_confirm", "n_clicks"),
        Input(f"{login_id}_create", "n_clicks"),
        State(f"{login_id}_username", "value"),
        State(f"{login_id}_password", "value"),
        prevent_initial_call=True,
    )
    def check_login(login, create, username, password):
        """
        Function that handle the logic to check the login information.
        """

        # PLACEHOLDER: connect to the server check for real user
        check_user = ["hello", "Kha Nguyen", "Sir Egg Crusher"]
        check_password = {"hello": "world", "Kha Nguyen": "123", "Sir Egg Crusher": "egg"}
        ######

        open_modal = True
        open_noti = False
        alert = ""
        color = "success"
        output_store = {}

        if ctx.triggered_id == f"{login_id}_confirm":
            if not (username in check_user and password == check_password[username]):
                open_noti = True
                alert = [
                    DashIconify(icon="radix-icons:cross-circled"),
                    " Username & password incorrect.",
                ]
                color = "danger"
            else:
                open_modal = False
                usr_split = username.split()
                if len(usr_split) > 1:
                    output_store["badge"] = usr_split[0][0].upper() + usr_split[-1][0].upper()
                else:
                    output_store["badge"] = usr_split[0][0].upper()

        else:  # create user
            if username in [None,''] or password in [None,'']:
                open_noti = True
                alert = [
                    DashIconify(icon="radix-icons:cross-circled"),
                    " Username & password can't be empty.",
                ]
                color = "danger"
            elif username in check_user:
                open_noti = True
                alert = [
                    DashIconify(icon="radix-icons:cross-circled"),
                    " Username already exists.",
                ]
                color = "danger"
            else:
                #PLACEHOLDER: Logic on how to save new user/password

                open_noti = True
                alert = [DashIconify(icon="radix-icons:check-circled"), " User created."]
                color = "success"

        return open_modal, open_noti, alert, color, output_store

    # PART 2: Login profile logic

    login_button = dbc.Button("Log in", id=login_id, outline=True, color="primary", size="sm")

    user_profile = dmc.Group(
        [
            dmc.Avatar(id=f"{login_id}_avatar", radius="xl", size="sm", color="cyan"),
            dbc.Button(
                "Profile",
                id=f"{login_id}_profile_button",
                outline=True,
                color="primary",
                size="sm",
            ),
            #NOTE: uncomment to turn on login logic again
            # dbc.Button(
            #     "Log out", id=f"{login_id}_logout", outline=True, color="primary", size="sm"
            # ),
        ],
        gap="xs",
    )

    login_components = html.Div(
        [   #NOTE: uncomment to turn on login logic again
            # dbc.Collapse(login_button, id=f"{login_id}_scheme_collapse", is_open=True),
            dbc.Collapse(user_profile, id=f"{login_id}_avatar_collapse", is_open=True),
        ]
    )
    #NOTE: uncomment to turn on login logic again
    # @callback(
    #     Output(f"{login_id}_scheme_collapse", "is_open"),
    #     Output(f"{login_id}_avatar_collapse", "is_open"),
    #     Output(f"{login_id}_avatar", "children"),
    #     Output(f"{login_id}_store", "data", allow_duplicate=True),
    #     Input(f"{login_id}_store", "data"),
    #     Input(f"{login_id}_logout", "n_clicks"),
    #     prevent_initial_call=True,
    # )
    # def switch_login_status(store_data, _):
    #     """
    #     Replace login button with user profile, if logged in.
    #     """

    #     login_open = dash.no_update
    #     avatar_open = dash.no_update
    #     update_avatar = dash.no_update
    #     update_data = dash.no_update

    #     if ctx.triggered_id == f"{login_id}_store" and store_data != {}:
    #         update_avatar = store_data["badge"]
    #         login_open = False
    #         avatar_open = True

    #     elif ctx.triggered_id == f"{login_id}_logout":
    #         update_avatar = ""
    #         login_open = True
    #         avatar_open = False
    #         update_data = {}

    #     return login_open, avatar_open, update_avatar, update_data

    return login_modal, login_components, info_store


def user_profile_modal(login_id):
    """
    Create user profile|preference modal, a coninuation of the create_login_modal() components.
    This modal allows users to customize their long-term search preferences or retrieve the existing
    profile from the server.

    Parameters
    ----------

    login_id : str
        Should be the login_id used in 'create_login_modal' function.

    Returns
    ----------
    profile_modal: dash component
        Modal to select the user preferences.
    
    profile_store: dcc.Store
        Session profile information storage.
    """
    
    
    # PLACEHOLDER: There should be a logic, function to retrieve all categorical options from database
    
    constraint_df = pd.read_csv(root_directory / 'data/processed/ui_feature_constraints.csv')
    constraint_df['value'] = constraint_df['value'].apply(ast.literal_eval)
    
    cuisine_list = constraint_df.loc[constraint_df['feature']=='cuisine','value'].tolist()[0]
    cooking_method_list = constraint_df.loc[constraint_df['feature']=='cooking_method','value'].tolist()[0]
    difficulty_list = constraint_df.loc[constraint_df['feature']=='difficulty','value'].tolist()[0]
    protein_content_list = constraint_df.loc[constraint_df['feature']=='protein_content','value'].tolist()[0]
    fiber_content_list = constraint_df.loc[constraint_df['feature']=='fiber_content','value'].tolist()[0]
    fat_content_list = constraint_df.loc[constraint_df['feature']=='fat_content','value'].tolist()[0]
    carbohydrate_content_list = constraint_df.loc[constraint_df['feature']=='carbohydrate_content','value'].tolist()[0]
    sodium_content_list = constraint_df.loc[constraint_df['feature']=='sodium_content','value'].tolist()[0]

    # cuisine_list = ["italian", "chinese", "india", "japanese", "mexican", "thai"]
    # dietary_list = ["vegan", "keto", "halal", "low-carb", "gluten-free"]
    # taste_list = ["sweet", "sour", "salty", "bitter", "umami/savory"]
    # allergen_list = [
    #     "celery",
    #     "gluten",
    #     "crustaceans",
    #     "eggs",
    #     "fish",
    #     "lupin",
    #     "milk",
    #     "molluscs",
    #     "mustard",
    #     "nuts",
    #     "peanuts",
    #     "sesame seeds",
    #     "sulphur dioxide",
    #     "soya",
    # ]
    ######

    option_stacks = html.Div(
        [
            dmc.Text("Select your favorite cuisine"),
            dcc.Dropdown(cuisine_list, id=f"{login_id}_cuisine_select", multi=True, maxHeight=300),
            html.Br(),
            dmc.Text("Preferred cooking method"),
            dcc.Dropdown(cooking_method_list, id=f"{login_id}_cooking_method_select", multi=True, maxHeight=300),
            html.Br(),
            dmc.Text("Preferred difficulty"),
            dcc.Dropdown(difficulty_list, id=f"{login_id}_difficulty_select", multi=True, maxHeight=300),
            html.Br(),
            dmc.Text("Preferred protein content"),
            dcc.Dropdown(protein_content_list, id=f"{login_id}_protein_select", multi=True, maxHeight=300),
            html.Br(),
            dmc.Text("Preferred fiber content"),
            dcc.Dropdown(fiber_content_list, id=f"{login_id}_fiber_select", multi=True, maxHeight=300),
            html.Br(),
            dmc.Text("Preferred fat content"),
            dcc.Dropdown(fat_content_list, id=f"{login_id}_fat_select", multi=True, maxHeight=300),
            html.Br(),
            dmc.Text("Preferred carbonhydrate content"),
            dcc.Dropdown(carbohydrate_content_list, id=f"{login_id}_carbonhydrate_select", multi=True, maxHeight=300),
            html.Br(),
            dmc.Text("Preferred sodium content"),
            dcc.Dropdown(sodium_content_list, id=f"{login_id}_sodium_select", multi=True, maxHeight=300),
        ],
        className="dbc",  # use this to update dcc components css style
    )

    profile_modal = dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Profile")),
            dbc.ModalBody(option_stacks),
        ],
        id=f"{login_id}_profile_modal",
        size="lg",
        is_open=False,
    )

    # store the output of profile preferences
    profile_store = dcc.Store(id=f"{login_id}_profile_store",data={})

    @callback(
        Output(f"{login_id}_profile_modal", "is_open"),
        Input(f"{login_id}_profile_button", "n_clicks"),
        State(f"{login_id}_profile_modal", "is_open"),
        prevent_initial_call=True,
    )
    def open_profile_modal(_, open_state):
        """
        Open the profile modal when click Profile button.
        """
        return not open_state
    
    @callback(
        output = dict(
            output_cuisine = Output(f"{login_id}_cuisine_select","value"),
            output_cooking_method = Output(f"{login_id}_cooking_method_select","value"),
            output_difficulty = Output(f"{login_id}_difficulty_select","value"),
            output_protein = Output(f"{login_id}_protein_select","value"),
            output_fiber = Output(f"{login_id}_fiber_select","value"),
            output_fat = Output(f"{login_id}_fat_select","value"),
            output_carbohydrate = Output(f"{login_id}_carbonhydrate_select","value"),
            output_sodium = Output(f"{login_id}_sodium_select","value")
        ),
        inputs = [Input(f"{login_id}_store", "data")],
        state = [State(f"{login_id}_profile_store","data")],
        prevent_initial_call = True
    )
    def load_initial_profile_preference(login_store_status,initial_state):
        """
        Load initial preference when user login.
        """
        
        if login_store_status != {} and (login_store_status is not None):
            if initial_state == {} or (not all(initial_state.values())):  # handle login/logout state

                #PLACEHOLDER: Load initial preferences from database if available
                # initial_cuisine = np.random.choice(
                #     cuisine_list,size=np.random.randint(0,1+len(cuisine_list)),
                #     replace=False).tolist()
                init_cuisine = []
                init_cooking = []
                init_difficulty = []
                init_protein = []
                init_fiber = []
                init_fat = []
                init_carbohydrate = []
                init_sodium = []
                
                ######

                return dict(
                    output_cuisine = init_cuisine,
                    output_cooking_method = init_cooking,
                    output_difficulty = init_difficulty,
                    output_protein = init_protein,
                    output_fiber = init_fiber,
                    output_fat = init_fat,
                    output_carbohydrate = init_carbohydrate,
                    output_sodium = init_sodium
                )
            else:
                return dict(
                    output_cuisine = dash.no_update,
                    output_cooking_method = dash.no_update,
                    output_difficulty = dash.no_update,
                    output_protein = dash.no_update,
                    output_fiber = dash.no_update,
                    output_fat = dash.no_update,
                    output_carbohydrate = dash.no_update,
                    output_sodium = dash.no_update
                )
        else:
            return dict(
                    output_cuisine = [],
                    output_cooking_method = [],
                    output_difficulty = [],
                    output_protein = [],
                    output_fiber = [],
                    output_fat = [],
                    output_carbohydrate = [],
                    output_sodium = []
                )

    @callback(
        Output(f"{login_id}_profile_store", "data"),
        inputs = dict(
            cuisine_select = Input(f"{login_id}_cuisine_select","value"),
            cooking_method_select = Input(f"{login_id}_cooking_method_select","value"),
            difficulty_select = Input(f"{login_id}_difficulty_select","value"),
            protein_select = Input(f"{login_id}_protein_select","value"),
            fiber_select = Input(f"{login_id}_fiber_select","value"),
            fat_select = Input(f"{login_id}_fat_select","value"),
            carbohydrate_select = Input(f"{login_id}_carbonhydrate_select","value"),
            sodium_select = Input(f"{login_id}_sodium_select","value")
        ),
        prevent_initial_call = True
    )
    def store_profile_preferences(
        cuisine_select,cooking_method_select,difficulty_select,protein_select,
        fiber_select,fat_select,carbohydrate_select,sodium_select
        ):
        """
        Store current profile preferences for the session
        """
        output_dict = dict()
        output_dict["cuisine_select"] = cuisine_select
        output_dict["cooking_method_select"] = cooking_method_select
        output_dict["difficulty_select"] = difficulty_select
        output_dict["protein_select"] = protein_select
        output_dict["fiber_select"] = fiber_select
        output_dict["fat_select"] = fat_select
        output_dict["carbohydrate_select"] = carbohydrate_select
        output_dict["sodium_select"] = sodium_select

        return output_dict

    return profile_modal,profile_store

def badge_list(
        badge_list:list
    ):
    """
    Create a badge list that allows user to easily identify which filter are match/unmatch.

    Parameters
    ----------

    badge_list: list
        The id of the search button.

    Returns
    ----------

    badges: dash component
        Return a list of badges for a recipe.
    """

    badges = []

    for name,priority,match in badge_list:
        input_text = name
        if type(match)==str:
            input_text = name + ': ' + match
            if eval(match) > 0.8: # condition for acceptable subslider match ratio
                color = 'lime'
            elif eval(match) > 0.35:
                color = 'yellow'
            else:
                color = 'red'
        else:
            color = 'lime' if match else 'red'
        
        badges.append(
            dmc.Badge(input_text,variant="outline" if priority=='priority' else "filled",color = color)
        )

    # for name,priority,match in badge_list:
    #     input_text = name
    #     if priority=='priority':
    #         color = 'white'
    #         if type(match) == str:
    #             input_text = name + ': ' + match
    #             if eval(match) > 0.8: # condition for acceptable subslider match ratio
    #                 text_color = 'success'
    #             elif eval(match) > 0.35:
    #                 text_color = 'warning'
    #             else:
    #                 text_color = 'danger'
    #         else:
    #             text_color = "success" if match else 'danger'
    #     else:
    #         color = "success" if match else 'danger'
    #         text_color = None
        
    #     badges.append(
    #         dbc.Badge(input_text,pill=True,color = color,text_color=text_color, className="me-1")
    #     )

    badges = dmc.Group(
        children=badges,
        gap="xs",     
        wrap="wrap"
    )

    return badges

def recommendation_card(
        item: dict,
        rank: int
    ):
    """
    Create a recipe info card that contain statistics info and filter matches.

    Parameters
    ----------

    item: dict
        The information dictionary of the recipe

    rank: int
        Rank of the recipe

    Returns
    ----------

    card: dash component
        Return a recipe card.
    """
    recipe_id = item['recipe_id']
    recipe_name = item['recipe_name']
    recipe_badges = item['badges']
    recipe_score = round(float(item['relevance_score']),4)
    recipe_fsa_score = item['fsa_score']
    recipe_who_score = item['who_score']
    recipe_img_url = item['image_url']

    card = dbc.Card(
        [
            dbc.CardHeader(
                dmc.Image(
                    radius="md",
                    h=200,
                    # w="100%",
                    fit="cover",
                    src=recipe_img_url,
                    # src="https://raw.githubusercontent.com/mantinedev/mantine/master/.demo/images/bg-9.png",
                    fallbackSrc="https://placehold.co/600x400?text=No+Image"  # PLACEHOLDER for image
                    
                ),
                className="p-1"
            ),
            dbc.CardBody(
                [   
                    #PLACEHOLDER: More information might be added here
                    html.H3(recipe_name, className="card-title",
                            style={
                                # "height": "3.6em",     # Exactly 2 lines of text
                                "height": "1em",
                                "overflow": "hidden"}
                            ),
                    html.H5(f'ID: {recipe_id}', className="card-title"),
                    html.H6(f"RANK: {rank} - Score: {recipe_score}"),
                    html.H6(f"FSA score: {recipe_fsa_score} - WHO score: {recipe_who_score}"),
                    badge_list(recipe_badges)
                ]
            ),
            dbc.CardFooter([
                dmc.Group(
                    [dbc.Button('Recipe info',size='sm',id = {"recipe_id":recipe_id,"type":"recipe_info"},n_clicks=0),
                    #TODO: Currently there is no recipe statistic
                    # dbc.Button('Statistics',size='sm',id = {"recipe_id":recipe_id,"type":"recipe_statistic"},n_clicks=0)
                    ],
                    justify="flex-start"
                )
            ]),
        ],
        style={"width": "32%"},
    )

    return card

def recipe_info_modal(search_id:str):
    """
    A popup recipe information modal.

    Parameters
    ----------

    search_id: str
        The id of the search button.

    Returns
    ----------

    component: dash component
        The popup modal.
    """
    component = dbc.Modal(
        id=f"{search_id}_info_modal",
        children=[dbc.ModalHeader("Recipe information"), dbc.ModalBody(id=f"{search_id}_info_modal_body")],
        is_open=False
    )
    return component

def recipe_statistic_modal(search_id:str):
    """
    A popup recipe statistic modal.

    Parameters
    ----------

    search_id: str
        The id of the search button.

    Returns
    ----------

    component: dash component
        The popup modal.
    """
    component = dbc.Modal(
        id=f"{search_id}_stat_modal",
        children=[dbc.ModalHeader("Recipe statistics"), dbc.ModalBody(id=f"{search_id}_stat_modal_body")],
        is_open=False
    )
    return component

def visualization_modal(search_id:str):
    """
    A popup recipe statistic modal.

    Parameters
    ----------

    search_id: str
        The id of the search button.

    Returns
    ----------

    component: dash component
        The popup modal.
    """
    component = dbc.Modal(
        id=f"{search_id}_visualization_modal",
        children=[dbc.ModalHeader("Visualization"), dbc.ModalBody(id=f"{search_id}_visualization_modal_body")],
        is_open=False,
        size='xl'
    )
    return component

