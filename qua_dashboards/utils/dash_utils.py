from typing import Union
from dash import dcc, html
from dash.dash import Any, warnings
import dash_bootstrap_components as dbc
from plotly import graph_objects as go


def convert_to_dash_component(elem: Union[dict, list]) -> Any:
    if isinstance(elem, list):
        return [convert_to_dash_component(e) for e in elem]
    elif isinstance(elem, dict):
        if "namespace" not in elem:
            return {
                key: convert_to_dash_component(value) for key, value in elem.items()
            }

        if elem["namespace"] == "dash_html_components":
            cls = getattr(html, elem["type"])
            if "children" in elem["props"]:
                children = elem["props"].pop("children")
                elem["props"]["children"] = convert_to_dash_component(children)
            return cls(**elem["props"])

        if elem["namespace"] == "dash_bootstrap_components":
            cls = getattr(dbc, elem["type"])
            if "children" in elem["props"]:
                children = elem["props"].pop("children")
                elem["props"]["children"] = convert_to_dash_component(children)
            return cls(**elem["props"])

        if elem["type"] == "Graph":
            if isinstance(elem["props"].get("figure"), dict):
                elem["props"]["figure"] = go.Figure(**elem["props"]["figure"])
            return dcc.Graph(**elem["props"])
        raise ValueError(f"Unknown element: {elem}")
    else:
        return elem
