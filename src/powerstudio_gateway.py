# pylint: disable=missing-class-docstring, missing-function-docstring, line-too-long
"""powerstudio_gateway module, used to connect to the PowerStudio API and get the data from the devices."""

from typing import TypeVar
import xml.etree
import xml.etree.ElementTree
import xml.dom.minidom
import urllib.request
import urllib.parse
import concurrent.futures


class PowerStudioGateway:
    """PowerStudio API Gateway:
    This class is used to connect to the PowerStudio API and get the data from the devices.
    The data is then converted to a dictionary that can be used by the any client for further processing.
    The class is designed to be used as a singleton, so that the context is only fetched once.
    The data is fetched in batches to avoid timeouts and performance issues.

    The gateway has the following methods:

    -> get_available_tags: Fetches all the available tags from the PowerStudio API
    ---- Fetch all the devices and their IDs (only once)
    ---- Fetch all the variables of each device and their IDs (only once)

    -> get_tags_values: Fetches the values of all the available tags from the PowerStudio API
    ---- Fetch all the values for all the variables (every time)
    ---- Convert the data to a dictionary
    ---- Return the dictionary

    The dictionary is in the following format:
    {
    "variableId": value
    }

    Variable Id is the idEx element of the variable node in the variableInfo XML, which is the id used for fetching the values

    """

    # PowerStudio API paths
    DEVICES_PATH = "/services/user/devices.xml"
    VARIABLES_PATH = "/services/user/varInfo.xml"
    VALUES_PATH = "/services/user/values.xml"

    # XML node names
    DEVICES_PARAM_NAME = "id"
    VARIABLES_PARAM_NAME = "var"

    # Batch sizes
    DISCOVER_VARS_BATCH_SIZE = 40

    """
    With 180 variables per device it works, and it takes arround 10 seconds.
    Whatever the number of variables, it will take between 10 and 13 seconds,
    doesn't seem to be a relation between the number of variables and the time
    it takes to get all the results.
    It's also possible that the bottleneck is the python code itself, and not
    the PowerStudio server, probably because of the XML parsing. A way to
    improve this would be to use a more "low level" approach, like using the
    file descriptor directly to read the XML, as we already know the structure
    of the XML.
    """
    READ_VALUES_BATCH_SIZE = 40

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.variable_ids: list[str] = []

    def tags_available(self):
        return len(self.variable_ids) > 0

    def import_tags(self, tags_file_path: str) -> None:

        with open(tags_file_path, "r", encoding="UTF-8") as tags_file:

            line = tags_file.readline()

            while line:

                if line[0] != "#" and line[0] != "\n" and len(line) > 2:
                    self.variable_ids.append(line.strip())

                line = tags_file.readline()

    def get_available_tags(self):
        # Get all the devices XML from PowerStudio
        response = urllib.request.urlopen(
            f"{self.host}:{self.port}{PowerStudioGateway.DEVICES_PATH}"
        ).read()

        devices = xml.etree.ElementTree.fromstring(response.decode("utf-8"))

        # Get the device IDs
        device_ids: list[str] = []
        for device in devices:
            if device.text is not None:
                device_ids.append(device.text)

        # Get the variables from all the devices, in packs, to avoid timeouts
        packs: list[list[str]] = make_batch_consecutive_sized(
            device_ids, PowerStudioGateway.DISCOVER_VARS_BATCH_SIZE
        )
        variable_ids: list[str] = []

        def get_variables(pack: list[str]) -> list[str]:
            # Build the URI
            variables_uri = f"{self.host}:{self.port}{self.VARIABLES_PATH}?"
            for device_id in pack:
                variables_uri += urllib.parse.quote(
                    f"{self.DEVICES_PARAM_NAME}={device_id}&", encoding="utf-8"
                )

            # Get the variables info XML from PowerStudio
            response = urllib.request.urlopen(variables_uri).read()

            # Parse the XML
            variables = xml.etree.ElementTree.fromstring(
                response.decode("utf-8")
            )
            result: list[str] = []
            for variable in variables:
                id_ex_element = variable.find("idEx")
                if (
                    id_ex_element is not None
                    and id_ex_element.text is not None
                ):
                    result.append(id_ex_element.text)

            return result

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=100
        ) as executor:
            # Start the load operations and mark each future with its URL
            futures = {executor.submit(get_variables, pack) for pack in packs}
            for future in concurrent.futures.as_completed(futures):

                result = future.result()
                variable_ids += result

        # Store the variable IDs in the instance for later use
        self.variable_ids = variable_ids

    def get_tags_values(self) -> dict[str, float]:
        measurements: dict[str, float] = {}

        if not self.tags_available():
            raise ValueError("No tags available")

        # Get the values from all the variables, in packs, to avoid timeouts
        batches = make_batch_consecutive_sized(
            self.variable_ids, PowerStudioGateway.READ_VALUES_BATCH_SIZE
        )

        def get_values(batch: list[str]) -> dict[str, float]:
            measurements: dict[str, float] = {}
            # Build the URI
            values_uri = f"{self.host}:{self.port}{self.VALUES_PATH}?"
            for variable_id in batch:
                values_uri += f"{self.VARIABLES_PARAM_NAME}={variable_id}&"

            values_uri = values_uri.replace(" ", "%20")

            # Get the variables values XML from PowerStudio
            response = urllib.request.urlopen(values_uri).read()

            # Parse the XML
            values = xml.etree.ElementTree.fromstring(response.decode("utf-8"))

            # Get the variable IDs and values and store them in the measurements dict
            for value in values:
                variable_id = value.find("id")
                value = value.find("value")
                if (
                    value is not None
                    and variable_id is not None
                    and variable_id.text is not None
                    and value.text is not None
                ):
                    measurements[variable_id.text] = (
                        float(value.text) if value.text != "-" else 0.0
                    )

            return measurements

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # Start the load operations and mark each future with its URL
            futures = {executor.submit(get_values, pack) for pack in batches}
            for future in concurrent.futures.as_completed(futures):

                result = future.result()
                measurements.update(result)

        # Return the measurements dict
        return measurements


T = TypeVar("T")


# Split a list into chunks of a given size
def make_batch_consecutive_sized(
    elements_list: list[T], size: int
) -> list[list[T]]:

    # Check if the size is valid
    if size < 2:
        raise ValueError("Chop size cannot be lower than 2")

    # Split the list into chunks
    return [
        elements_list[i : i + size] for i in range(0, len(elements_list), size)
    ]
