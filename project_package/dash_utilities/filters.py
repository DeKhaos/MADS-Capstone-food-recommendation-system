import os,ast
from pathlib import Path

import dash
from dash import html, Output, Input, State, ALL,MATCH, callback, ctx, dcc
import dash_mantine_components as dmc
import dash_bootstrap_components as dbc
import pandas as pd
import numpy as np
import json

from .modals import recommendation_card,recipe_info_modal,recipe_statistic_modal
from .dummy_data import generate_recipe_statistic
from ..data_preprocessing.utils import chroma_filter_operator
from ..data_preprocessing.default import USER_SEARCH_TEMPLATE,OPERATOR_MAPPING,TRAIT_MAPPING
from ..modeling.recommendation_utils import recommendation_doc_id_pipeline
from .in_memory_variables import (
    _app_data
    )


root_directory = Path(os.getcwd())

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

    constraint_df = pd.read_csv(root_directory / 'data/processed/ui_feature_constraints.csv')  # get constraint info from processed csv
    constraint_df['value'] = constraint_df['value'].apply(ast.literal_eval)
    
    cuisine_list = constraint_df.loc[constraint_df['feature']=='cuisine','value'].tolist()[0]
    cooking_method_list = constraint_df.loc[constraint_df['feature']=='cooking_method','value'].tolist()[0]
    difficulty_list = constraint_df.loc[constraint_df['feature']=='difficulty','value'].tolist()[0]
    like_ingredients = constraint_df.loc[constraint_df['feature']=='ingredients','value'].tolist()[0]
    dislike_ingredients = constraint_df.loc[constraint_df['feature']=='ingredients','value'].tolist()[0]
    
    calorie_range = [100, 1000, 2000, 3000, 4000, 5000]
    calorie_marks = [str(item) for item in calorie_range]
    calorie_marks[0] = "≤" + calorie_marks[0]
    calorie_marks[-1] = "≥" + calorie_marks[-1]
    calorie_marks = dict(zip(calorie_range, calorie_marks))

    prepare_time = [60, 120, 720, 1440]
    prepare_marks = [str(item) for item in prepare_time]
    prepare_marks[0] = "≤" + prepare_marks[0]
    prepare_marks = dict(zip(prepare_time, prepare_marks))

    cooking_time = [60, 240, 1440, 4320]
    cook_marks = [str(item) for item in cooking_time]
    cook_marks[0] = "≤" + cook_marks[0]
    cook_marks = dict(zip(cooking_time, cook_marks))

    total_cook_time = [60, 240, 1440, 4320]
    total_cook_marks = [str(item) for item in total_cook_time]
    total_cook_marks[0] = "≤" + total_cook_marks[0]
    total_cook_marks = dict(zip(total_cook_time, total_cook_marks))

    who_score = constraint_df.loc[constraint_df['feature']=='who_score','value'].tolist()[0]
    fsa_score = constraint_df.loc[constraint_df['feature']=='fsa_score','value'].tolist()[0]

    protein_content_list = constraint_df.loc[constraint_df['feature']=='protein_content','value'].tolist()[0]
    fiber_content_list = constraint_df.loc[constraint_df['feature']=='fiber_content','value'].tolist()[0]
    fat_content_list = constraint_df.loc[constraint_df['feature']=='fat_content','value'].tolist()[0]
    carbohydrate_content_list = constraint_df.loc[constraint_df['feature']=='carbohydrate_content','value'].tolist()[0]
    sodium_content_list = constraint_df.loc[constraint_df['feature']=='sodium_content','value'].tolist()[0]

    #PLACEHOLDER: uncomment to enable macro/micro nutrient
    # macro_nutrients = {
    #     "cholesterol": ([0, 100], "mg"),
    #     "carbohydrates": ([10, 100], "g"),
    #     "protein": ([10, 100], "g"),
    #     "fat": ([10, 100], "g"),
    #     "saturated_fats": ([10, 100], "g"),
    #     "fiber": ([10, 100], "g"),
    #     "sugar": ([10, 100], "g"),
    # }

    # micro_nutrients = {
    #     "vitamins": {
    #         "A": ([0, 100], "mg"),
    #         "B1(thiamin)": ([0, 100], "mg"),
    #         "B3 (niacin)": ([0, 100], "mg"),
    #         "B6": ([0, 100], "mg"),
    #         "C": ([0, 100], "mg"),
    #     },
    #     "minerals": {
    #         "Sodium": ([0, 100], "mg"),
    #         "Calcium": ([0, 100], "mg"),
    #         "Copper": ([0, 100], "mg"),
    #         "Iron": ([0, 100], "mg"),
    #         "Magnesium": ([0, 100], "mg"),
    #         "Potassium": ([0, 100], "mg"),
    #     },
    # }
    ######

    # lambda function for creating filter header
    filter_header = lambda label,name,filter_type,exact="exact",disable_priority=False: dmc.Group(
        [   
            dbc.Switch(id={"name": name,"type":"filter_control","filter":filter_type},value=False),
            dmc.Text(label, fw=500, size="lg"), 
            dbc.Collapse(
                dbc.RadioItems(
                    options=[
                        {"label": "Exact filter", "value": "exact"},
                        {"label": "Priority filter", "value": "priority",'disabled':disable_priority},
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


    #NOTE: There are 3 type of filters: filter_checklist,filter_slider,filter_dropdown,
    
    filters = dbc.Card(
        html.Div(
            [   
                dmc.Text("Choose your filters:", size="xl", fw=700, td="underline"),
                dbc.Switch(id="enable_filters",label = "enable/disable all filters",value=False),
                html.Hr(
                    className="my-1"
                ),

                filter_header("Cuisine","cuisine_type","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in cuisine_list],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "cuisine_type"},
                    ),
                    is_open = False,
                    id = {"name": "cuisine_type","type":"filter_control","filter":"filter_checklist","collapse":1}
                ),
                html.Hr(),

                filter_header("Cooking method","cook_method","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in cooking_method_list],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "cook_method"},
                    ),
                    is_open = False,
                    id = {"name": "cook_method","type":"filter_control","filter": "filter_checklist","collapse":1}
                ),
                html.Hr(),

                filter_header("Difficulty level","difficulty_level","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in difficulty_list],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "difficulty_level"},
                    ),
                    is_open = False,
                    id = {"name": "difficulty_level","type":"filter_control","filter": "filter_checklist","collapse":1}
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

                filter_header("Dislike ingredients","dislike_ingredient","filter_dropdown",disable_priority=True),
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

                filter_header("Calorie range (kcal)","calorie","filter_slider",disable_priority=True),
                dbc.Collapse(
                    dcc.RangeSlider(
                        min(calorie_range),
                        max(calorie_range),
                        value=[min(calorie_range),max(calorie_range)],
                        marks=calorie_marks,
                        id={"filter": "filter_slider", "name": "calorie"},
                        className="w-75",
                    ),
                    is_open = False,
                    id = {"name": "calorie","type":"filter_control","filter": "filter_slider","collapse":1}
                ),
                html.Hr(),

                filter_header("Preparation time (min)","prepare_time","filter_slider",disable_priority=True),
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

                filter_header("Cooking time (min)","cooking_time","filter_slider",disable_priority=True),
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

                filter_header("Total time (min)","total_cook_time","filter_slider",disable_priority=True),
                dbc.Collapse(
                    dcc.RangeSlider(
                        min(total_cook_time),
                        max(total_cook_time),
                        step=5,
                        value=[min(total_cook_time),max(total_cook_time)],
                        marks=total_cook_marks,
                        id={"filter": "filter_slider", "name": "total_cook_time"},
                        className="w-75",
                    ),
                    is_open = False,
                    id = {"name": "total_cook_time","type":"filter_control","filter": "filter_slider","collapse":1}
                ),
                html.Hr(),
                
                filter_header("WHO health score","who_score","filter_slider",disable_priority=True),
                dbc.Collapse(
                    dcc.RangeSlider(
                        min(who_score),
                        max(who_score),
                        step=1,
                        value=[min(who_score),max(who_score)],
                        id={"filter": "filter_slider", "name": "who_score"},
                        className="w-75",
                    ),
                    is_open = False,
                    id = {"name": "who_score","type":"filter_control","filter": "filter_slider","collapse":1}
                ),
                html.Hr(),

                filter_header("FSA health score","fsa_score","filter_slider",disable_priority=True),
                dbc.Collapse(
                    dcc.RangeSlider(
                        min(fsa_score),
                        max(fsa_score),
                        step=1,
                        value=[min(fsa_score),max(fsa_score)],
                        id={"filter": "filter_slider", "name": "fsa_score"},
                        className="w-75",
                    ),
                    is_open = False,
                    id = {"name": "fsa_score","type":"filter_control","filter": "filter_slider","collapse":1}
                ),
                html.Hr(),

                filter_header("Protein content","protein_content","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in protein_content_list],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "protein_content"},
                    ),
                    is_open = False,
                    id = {"name": "protein_content","type":"filter_control","filter":"filter_checklist","collapse":1}
                ),
                html.Hr(),

                filter_header("Fiber content","fiber_content","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in fiber_content_list],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "fiber_content"},
                    ),
                    is_open = False,
                    id = {"name": "fiber_content","type":"filter_control","filter":"filter_checklist","collapse":1}
                ),
                html.Hr(),

                filter_header("Fat content","fat_content","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in fat_content_list],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "fat_content"},
                    ),
                    is_open = False,
                    id = {"name": "fat_content","type":"filter_control","filter":"filter_checklist","collapse":1}
                ),
                html.Hr(),

                filter_header("Carbohydrate content","cab_content","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in carbohydrate_content_list],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "cab_content"},
                    ),
                    is_open = False,
                    id = {"name": "cab_content","type":"filter_control","filter":"filter_checklist","collapse":1}
                ),
                html.Hr(),

                filter_header("Sodium content","sodium_content","filter_checklist"),
                dbc.Collapse(
                    dbc.Checklist(
                        options=[{"label": item, "value": item} for item in sodium_content_list],
                        inline=True,
                        id={"filter": "filter_checklist", "name": "sodium_content"},
                    ),
                    is_open = False,
                    id = {"name": "sodium_content","type":"filter_control","filter":"filter_checklist","collapse":1}
                ),
                html.Hr(),

                #PLACEHOLDER: uncomment to enable macro/micro nutrient
                # html.Hr(),
                # filter_header("Macro-nutrients","macro_nutrient","filter_slider","priority"),
                # dbc.Collapse(
                #     html.Div([
                #         create_slider('',info,'macro_nutrient') for info in macro_nutrients.items()
                #     ]),
                #     is_open = False,
                #     id = {"name": "macro_nutrient","type":"filter_control","filter": "filter_slider","collapse":1}
                # ),
                # html.Hr(),

                # filter_header("Micro-nutrients: Vitamins","vitamin_nutrient","filter_slider","priority"),
                # dbc.Collapse(
                #     html.Div([
                #         create_slider("Vitamin ",info,"vitamin_nutrient") 
                #         for info in micro_nutrients['vitamins'].items()
                #     ]),
                #     is_open = False,
                #     id = {"name": "vitamin_nutrient","type":"filter_control","filter": "filter_slider","collapse":1}
                # ),
                # html.Hr(),

                # filter_header("Micro-nutrients: Minerals","mineral_nutrient","filter_slider","priority"),
                # dbc.Collapse(
                #     html.Div([
                #         create_slider('',info,'mineral_nutrient') 
                #         for info in micro_nutrients["minerals"].items()
                #     ]),
                #     is_open = False,
                #     id = {"name": "mineral_nutrient","type":"filter_control","filter": "filter_slider","collapse":1}
                # )


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
            # sub_sliders_df = pd.json_normalize(context_dict["sub_sliders"])  #PLACEHOLDER: uncomment to enable macro/micro nutrient

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

                    # nutrient slider  #PLACEHOLDER: uncomment to enable macro/micro nutrient
                    # check_df = pd.merge(
                    #     switch_df[['id.filter','id.name','priority_type']],
                    #     sub_sliders_df[['id.filter','id.name','id.sub_name','value']],
                    #     how='inner',on=['id.filter','id.name']
                    # )
                    # if check_df.shape[0] >0:
                    #     filter_df = pd.concat([filter_df,check_df])

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
            
            html.Hr(),
            dmc.Text("Search pipeline settings:", size="xl", fw=700, td="underline"),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Number of candidate:",
                                id = f"{search_id}_candidate",
                                min=200, max=2000,value=300, className="w-75"
                            ),
                            dbc.Tooltip(
                                "Number of candidate retrieved from Chroma vectorstore",
                                target=f"{search_id}_candidate"
                            )
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Number of recommendations:",
                                id = f"{search_id}_n_recommendations",
                                min=10, max=200,value=50, className="w-75"
                            ),
                            dbc.Tooltip(
                                "Number of recipes generated from the recommendation model",
                                target=f"{search_id}_n_recommendations"
                            )
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Number of similar users:",
                                id = f"{search_id}_n_user",
                                min=5, max=50,value=10, className="w-75"
                            ),
                            dbc.Tooltip(
                                """Number of users similar to the profile to retrieve. 
                                This is used for collaboration and hybrid models""",
                                target=f"{search_id}_n_user"
                            )
                        ],
                        width=4,
                    )
                ],align="end"
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Top n to retrieve:",
                                id = f"{search_id}_n_top",
                                min=1, max=20,value=5, className="w-75"
                            ),
                            dbc.Tooltip(
                                """Retrieve n top recipe from the list of ranked 
                                recommendations which have the highest scores""",
                                target=f"{search_id}_n_top"
                            )
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Bottom n to retrieve:",
                                id = f"{search_id}_n_bottom",
                                min=1, max=10,value=3, className="w-75"
                            ),
                            dbc.Tooltip(
                                """Retrieve n bottom recipe from the list of ranked 
                                recommendations which have the lowest scores""",
                                target=f"{search_id}_n_bottom"
                            )
                        ],
                        width=4,
                    )
                ],align="end"
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [   
                            dmc.Text("Recommendation model:", fw=500, size="lg",className="mt-1"),
                            dbc.RadioItems(
                                options=[
                                    {"label": "BM25", "value": "item-content",
                                     "label_id":f"{search_id}_item-content_tooltip"},
                                    {"label": "SVD", "value": "collab",
                                     "label_id":f"{search_id}_collab_tooltip"},
                                    {"label": "LightFM", "value": "hybrid",
                                     "label_id":f"{search_id}_hybrid_tooltip"}
                                ],
                                value="item-content",
                                id=f"{search_id}_rec_model_switch",
                                inline=True,
                                className="mb-1"
                            ),
                            dbc.Tooltip(
                                "BM25 is a item-content filtering model.",
                                target=f"{search_id}_item-content_tooltip"
                            ),
                            dbc.Tooltip(
                                "SVD is a user-item interaction filtering model.",
                                target=f"{search_id}_collab_tooltip"
                            ),
                            dbc.Tooltip(
                                """LightFM is a hybrid model which takes into account the
                                context of item content and user.""",
                                target=f"{search_id}_hybrid_tooltip"
                            )
                        ],
                        width=4,
                    )
                ],align="end"
            ),
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Profile weight:",
                                id = f"{search_id}_profile_w",
                                min=0, max=10,value=1.5, 
                                decimalScale=2,step=0.1,
                                className="w-75"
                            ),
                            dbc.Tooltip(
                                """The bias weight use to pull the Chroma retrieval results toward user profile. 
                                Should be higher than filter weight.""",
                                target=f"{search_id}_profile_w"
                            )
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Filters weight:",
                                id = f"{search_id}_filters_w",
                                min=0, max=10,value=0.75,
                                decimalScale=2,step=0.1,
                                className="w-75"
                            ),
                            dbc.Tooltip(
                                """The bias weight use to pull the Chroma retrieval results toward the chosen filter with
                                'Priority filter' option. Should be lower than Profile weight.""",
                                target=f"{search_id}_filters_w"
                            )
                        ],
                        width=4,
                    )
                ],align="end"
            ),  
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "ReRanker pull force:",
                                id = f"{search_id}_ranker_bias_w",
                                min=0, max=5,value=0.35, 
                                decimalScale=2,step=0.05,
                                className="w-75"
                            ),
                            dbc.Tooltip(
                                """When reranking the recommendation, we are also taking into account the context
                                of bias used in Chroma vectorstore retrieval step by introducing the bias pull force.
                                This will penalize the ranking score for negative bias, and increase score for positive
                                bias when evaluating the retrieved recipes. The recommended value is [0,1] but can
                                go higher for stronger bias effect.
                                """,
                                target=f"{search_id}_ranker_bias_w"
                            )
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [
                            dmc.NumberInput(
                                label = "Health score weight:",
                                id = f"{search_id}_health_w",
                                min=0, max=1,value=0,
                                decimalScale=2,step=0.05,
                                className="w-75"
                            ),
                            dbc.Tooltip(
                                """
                                Rescale the ranking result to prioritize healthy recipes by introducing
                                the health score to it. The higher the stronger the effect, at 0 there is no rescale.
                                """,
                                target=f"{search_id}_health_w"
                            )
                        ],
                        width=4,
                    ),
                    dbc.Col(
                        [   
                            dmc.Text("Healthy recipe criteria:", fw=500, size="lg",className="mt-1"),
                            dbc.RadioItems(
                                options=[
                                    {"label": "WHO", "value": "who_score"},
                                    {"label": "FSA", "value": "fsa_score"}
                                ],
                                value="who_score",
                                id=f"{search_id}_health_score_switch",
                                inline=True,
                                className="mb-1"
                            ),
                            dbc.Tooltip(
                                "Choose the type of score for ranking. Only have an effect if health score weight >0",
                                target=f"{search_id}_health_score_switch"
                            ),
                        ],
                        width=4,
                    )
                ],align="end"
            ),


            dbc.Button("Search", id = search_id, color="primary", className="mt-3 w-25",n_clicks = 0),
            html.Hr(),
            dmc.Text('Legend:', fw=700,size="lg"),
            dmc.Group(
                [dmc.Badge("Prioritize filter condition",variant="outline",color = 'lime'),
                 dmc.Text("A match"),
                 dmc.Badge("Prioritize filter condition",variant="outline",color = 'red'),
                 dmc.Text("Not a match")
                 ]
            ),
            #PLACEHOLDER: uncomment to enable macro/micro nutrient
            # dmc.Group(
            #     [dmc.Badge("No. of nutrient match",variant="outline",color = 'lime'),
            #      dmc.Text("High match (>80%)"),
            #      dmc.Badge("No. of nutrient match",variant="outline",color = 'yellow'),
            #      dmc.Text("Medium match (35-80%)")
            #      ]
            # ),
            dmc.Group(
                [
                #  dmc.Badge("No. of nutrient match",variant="outline",color = 'red'),
                #  dmc.Text("Low match (<35%)"),
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
            Output(f"{search_id}_recommendation_store","data"),
            Output("notification-container", "sendNotifications",  allow_duplicate=True)
         ],
        inputs = dict(
            search = Input(search_id,"n_clicks"),
            # filter_dict must be Input to sync when click Search button
            filter_dict = Input(filter_store_id,"data")  
        ),
        state = dict(
            url = State("url","pathname"),
            #page stores
            page_stores = State({"page":ALL,"type":"input_store"},"data"),
            #Profile info
            profile_dict = State(profile_store_id,"data"),
            # Pipeline settings
            n_candidate = State(f"{search_id}_candidate","value"),
            n_recommendations = State(f"{search_id}_n_recommendations","value"),
            n_user = State(f"{search_id}_n_user","value"),
            n_top = State(f"{search_id}_n_top","value"),
            n_bottom = State(f"{search_id}_n_bottom","value"),
            rec_model = State(f"{search_id}_rec_model_switch","value"),
            profile_w = State(f"{search_id}_profile_w","value"),
            filters_w = State(f"{search_id}_filters_w","value"),
            ranker_bias_w = State(f"{search_id}_ranker_bias_w","value"),
            health_w = State(f"{search_id}_health_w","value"),
            health_name = State(f"{search_id}_health_score_switch","value")
        ),
        prevent_initial_call = True
    )
    def generate_recommendation(
            search,filter_dict,url,
            page_stores,profile_dict,
            n_candidate,n_recommendations,n_user,
            n_top,n_bottom,rec_model,profile_w,
            filters_w,ranker_bias_w,health_w,health_name
        ):
        """
        Generating recommendations based on parameters,profile and filters. This callback
        function is shared between pages, but perhaps we can customize different function for each page later.
        """

        url = url[1:]

        context_dict = ctx.args_grouping
        page_df = pd.json_normalize(context_dict["page_stores"])
        idx = page_df.loc[page_df['id.page']==url].index[0]

        #constraint information to use
        constraint_df = pd.read_csv(root_directory / 'data/processed/ui_feature_constraints.csv')
        constraint_df['value'] = constraint_df['value'].apply(ast.literal_eval)

        recommendation_data = {}
        include_traits = []
        exclude_traits = []
        pos_rank_bias = None
        neg_rank_bias = None

        # Handle input query and bias logics when switching pages ---------------------------
        if url == "text_search":

            # Check if there is input data before running the pipeline
            page_data = page_stores[idx]
            recipe_name = page_data["recipe_name"]
            recipe_descript = page_data["recipe_description"]
            recipe_dislike = page_data["recipe_dislike"]

            if (recipe_name in ["",None]) and (recipe_descript in ["",None]) and (recipe_dislike in ["",None]):
                notifi = [dict(
                    title="Requirement",
                    message="Please input recipe name/description for processing.",
                    color="red",
                    action="show",
                    autoClose=2000,
                    withCloseButton=True
                )]

                return None,recommendation_data,notifi
            
            if recipe_descript not in [None,'']:  # Add positive bias to ranking step
                pos_rank_bias = recipe_descript

            if recipe_dislike not in [None,'']:  # Add negative bias to ranking step
                exclude_traits.append((recipe_dislike,profile_w))
                neg_rank_bias = recipe_dislike

            # Create search query
            query = """
            The recipe name:{}.
            Extra info:
            {}
            """
            query = query.format(recipe_name,recipe_descript)

        else:
            notifi = [dict(
                title="Not supported",
                message="Current URL isn't supported, please switch page",
                color="red",
                action="show",
                autoClose=2000,
                withCloseButton=True
            )]
            return None,recommendation_data,notifi
        
        # Handle all reamining shared filters input to the pipeline ---------------------------

        # Check whether we are testing chunk data only, then we need to filter the list of recipe ID
        # and user ID in related chunk data, as as Chroma vectorstore might return ID out of ID mapping
        # of testing models.
        if _app_data['chunk_test']:
            limit_user_ids = _app_data['user_reviews']["user_id"].unique().tolist()
        else:
            limit_user_ids = None

        user_profile = USER_SEARCH_TEMPLATE.format(
            profile_dict.get("cuisine_select",[]),
            profile_dict.get("cooking_method_select",[]),
            profile_dict.get("difficulty_select",[]),
            profile_dict.get("protein_select",[]),
            profile_dict.get("fiber_select",[]),
            profile_dict.get("fat_select",[]),
            profile_dict.get("carbohydrate_select",[]),
            profile_dict.get("sodium_select",[])
        )
        include_traits.append(
            (user_profile,profile_w)  # Add User Profile bias for collaboration search
        )

        # Logic to add Chroma search operator based on exact filters
        filter_df = pd.DataFrame(filter_dict)
        type_mapping = dict(
            filter_name = list(OPERATOR_MAPPING.keys()),
            operator_type = list(OPERATOR_MAPPING.values())
        )
        if filter_df.empty:
            filter_operators = None
        else:
            filter_operators = chroma_filter_operator(filter_df,type_mapping)

        # Logic to add extra priority trait to query embedding
        trait_df = filter_df
        if not trait_df.empty:
            trait_df = trait_df.loc[
                (~(filter_df['filter_value'].isin([None,[]]))) & 
                (filter_df['priority_type']=='priority')
            ]
        for _,row in trait_df.iterrows():  
            include_traits.append((
                TRAIT_MAPPING[row['filter_name']].format(row['filter_value']),
                filters_w
            ))

        if health_w > 0: # weighted rerank score based on healthy score
            min_max = constraint_df.loc[constraint_df['feature']=='who_score','value'].tolist()[0]
            weighted_rank_config = {
                "ranker_weight": 1-health_w,
                "feature_weight": health_w,
                "feature_name": health_name,
                "feature_min": min_max[0],
                "feature_max": min_max[1]
            }

        query_df,rank_df = recommendation_doc_id_pipeline(
            data_df = _app_data["recipe_df"],
            vectorstore = _app_data["vectorstore"],
            rank_model = _app_data["reranker"],
            query = query,
            filters = filter_operators,
            dataset = _app_data['dataset'],
            user_profile = user_profile,
            user_vectorstore = _app_data["user_vectorstore"],
            recommendation_model = _app_data[rec_model],
            embedding_model = _app_data["embedding_model"],
            model_type = rec_model,
            add_biases = include_traits,
            remove_biases = exclude_traits,
            candidate = n_candidate,
            n_recommendations = n_recommendations,
            n_user = n_user,
            n_rank = n_recommendations,
            pos_rank_bias = pos_rank_bias,
            neg_rank_bias = neg_rank_bias,
            ranker_bias_weight = ranker_bias_w,
            weighted_rank_config = weighted_rank_config if health_w > 0 else None,
            limit_user_ids = limit_user_ids,
            random_state = 0
        )
            

        recommendation_data = {}
        #PLACEHOLDER: Logic to generate recommendation and its statistics from database in the server
        if filter_dict!={}:
            # print(filter_dict)
            # print(pd.DataFrame(filter_dict))
            # print('====')
            # print(profile_dict)
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

            return recommendations,recommendation_data,dash.no_update
        else:
            return [],recommendation_data,dash.no_update
        
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
