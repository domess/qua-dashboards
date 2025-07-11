import logging
import uuid
from typing import Any, Dict, Union

import dash_bootstrap_components as dbc
import dash
from dash import Dash, Input, Output, State, html, ctx, ALL

from qua_dashboards.video_mode.data_acquirers.base_data_acquirer import (
    BaseDataAcquirer,
    ModifiedFlags,
)
from qua_dashboards.video_mode.tab_controllers.base_tab_controller import (
    BaseTabController,
)
from qua_dashboards.video_mode import data_registry


logger = logging.getLogger(__name__)

__all__ = ["LiveViewTabController"]


class LiveViewTabController(BaseTabController):
    """
    Controls the 'Live View' tab in the Video Mode application.

    This tab allows users to start and stop the data acquisition process
    using a single toggle button and view the current status. It also allows
    configuration of the data acquirer parameters and sets the
    shared viewer to display live data from the acquirer.
    """

    _TAB_LABEL = "Live View"
    _TAB_VALUE = "live-view-tab"

    _TOGGLE_ACQ_BUTTON_ID_SUFFIX = "toggle-acq-button"
    _ACQUIRER_CONTROLS_DIV_ID_SUFFIX = "acquirer-controls-div"
    _ACQUIRER_STATUS_INDICATOR_ID_SUFFIX = "acquirer-status-indicator"
    _DUMMY_OUTPUT_ACQUIRER_UPDATE_SUFFIX = "dummy-output-acquirer-updates"

    def __init__(
        self,
        data_acquirer: BaseDataAcquirer,
        component_id: str = "live-view-tab-controller",
        is_active: bool = False,
        **kwargs: Any,
    ) -> None:
        """Initializes the LiveViewTabController.

        Args:
            component_id: A unique string identifier for this component instance.
            data_acquirer: The data acquirer instance that this tab will control
                and interact with.
            **kwargs: Additional keyword arguments passed to BaseComponent.
        """
        super().__init__(component_id=component_id, is_active=is_active, **kwargs)
        self._data_acquirer_instance: BaseDataAcquirer = data_acquirer
        logger.info(
            f"LiveViewTabController '{self.component_id}' initialized with "
            f"Data Acquirer '{self._data_acquirer_instance.component_id}'."
        )

    def get_layout(self) -> dbc.Card:
        """
        Generates the Dash layout for the Live View control panel.

        The layout includes a single toggle button for starting/stopping data
        acquisition, a status indicator, and embeds the data acquirer's
        specific parameter controls.

        Returns:
            An html.Div component containing the controls.
        """
        logger.debug(
            f"Generating layout for LiveViewTabController '{self.component_id}'"
        )

        toggle_button_and_status = dbc.Row(
            [
                dbc.Col(
                    dbc.Button(
                        "Start Acquisition",  # Initial text
                        id=self._get_id(self._TOGGLE_ACQ_BUTTON_ID_SUFFIX),
                        color="success",  # Initial color for "Start"
                        className="me-1",
                        style={"width": "100%"},
                    ),
                    width=8,  # Adjusted width
                ),
                dbc.Col(
                    html.Div(
                        dbc.Badge(
                            "STOPPED",  # Initial status text
                            id=self._get_id(self._ACQUIRER_STATUS_INDICATOR_ID_SUFFIX),
                            color="secondary",  # Initial color for STOPPED
                            className="ms-1 p-2",  # Added padding
                            style={
                                "fontSize": "0.9rem",
                                "width": "100%",
                                "textAlign": "center",
                            },
                        ),
                        className=(
                            "d-flex align-items-center justify-content-center h-100"
                        ),
                    ),
                    width=4,  # Adjusted width
                ),
            ],
            className="mb-3 align-items-center",
        )

        acquirer_specific_controls = (
            self._data_acquirer_instance.get_dash_components(include_subcomponents=True)
            if self._data_acquirer_instance
            else [html.P("Data acquirer components could not be loaded.")]
        )

        acquirer_controls_div = html.Div(
            id=self._get_id(self._ACQUIRER_CONTROLS_DIV_ID_SUFFIX),  # type: ignore
            children=acquirer_specific_controls,
            className="mt-3 p-3 border rounded",
        )

        card_body = dbc.CardBody(
            [
                html.H5("Live Acquisition Control", className="card-title text-light"),
                toggle_button_and_status,
                html.Hr(),
                html.H6("Acquirer Parameters", className="text-light"),
                acquirer_controls_div,
                html.Div(
                    id=self._get_id(self._DUMMY_OUTPUT_ACQUIRER_UPDATE_SUFFIX),  # type: ignore
                    style={"display": "none"},
                ),
            ]
        )
        return dbc.Card(
            card_body, color="dark", inverse=True, className="tab-card-dark"
        )

    def on_tab_activated(self) -> Dict[str, Any]:
        """
        Called by the orchestrator when this tab becomes active.

        Sets the shared viewer to point to the live data stream from the
        data_registry.
        """
        from qua_dashboards.video_mode.video_mode_component import VideoModeComponent

        logger.info(f"LiveViewTabController '{self.component_id}' activated.")

        current_live_version = data_registry.get_current_version(
            data_registry.LIVE_DATA_KEY
        )

        if current_live_version is None:
            current_live_version = str(uuid.uuid4())
            logger.debug(
                f"{self.component_id}: No current live data version found. "
                f"Using placeholder: {current_live_version}"
            )

        viewer_data_payload = {
            "key": data_registry.LIVE_DATA_KEY,
            "version": current_live_version,
        }

        updates = {
            VideoModeComponent.VIEWER_DATA_STORE_SUFFIX: viewer_data_payload,
            VideoModeComponent.VIEWER_UI_STATE_STORE_SUFFIX: {},
            VideoModeComponent.VIEWER_LAYOUT_CONFIG_STORE_SUFFIX: {},
        }
        return updates

    def on_tab_deactivated(self) -> None:
        """Called by the orchestrator when this tab is no longer active."""
        logger.info(f"LiveViewTabController '{self.component_id}' deactivated.")
        pass

    def register_callbacks(
        self,
        app: Dash,
        orchestrator_stores: Dict[str, Any],
        shared_viewer_store_ids: Dict[str, Any],
    ) -> None:
        """
        Registers Dash callbacks for the Live View tab.

        Args:
            app: The main Dash application instance.
            orchestrator_stores: Dictionary of orchestrator-level store IDs.
            shared_viewer_store_ids: Dictionary of shared viewer store IDs.
        """
        logger.info(
            f"Registering callbacks for LiveViewTabController '{self.component_id}'."
        )
        self._register_acquisition_control_callback(app, orchestrator_stores)
        self._register_parameter_update_callback(app)

    def _register_acquisition_control_callback(
        self, app: Dash, orchestrator_stores: Dict[str, Any]
    ) -> None:
        """Registers callback for acquisition control and status updates."""
        from qua_dashboards.video_mode.video_mode_component import VideoModeComponent

        main_status_alert_id = orchestrator_stores.get(
            VideoModeComponent._MAIN_STATUS_ALERT_ID_SUFFIX
        )
        if not main_status_alert_id:
            logger.error(
                f"Could not find {VideoModeComponent._MAIN_STATUS_ALERT_ID_SUFFIX} "
                "in orchestrator_stores. Status synchronization might be affected."
            )

        @app.callback(
            Output(self._get_id(self._TOGGLE_ACQ_BUTTON_ID_SUFFIX), "children"),
            Output(self._get_id(self._TOGGLE_ACQ_BUTTON_ID_SUFFIX), "color"),
            Output(self._get_id(self._ACQUIRER_STATUS_INDICATOR_ID_SUFFIX), "children"),
            Output(self._get_id(self._ACQUIRER_STATUS_INDICATOR_ID_SUFFIX), "color"),
            Input(self._get_id(self._TOGGLE_ACQ_BUTTON_ID_SUFFIX), "n_clicks"),
            Input(main_status_alert_id, "children"),
            prevent_initial_call=True,
        )
        def handle_acquisition_control_and_status_update(
            _toggle_clicks: Any, _status_alert_trigger: Any
        ) -> tuple[str, str, str, str]:
            """
            Handles acquisition toggle and updates UI based on acquirer status.
            """
            triggered_input_id_obj = ctx.triggered_id
            is_button_click = False
            if isinstance(triggered_input_id_obj, dict):  # Pattern matched ID
                is_button_click = (
                    triggered_input_id_obj.get("index")
                    == self._TOGGLE_ACQ_BUTTON_ID_SUFFIX
                )
            elif isinstance(triggered_input_id_obj, str):  # Simple string ID
                is_button_click = (
                    self._get_id(self._TOGGLE_ACQ_BUTTON_ID_SUFFIX)
                    == triggered_input_id_obj
                )

            acquirer_state = self._data_acquirer_instance.get_latest_data()
            current_status = acquirer_state.get("status", "unknown").upper()
            error_details = acquirer_state.get("error")

            button_text: str
            button_color: str
            status_text: str
            status_color: str

            if is_button_click:
                logger.debug(
                    f"LiveViewTab: Toggle acquisition button clicked. "
                    f"Current reported acquirer status: {current_status}"
                )
                if current_status == "RUNNING":
                    logger.info(
                        f"Attempting to stop acquisition for "
                        f"'{self._data_acquirer_instance.component_id}'"
                    )
                    self._data_acquirer_instance.stop_acquisition()
                    button_text, button_color = "Start Acquisition", "success"
                    status_text, status_color = "STOPPED", "secondary"
                else:  # Was STOPPED, ERROR, or UNKNOWN
                    logger.info(
                        f"Attempting to start acquisition for "
                        f"'{self._data_acquirer_instance.component_id}'"
                    )
                    self._data_acquirer_instance.start_acquisition()
                    button_text, button_color = "Stop Acquisition", "danger"
                    status_text, status_color = "RUNNING", "success"
            else:
                if current_status != "STOPPED":
                    logger.debug(
                        f"LiveViewTab: Status update triggered externally. "
                        f"Acquirer status: {current_status}"
                    )
                if current_status == "RUNNING":
                    button_text, button_color = "Stop Acquisition", "danger"
                    status_text, status_color = "RUNNING", "success"
                elif current_status == "STOPPED":
                    button_text, button_color = "Start Acquisition", "success"
                    status_text, status_color = "STOPPED", "secondary"
                elif current_status == "ERROR":
                    button_text, button_color = (
                        "Start Acquisition",
                        "success",
                    )
                    status_text = (
                        f"ERROR{(': ' + str(error_details)) if error_details else ''}"
                    )
                    status_text = status_text[:100]
                    status_color = "danger"
                else:  # Unknown or other states
                    button_text, button_color = "Start Acquisition", "warning"
                    status_text, status_color = current_status, "warning"

            return button_text, button_color, status_text, status_color

    def _register_parameter_update_callback(self, app: Dash) -> None:

        """Registers callback for data acquirer parameter updates."""
        all_acquirer_components = self._data_acquirer_instance.get_components()

        dynamic_inputs = [
            Input(component._get_id(ALL), "value")
            for component in all_acquirer_components
        ]
        dynamic_states_ids = [
            State(component._get_id(ALL), "id") for component in all_acquirer_components
        ]

        @app.callback(
            Output(
                self._get_id(self._DUMMY_OUTPUT_ACQUIRER_UPDATE_SUFFIX),
                component_property="children",
            ),
            dynamic_inputs,
            dynamic_states_ids,
            prevent_initial_call=True,
        )
        def handle_acquirer_parameter_update(*args: Any):
            num_comp_types = len(all_acquirer_components)
            values_by_type_list = args[:num_comp_types]
            ids_by_type_list = args[num_comp_types : 2 * num_comp_types]

            parameters_to_update: Dict[str, Dict[str, Any]] = {}

            for i, component in enumerate(all_acquirer_components):
                component_params = self._parse_component_parameters(
                    component.component_id,
                    values_by_type_list[i],
                    ids_by_type_list[i],
                )

                if not component_params:
                    continue
                parameters_to_update[component.component_id] = component_params

            self._data_acquirer_instance.update_parameters(parameters_to_update)

            return dash.no_update

    @staticmethod
    def _parse_component_parameters(
        component_id: Union[str, dict],
        values: Any,
        ids: Any,
    ) -> Dict[str, Any]:
        if not values or not ids:
            return {}

        current_type_params: Dict[str, Any] = {}
        for idx, param_id_dict in enumerate(ids):
            if isinstance(param_id_dict, dict) and "index" in param_id_dict:
                param_name = param_id_dict["index"]
                if idx < len(values):
                    param_value = values[idx]
                    current_type_params[param_name] = param_value
                else:
                    logger.warning(
                        f"Value missing for param_id {param_id_dict} "
                        f"of type {component_id}"
                    )
            else:
                logger.warning(
                    f"Unexpected ID format in acquirer params: "
                    f"{param_id_dict} of type {component_id}"
                )
        return current_type_params
