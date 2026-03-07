import dash_mantine_components as dmc
import dash_bootstrap_components as dbc
from dash import html, Output, Input, State, callback,ctx, dcc
from dash_iconify import DashIconify
import dash

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

    info_store = dcc.Store(id=f"{login_id}_store",data={})  # use to store login info

    user_input = html.Div(
        [
            dbc.Label("User", html_for=f"{login_id}_username"),
            dbc.Input(
                type="text", 
                id=f"{login_id}_username", 
                placeholder="Enter username"
            ),
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
            )
        ],
        className="mb-3",
    )

    form_login = dbc.Form(
        [
            user_input, 
            password_input,
            dbc.Alert(id = f"{login_id}_status",is_open=False),
            html.Div([
                dbc.Button("Login", id = f"{login_id}_confirm",className='me-2'),
                dbc.Button("Create User", id = f"{login_id}_create")
            ])
         
         ]
    )

    login_modal = dbc.Modal(
        id=f"{login_id}_modal",
        children=[
            dbc.ModalHeader("Login form"),
            dbc.ModalBody(
                form_login
            )
        ],
        is_open = False
    )

    @callback(
        Output(f"{login_id}_modal", "is_open"),
        Output(f"{login_id}_status","is_open"),
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
        Output(f"{login_id}_modal", "is_open",allow_duplicate=True),
        Output(f"{login_id}_status","is_open",allow_duplicate=True),
        Output(f"{login_id}_status","children"),
        Output(f"{login_id}_status","color"),
        Output(f"{login_id}_store","data"),
        Input(f"{login_id}_confirm","n_clicks"),
        Input(f"{login_id}_create","n_clicks"),
        State(f"{login_id}_username", "value"),
        State(f"{login_id}_password", "value"),
        prevent_initial_call=True,
    )
    def check_login(login,create,username,password):
        """
        Function that handle the logic to check the login information.
        """

        #PLACEHOLDER: connect to the server check for real user
        check_user = ["hello","Kha Nguyen","Sir Egg Crusher"]
        check_password = {
            "hello":"world",
            "Kha Nguyen":"123",
            "Sir Egg Crusher":"egg"
        }
        ######

        open_modal = True
        open_noti = False
        alert = ""
        color = "success"
        output_store = {}

        if ctx.triggered_id == f"{login_id}_confirm":
            if not (username in check_user and password == check_password[username]):
                open_noti = True
                alert = [DashIconify(icon="radix-icons:cross-circled"),
                       " Username & password incorrect."]
                color = "danger"
            else:
                open_modal = False
                usr_split = username.split()
                if len(usr_split) > 1:
                    output_store["badge"] = usr_split[0][0].upper() + usr_split[-1][0].upper()
                else:
                    output_store["badge"] = usr_split[0][0].upper()

        else:  # create user
            if username in check_user:
                open_noti = True
                alert = [DashIconify(icon="radix-icons:cross-circled"),
                       " Username already exists."]
                color = "danger"
            else:
                open_noti = True
                alert = [DashIconify(icon="radix-icons:check-circled"),
                       " User created."]
                color = "success"

        return open_modal,open_noti,alert,color,output_store

    # PART 2: Login profile logic

    login_button = dbc.Button(
        "Log in", id = login_id,
        outline=True, color="primary",size='sm'
    )

    user_profile = dmc.Group(
            [
                dmc.Avatar(id = f"{login_id}_avatar",radius="xl", size="sm",color='cyan'),
                dbc.Button("Profile", id = f"{login_id}_profile_button", 
                           outline=True, color="primary",size='sm'),
                dbc.Button("Log out", id = f"{login_id}_logout", 
                           outline=True, color="primary",size='sm')
            ],
            gap="xs"
        )
    
    login_components = html.Div([
        dbc.Collapse(login_button,id=f"{login_id}_scheme_collapse",is_open=True),
        dbc.Collapse(user_profile,id=f"{login_id}_avatar_collapse",is_open=False)
    ])

    @callback(
        Output(f"{login_id}_scheme_collapse","is_open"),
        Output(f"{login_id}_avatar_collapse","is_open"),
        Output(f"{login_id}_avatar","children"),
        Output(f"{login_id}_store","data",allow_duplicate=True),
        Input(f"{login_id}_store","data"),
        Input(f"{login_id}_logout","n_clicks"),
        prevent_initial_call = True
    )
    def switch_login_status(store_data,_):
        """
        Replace login button with user profile, if logged in.
        """
        
        login_open = dash.no_update
        avatar_open = dash.no_update
        update_avatar = dash.no_update
        update_data = dash.no_update

        if ctx.triggered_id == f"{login_id}_store" and store_data != {}:
            update_avatar = store_data["badge"]
            login_open = False
            avatar_open = True

        elif ctx.triggered_id == f"{login_id}_logout":
            update_avatar = ""
            login_open = True
            avatar_open = False
            update_data = {}
        
        return login_open,avatar_open,update_avatar,update_data

    return login_modal,login_components,info_store

def user_profile_modal(login_id):
    """
    Create user profile|preference modal, a coninuation of the create_login_modal components.
    This modal allows users to customize their long-term search preferences or retrieve the existing
    profile from the server.

    Parameters
    ----------
    login_id : str
        Should be the login_id used in 'create_login_modal' function.

    Returns
    ----------

    """

    #PLACEHOLDER: There should be a logic, function to retrieve all categorical options from database

    cuisine_list = ["italian","chinese","india","japanese","mexican","thai"]

    dietary_list = ["vegan","keto","halal"]

    option_stacks = html.Div([
        dmc.MultiSelect(
            label="Select your favorite cuisine",
            placeholder="Select all you like!",
            id=f"{login_id}_cuisine_select",
            data=[{"value":item,"label":item} for item in cuisine_list],
            w=400,
            mb=10,
            comboboxProps={"withinPortal": False}
        ),
        dmc.Text('Dietary'),
        dcc.Dropdown(
            ['New York City', 'Montreal', 'San Francisco'],
            ['Montreal', 'San Francisco'],
            multi=True
        )
    ])


    profile_modal = dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle("Profile")),
                dbc.ModalBody(option_stacks),
            ],
            id=f"{login_id}_profile_modal",
            size="lg",
            is_open=False,
        )
    
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
    
    return profile_modal