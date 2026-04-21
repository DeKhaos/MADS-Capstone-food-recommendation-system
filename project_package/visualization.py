from typing import List

import pandas as pd
import numpy as np
import plotly.graph_objects as go

def sankey_fig_node_mapping(
    df: pd.DataFrame,
    feature: str,
    log_scale:bool = False
    ):
    """
    Utilize function to map the category labels from the pipeline Dataframe to each sankey node. Only the 
    labels in 'ranked' step will be used to create note.

    Parameters
    ----------

    df: pd.DataFrame
        Pipeline dataframe which contain 'pipeline_step' feature and the target feature labels.

    feature: str
        The column to process.

    log_scale: bool
        Add log scaled value to output Dataframe.

    Returns
    ----------
    map_df: pd.DataFrame

    node_map: dict
        Map node names to node ids
    """

    process_df = df.copy()
    process_df['value'] = 1  # add feature to count

    process_df = process_df.groupby(['pipeline_step',feature],sort=False)['value'].count().reset_index()

    process_df['name'] = process_df['pipeline_step'] + ':<br>' + process_df[feature]  # Create node names

    # We are using the ranked items to retrieved the labels at the end of the pipeline and traceback to previous layer
    check_list = process_df.loc[process_df['pipeline_step']=='ranked',feature].tolist()

    process_df = process_df.loc[process_df[feature].isin(check_list)].reset_index(drop=True)

    item_2_map = process_df.name.tolist() + ['user:<br>' + item for item in check_list]  # Add a final note layers for displaying to users
    node_map = {node: i for i, node in enumerate(item_2_map)}

    # Mapping the source, target nodes and the link weight.
    data = []
    for item in check_list:
        slice_df = process_df.loc[process_df[feature] == item]
        n = slice_df.shape[0]
        for i in range(n):
            if i != n-1:
                data.append({
                    "source_name":slice_df.iloc[i]['name'],
                    "target_name":slice_df.iloc[i+1]['name'],
                    "value":slice_df.iloc[i]['value']
                })
            else:
                data.append({
                    "source_name":slice_df.iloc[i]['name'],
                    "target_name":"user:<br>" + item,
                    "value":slice_df.iloc[i]['value']
                })

    # node index mapping
    map_df = pd.DataFrame(data)
    map_df['source'] = map_df['source_name'].map(node_map)
    map_df['target'] = map_df['target_name'].map(node_map)
    map_df = map_df.dropna(subset = 'value')  # drop any connection that have NaN value

    if log_scale:  # add scaled weight values
        map_df['log_value'] = np.log1p(map_df['value'])
    # map_df = map_df.sort_values(['target','value'],ascending=[False,False])

    return map_df,node_map

def sankey_plot(
    data: pd.DataFrame,
    feature: str,
    title: str,
    log_scale: bool = True,
    highlight_targets: List[str] = None,
    hightlight_color: str = "red",
    height: int = 600,
    width: int = 1000
):
    """
    Create sankey for a single query to analyze how labels of a category feature is being updated through
    the recommendation pipeline.

    Parameters
    ----------

    data: pd.DataFrame
        Pipeline dataframe which contain 'pipeline_step' feature and the target feature labels.

    feature: str
        The column to process.

    title: str
        The title of the chart.

    log_scale: bool
        Add log scaled value to output Dataframe.

    highlight_targets: List[str]
        List pattern matching string use to target which node text to highlight.

    hightlight_color: str
        The highlight color

    height: int
        The height of the plot.

    width: int
        The width of the plot.

    Returns
    ----------
    fig: plotly.graph_object
    """

    map_df, node_map = sankey_fig_node_mapping(data,feature,log_scale)
    
    if log_scale:
        value_col = 'log_value'
    else:
        value_col = 'value'
        
    node_labels = list(node_map.keys())
    # we get the layer that each node belong to
    node_layers = [item.split(":<br>")[0] for item in node_labels]

    # Add highlight to certain node texts
    if highlight_targets is not None:
        highlight_style = f"color: {hightlight_color};"
        new_node_labels = []
        for node_label in node_labels:
            if any(target in node_label for target in highlight_targets) :
                highlighted = f"<b><span style='{highlight_style}'>{node_label}</span></b>"
                new_node_labels.append(highlighted)
            else:
                new_node_labels.append(node_label)

        node_labels = new_node_labels

    # Layer colors
    color_map = {
        "full_data":"red",
        "candidate":"orange",
        "recommendation":"yellow",
        "ranked":"blue",
        "user":"green"
    }

    node_colors = list(map(lambda x:color_map[x],node_layers))

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.75),
            label=node_labels,
            color=node_colors,
            customdata=node_layers,
            hovertemplate=(
                "Layer: %{customdata}<extra></extra>"
            )
        ),
        link=dict(
            source=map_df['source'],
            target=map_df['target'],
            value=map_df[value_col],
            customdata=map_df['value'],
            hovertemplate=(
                "label count: %{customdata}<extra></extra>"
            ),
            color="rgba(100, 100, 255, 0.4)" # Semitransparent blue
        )
    )])

    # Color map for legends
    layer_info = {
        "Full data layer": "red",
        "Candidate layer": "orange",
        "Recommendation layer": "yellow",
        "Ranked layer": "blue",
        "User layer": "green"
    }

    # 2. Add a dummy scatter trace for each layer
    for name, color in layer_info.items():
        fig.add_trace(go.Scatter(
            x=[None], # No data points
            y=[None],
            mode='markers',
            marker=dict(size=10, color=color), # Match the node color
            legendgroup=name,
            showlegend=True,
            name=name
        ))
        
    fig.update_layout(
        title={
            'text': title,
            'y': 0.9,           
            'x': 0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        height=height,
        width=width,
        xaxis=dict(
            showgrid=False, 
            zeroline=False, 
            showticklabels=False,
            visible=False
        ),
        yaxis=dict(
            showgrid=False, 
            zeroline=False, 
            showticklabels=False,
            visible=False
        ),
        plot_bgcolor='rgba(0,0,0,0)', # Sets background to transparent
    )

    return fig