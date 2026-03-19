import dash
from dash import html, Output, Input, State, ALL,MATCH, callback, ctx, dcc
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np

from .modals import recommendation_card,recipe_info_modal,recipe_statistic_modal
from . dummy_data import generate_recipe_statistic

def shared_filters(trigger_id, store_id):
    """
    The list of filter components that each recommendation functionality should have.

    Parameters
    ----------

    trigger_id: str
        The trigger id of the button which will be connected to the dcc.Store for filters.

    store_id : str
        The custom id of the dcc.Store that will store the selected filter info.

    Returns
    ----------

    filters: dash component
        Return a list of filters wrapped in dbc.Card
    
    dcc.Store:
        The component that store the info of the filters.
    """
    #PLACEHOLDER: There should be a logic, function to retrieve all categorical options from database
    meal_types = [
        "breakfast",
        "lunch",
        "dinner",
        "supper",
        "snack",
        "afternoon tea",
        "brunch",
        "picnic",
    ]

    prepare_time = [30, 60, 90, 120]
    prepare_marks = [str(item) for item in prepare_time]
    prepare_marks[0] = "≤" + prepare_marks[0]
    prepare_marks[-1] = "≥" + prepare_marks[-1]
    prepare_marks = dict(zip(prepare_time, prepare_marks))

    cooking_time = [15, 30, 60, 90]
    cook_marks = [str(item) for item in cooking_time]
    cook_marks[0] = "≤" + cook_marks[0]
    cook_marks[-1] = "≥" + cook_marks[-1]
    cook_marks = dict(zip(cooking_time, cook_marks))

    like_ingredients = [
        "fish",
        "pork",
        "beef",
        "lamb",
        "cucumber",
        "cabbage",
        "olive oil",
        "tomato",
        "potato",
        "peanut",
        "celery",
    ]

    dislike_ingredients = [
        "fish",
        "pork",
        "beef",
        "lamb",
        "cucumber",
        "cabbage",
        "olive oil",
        "tomato",
        "potato",
        "peanut",
        "celery",
    ]

    skill_level = ["beginner", "intermediate", "advanced"]

    cooking_method = [
        "baking",
        "grilling",
        "roasting",
        "sauteing",
        "frying",
        "broiling",
        "sous vide",
        "poaching",
        "simmering",
        "boiling",
        "steaming",
        "braising",
        "stewing",
    ]

    calory_range = [100, 400, 800, 1500, 2000]
    calory_marks = [str(item) for item in calory_range]
    calory_marks[0] = "≤" + calory_marks[0]
    calory_marks[-1] = "≥" + calory_marks[-1]
    calory_marks = dict(zip(calory_range, calory_marks))

    macro_nutrients = {
        "cholesterol": ([0, 100], "mg"),
        "carbohydrates": ([10, 100], "g"),
        "protein": ([10, 100], "g"),
        "fat": ([10, 100], "g"),
        "saturated_fats": ([10, 100], "g"),
        "fiber": ([10, 100], "g"),
        "sugar": ([10, 100], "g"),
    }

    micro_nutrients = {
        "vitamins": {
            "A": ([0, 100], "mg"),
            "B1(thiamin)": ([0, 100], "mg"),
            "B3 (niacin)": ([0, 100], "mg"),
            "B6": ([0, 100], "mg"),
            "C": ([0, 100], "mg"),
        },
        "minerals": {
            "Sodium": ([0, 100], "mg"),
            "Calcium": ([0, 100], "mg"),
            "Copper": ([0, 100], "mg"),
            "Iron": ([0, 100], "mg"),
            "Magnesium": ([0, 100], "mg"),
            "Potassium": ([0, 100], "mg"),
        },
    }
    ######

    # lambda function for creating filter header
    filter_header = lambda label,name,filter_type,exact="exact": dmc.Group(
        [   
            dbc.Switch(id={"name": name,"type":"filter_control","filter":filter_type},value=False),
            dmc.Text(label, fw=500, size="lg"), 
            dbc.Collapse(
                dbc.RadioItems(
                    options=[
                        {"label": "Exact filter", "value": "exact"},
                        {"label": "Priority filter", "value": "priority"},
                    ],
                    value=exact,
                    id={"type": "exact_switch", "name": name,"filter":filter_type},
                    inline=True,
                ),
                is_open=False,
                id = {"name": name,"type":"filter_control","filter":filter_type,"collapse":0}
            )
        ],
        align="flex-end",gap="xs"
    )

    # lambda function for creating subslider for nutrients
    create_slider = lambda prefix,info,name,filter_type="filter_slider": dmc.Group([
        dbc.Label(prefix + info[0] + ':'),
        dcc.RangeSlider(
            min(info[1][0]),
            max(info[1][0]),
            value=[min(info[1][0]),max(info[1][0])],
            marks={
                min(info[1][0]): str(min(info[1][0])) + info[1][1],
                max(info[1][0]): str(max(info[1][0])) + info[1][1]
            },
            id={"filter": filter_type, "name": name, "sub_name":info[0]},
            className="w-60"
        )
    ],justify="space-between",className="mb-2")


    #NOTE: 3 type of filter: filter_checklist,filter_slider,filter_dropdown,
    
    filters = dbc.Card(
        html.Div(
            [   
                dmc.Text("Choose your filters:", size="xl", fw=700, td="underline"),
                dbc.Switch(id="enable_filters",label = "enable/disable all filters",value=False),
                html.Hr(
                    className="my-1"
                ),

                filter_header("Meal type","meal_type","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in meal_types],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "meal_type"},
                    ),
                    is_open = False,
                    id = {"name": "meal_type","type":"filter_control","filter":"filter_checklist","collapse":1}
                ),
                html.Hr(),

                filter_header("Preparation time (min)","prepare_time","filter_slider"),
                dbc.Collapse(
                    dcc.RangeSlider(
                        min(prepare_time),
                        max(prepare_time),
                        step=5,
                        value=[min(cooking_time),max(prepare_time)],
                        marks=prepare_marks,
                        id={"filter": "filter_slider", "name": "prepare_time"},
                        className="w-75",
                    ),
                    is_open = False,
                    id = {"name": "prepare_time","type":"filter_control","filter": "filter_slider","collapse":1}
                ),
                html.Hr(),

                filter_header("Cooking time (min)","cooking_time","filter_slider"),
                dbc.Collapse(
                    dcc.RangeSlider(
                        min(cooking_time),
                        max(cooking_time),
                        step=5,
                        value=[min(cooking_time),max(cooking_time)],
                        marks=cook_marks,
                        id={"filter": "filter_slider", "name": "cooking_time"},
                        className="w-75",
                    ),
                    is_open = False,
                    id = {"name": "cooking_time","type":"filter_control","filter": "filter_slider","collapse":1}
                ),
                html.Hr(),

                filter_header("Preferred ingredients","like_ingredient","filter_dropdown"),
                dbc.Collapse(
                    dcc.Dropdown(
                        like_ingredients,
                        id={"filter": "filter_dropdown", "name": "like_ingredient"},
                        multi=True,
                        maxHeight=300,
                        className="w-75",
                    ),
                    is_open = False,
                    id = {"name": "like_ingredient","type":"filter_control","filter": "filter_dropdown","collapse":1}
                ),
                html.Hr(),

                filter_header("Dislike ingredients","dislike_ingredient","filter_dropdown"),
                dbc.Collapse(
                    dcc.Dropdown(
                        dislike_ingredients,
                        id={"filter": "filter_dropdown", "name": "dislike_ingredient"},
                        multi=True,
                        maxHeight=300,
                        className="w-75",
                    ),
                    is_open = False,
                    id = {"name": "dislike_ingredient","type":"filter_control","filter": "filter_dropdown","collapse":1}
                ),
                html.Hr(),

                filter_header("Skill level","skill_level","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in skill_level],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "skill_level"},
                    ),
                    is_open = False,
                    id = {"name": "skill_level","type":"filter_control","filter": "filter_checklist","collapse":1}
                ),
                html.Hr(),

                filter_header("Cooking method","cook_method","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in cooking_method],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "cook_method"},
                    ),
                    is_open = False,
                    id = {"name": "cook_method","type":"filter_control","filter": "filter_checklist","collapse":1}
                ),
                html.Hr(),

                filter_header("Calory range (kcal)","calory","filter_slider","priority"),
                dbc.Collapse(
                    dcc.RangeSlider(
                        min(calory_range),
                        max(calory_range),
                        value=[min(calory_range),max(calory_range)],
                        marks=calory_marks,
                        id={"filter": "filter_slider", "name": "calory"},
                        className="w-75",
                    ),
                    is_open = False,
                    id = {"name": "calory","type":"filter_control","filter": "filter_slider","collapse":1}
                ),
                html.Hr(),

                filter_header("Macro-nutrients","macro_nutrient","filter_slider","priority"),
                dbc.Collapse(
                    html.Div([
                        create_slider('',info,'macro_nutrient') for info in macro_nutrients.items()
                    ]),
                    is_open = False,
                    id = {"name": "macro_nutrient","type":"filter_control","filter": "filter_slider","collapse":1}
                ),
                html.Hr(),

                filter_header("Micro-nutrients: Vitamins","vitamin_nutrient","filter_slider","priority"),
                dbc.Collapse(
                    html.Div([
                        create_slider("Vitamin ",info,"vitamin_nutrient") 
                        for info in micro_nutrients['vitamins'].items()
                    ]),
                    is_open = False,
                    id = {"name": "vitamin_nutrient","type":"filter_control","filter": "filter_slider","collapse":1}
                ),
                html.Hr(),

                filter_header("Micro-nutrients: Minerals","mineral_nutrient","filter_slider","priority"),
                dbc.Collapse(
                    html.Div([
                        create_slider('',info,'mineral_nutrient') 
                        for info in micro_nutrients["minerals"].items()
                    ]),
                    is_open = False,
                    id = {"name": "mineral_nutrient","type":"filter_control","filter": "filter_slider","collapse":1}
                )


            ],
            className="m-2 dbc",
        )
    )

    # store the output of filters
    store_component = dcc.Store(id=store_id,data={})

    @callback(
        Output({"name": ALL,"type":"filter_control","filter":ALL},"value"),
        Input("enable_filters","value"),
        prevent_intial_call = True
    )
    def enable_disable_filters(trigger_bool):
        """
        Enable/disable all filters
        """
        output_len = len(ctx.outputs_list)
        return [trigger_bool]*output_len
    
    @callback(
        Output({"name": MATCH,"filter":MATCH,"type":"filter_control","collapse":ALL},"is_open"),
        Input({"name": MATCH,"filter":MATCH,"type":"filter_control"},"value"),
        prevent_intial_call = True
    )
    def open_filter_content(trigger_bool):
        """
        Sync open/close collapse component with filter activation switch.
        """
        output_len = len(ctx.outputs_list)
        return [trigger_bool]*output_len

    @callback(
        Output(store_id,"data"),
        inputs = dict(click = Input(trigger_id,"n_clicks")),
        state = dict(
            enable_switches = State({"type":"filter_control", "name": ALL,"filter":ALL},"value"),
            priority_types = State({"type": "exact_switch", "name": ALL,"filter":ALL},"value"),
            checklists = State({"filter": "filter_checklist", "name": ALL},"value"),
            dropdowns = State({"filter": "filter_dropdown", "name": ALL},"value"),
            sliders = State({"filter": "filter_slider", "name": ALL},"value"),
            sub_sliders = State({"filter": "filter_slider", "name": ALL, "sub_name":ALL},"value"),
        ),
        prevent_intial_call = True
    )
    def store_filters_info(click,enable_switches,priority_types,checklists,dropdowns,sliders,sub_sliders):
        """
        Store filter information into a dictionary.

        Returns
        ----------
        dict:
            Contain filter information in a nested dictionary, where the first level is the 
            filter type: [filter_checklist,filter_dropdown,filter_slider,filter_sub_slider]
        """
        if click>0:
            filter_dict = dict()

            context_dict = ctx.args_grouping

            switch_df = pd.json_normalize(context_dict["enable_switches"])
            priority_df = pd.json_normalize(context_dict["priority_types"])
            checklists_df = pd.json_normalize(context_dict["checklists"])
            dropdowns_df = pd.json_normalize(context_dict["dropdowns"])
            sliders_df = pd.json_normalize(context_dict["sliders"])
            sub_sliders_df = pd.json_normalize(context_dict["sub_sliders"])

            switch_df = switch_df.loc[switch_df['value']==True]  #get only filter that turned on
            switch_df = pd.merge(
                switch_df[['id.filter','id.name']],
                priority_df[['id.filter','id.name','value']],
                how='inner',on=['id.filter','id.name']
            )
            switch_df.rename(columns={'value':'priority_type'},inplace=True)

            filter_df = pd.DataFrame()

            if switch_df.shape[0] == 0:
                return filter_dict
            else:
                if switch_df['id.filter'].eq("filter_checklist").any():  # Handle checklist data
                    check_df = pd.merge(
                        switch_df[['id.filter','id.name','priority_type']],
                        checklists_df[['id.filter','id.name','value']],
                        how='inner',on=['id.filter','id.name']
                    )
                    filter_df = pd.concat([filter_df,check_df])

                if switch_df['id.filter'].eq("filter_dropdown").any():  # Handle dropdown data
                    check_df = pd.merge(
                        switch_df[['id.filter','id.name','priority_type']],
                        dropdowns_df[['id.filter','id.name','value']],
                        how='inner',on=['id.filter','id.name']
                    )
                    filter_df = pd.concat([filter_df,check_df])

                if switch_df['id.filter'].eq("filter_slider").any():  # Handle slider data  
                    # normal slider
                    check_df = pd.merge(
                        switch_df[['id.filter','id.name','priority_type']],
                        sliders_df[['id.filter','id.name','value']],
                        how='inner',on=['id.filter','id.name']
                    )
                    if check_df.shape[0] >0:
                        filter_df = pd.concat([filter_df,check_df])

                    # nutrient slider
                    check_df = pd.merge(
                        switch_df[['id.filter','id.name','priority_type']],
                        sub_sliders_df[['id.filter','id.name','id.sub_name','value']],
                        how='inner',on=['id.filter','id.name']
                    )
                    if check_df.shape[0] >0:
                        filter_df = pd.concat([filter_df,check_df])

                filter_df.rename(columns = {
                    "id.filter":"filter_type",
                    "id.name":"filter_name",
                    "id.sub_name":"filter_sub_name",
                    "value":"filter_value"},
                    inplace=True
                    )
                filter_df.reset_index(drop=True,inplace=True)
                filter_dict = filter_df.to_dict()

            return filter_dict
        else:
            return dash.no_update
    
    return filters,store_component


def recommendation_filters(search_id,profile_store_id,filter_store_id):
    """
    Recommendation settings and output layout.

    Parameters
    ----------

    search_id: str
        The id of the search button.

    profile_store_id : str
        The id of the dcc.Store that store profile preferences.

    filter_store_id : str
        The id of the dcc.Store that store filter values.

    Returns
    ----------

    output_components: dash component
        Return a list of parameters for generating output
    """

    output_components = html.Div(
        [   
            # Store recommendation data
            dcc.Store(data = {},id = f"{search_id}_recommendation_store"),
            
            # Recommendation output modals
            recipe_info_modal(search_id),
            recipe_statistic_modal(search_id),

            dbc.Row(
                [
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Number of candidate recipes:",
                                id = f"{search_id}_candidate",
                                min=50, max=200,value=50, className="w-75"
                            )
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Number of top rank recommendations:",
                                id = f"{search_id}_n_top",
                                min=1, max=10,value=5, className="w-75"
                            )
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Number of least likely recommendations:",
                                id = f"{search_id}_n_bottom",
                                min=1, max=5,value=3, className="w-75"
                            )
                        ],
                        width=4,
                    )
                ],align="end"
            ),
            dbc.Button("Search", id = search_id, color="primary", className="mt-1 w-25",n_clicks = 0),
            html.Hr(),
            dmc.Text('Legend:', fw=700,size="lg"),
            dmc.Group(
                [dmc.Badge("Prioritize filter condition",variant="outline",color = 'lime'),
                 dmc.Text("A match"),
                 dmc.Badge("Prioritize filter condition",variant="outline",color = 'red'),
                 dmc.Text("Not a match")
                 ]
            ),
            dmc.Group(
                [dmc.Badge("No. of nutrient match",variant="outline",color = 'lime'),
                 dmc.Text("High match (>80%)"),
                 dmc.Badge("No. of nutrient match",variant="outline",color = 'yellow'),
                 dmc.Text("Medium match (35-80%)")
                 ]
            ),
            dmc.Group(
                [dmc.Badge("No. of nutrient match",variant="outline",color = 'red'),
                 dmc.Text("Low match (<35%)"),
                 dmc.Badge("Exact filter condition",variant="filled",color = 'lime'),
                 dmc.Text("A match")
                 ]
            ),

            html.Hr(),
            dcc.Loading(html.Div(id=f'{search_id}_recommendation_outputs')),
            html.Br()
        ],
        className="m-2 dbc",
    )

    @callback(
        [
            Output(f"{search_id}_recommendation_outputs","children"),
            Output(f"{search_id}_recommendation_store","data")
         ],
        inputs = dict(
            search = Input(search_id,"n_clicks"),
            # filter_dict must be Input to sync when click Search button
            filter_dict = Input(filter_store_id,"data")  
        ),
        state = dict(
            
            profile_dict = State(profile_store_id,"data"),
            n_candidate = State(f"{search_id}_candidate","value"),
            n_top = State(f"{search_id}_n_top","value"),
            n_bottom = State(f"{search_id}_n_bottom","value")
        ),
        prevent_initial_call = True
    )
    def generate_recommendation(
            search,filter_dict,profile_dict,
            n_candidate,n_top,n_bottom
        ):
        """
        Generating recommendations based on parameters,profile and filters.
        """
        recommendation_data = {}
        #PLACEHOLDER: Logic to generate recommendation and its statistics from database in the server
        if filter_dict!={}:
            recipe_statistics = generate_recipe_statistic(filter_dict,profile_dict,n_candidate)

            output_list = []  # Output top + bottom recommendation
            output_list.extend(recipe_statistics[:n_top])
            output_list.extend(recipe_statistics[-n_bottom:])
            rank_list = list(range(1,1+n_top))
            rank_list.extend(list(range(n_candidate+1-n_bottom,n_candidate+1)))

            recommendation_data["recipe_statistics"] = recipe_statistics

            #TODO: logic to create recommendation model statistics over the list of recommended items
            
            health_score = round(np.random.rand(),3)
            diveristy_score = round(np.random.rand(),3)
            serendipity_score = round(np.random.rand(),3)
            precision_score =  round(np.random.rand(),3)
            recommendation_data["model_statistics"] = {
                "average_health_score":health_score,
                "diversity_score":diveristy_score,
                "serendipity_score":serendipity_score,
                "Average Precision@k":precision_score
            }
        ###

            recommendations = html.Div([
                dmc.Text('Recommendation statistics', fw=700,size="lg"),
                dmc.Text(f'Average health score: {health_score}'),
                dmc.Text(f'Diversity score: {diveristy_score}'),
                dmc.Text(f'Serendipity score: {serendipity_score}'),
                dmc.Text(f'Average Precision@k: {precision_score}'),
                html.Hr(),
                dmc.Group(
                    children=[recommendation_card(item,rank) for rank,item in zip(rank_list,output_list)],
                    gap="xs",     
                    wrap="wrap",
                    justify="flex-start")
                    
            ])

            return recommendations,recommendation_data
        else:
            return [],recommendation_data
        
    @callback(
        Output(f"{search_id}_info_modal","is_open"),
        Output(f"{search_id}_info_modal_body","children"),
        Input({"recipe_id":ALL,"type":"recipe_info"},"n_clicks"),
        State(f"{search_id}_info_modal","is_open"),
        State(f"{search_id}_recommendation_store","data"),
        prevent_initial_call = True
    )
    def display_recipe_info(clicks,is_open,rec_data):
        """
        Generate recommended recipe info card.
        """

        if sum(clicks) == 0:  # handlle intial state of buttons
            return dash.no_update, dash.no_update
        else:
            recipe_id = dash.ctx.triggered_id["recipe_id"]

            #TODO: retrieve recipe information using recipe_id from database
            df = pd.DataFrame(rec_data["recipe_statistics"])

            df = df.loc[df["recipe_id"] == recipe_id]
            recipe_name = df['recipe_name'].values[0]

            recipe_information = dcc.Markdown(
                f"""
                ## {recipe_name} - ID: {recipe_id}

                <recipe description>

                ### Cooking instruction:
                * Step 1
                * Step 2
                * Step 3

                Category taggings: tag_1, tag_2, tag_3

                <Nutrient facts>

                ...
                """,
                className="card-text"
            )

            return not is_open,recipe_information
        
    @callback(
        Output(f"{search_id}_stat_modal","is_open"),
        Output(f"{search_id}_stat_modal_body","children"),
        Input({"recipe_id":ALL,"type":"recipe_statistic"},"n_clicks"),
        State(f"{search_id}_stat_modal","is_open"),
        State(f"{search_id}_recommendation_store","data"),
        prevent_initial_call = True
    )
    def display_recipe_statistic(clicks,is_open,rec_data):
        """
        Generate recommended recipe statistics card.
        """

        if sum(clicks) == 0:  # handlle intial state of buttons
            return dash.no_update, dash.no_update
        else:
            recipe_id = dash.ctx.triggered_id["recipe_id"]

            #TODO: retrieve recipe statistic using recipe_id from database
            df = pd.DataFrame(rec_data["recipe_statistics"])

            df = df.loc[df["recipe_id"] == recipe_id]
            recipe_name = df['recipe_name'].values[0]

            long_term = df['long_term'].values[0]
            short_term = df['short_term'].values[0]
            average_score = df['average_metric'].values[0]

            recipe_information = dcc.Markdown(
                f"""
                ## {recipe_name} - ID: {recipe_id}
                
                Evaluation matching scores:

                Long-term preference score: {round(long_term,3)}

                Short-term filters score: {round(short_term,3)}

                Average score: {round(average_score,3)}

                ...
                """,
                className="card-text"
            )

            return not is_open,recipe_information

    return output_components
