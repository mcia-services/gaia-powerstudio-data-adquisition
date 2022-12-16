
import json
import time
import xml.etree
import xml.etree.ElementTree
import xml.dom.minidom
import urllib.request
from collections import defaultdict

## PowerStudio API Gateway:
# This class is used to connect to the PowerStudio API and get the data from the devices.
# The data is then converted to a dictionary that can be used by the any client for further processing.
# The class is designed to be used as a singleton, so that the context is only fetched once.
# The data is fetched in batches to avoid timeouts and performance issues.
#
# The gateway has the following methods:
#
# -> get_available_tags: Fetches all the available tags from the PowerStudio API
# ---- Fetch all the devices and their IDs (only once)
# ---- Fetch all the variables of each device and their IDs (only once)
#
# -> get_tags_values: Fetches the values of all the available tags from the PowerStudio API
# ---- Fetch all the values for all the variables (every time)
# ---- Convert the data to a dictionary 
# ---- Return the dictionary
# 
# The dictionary is in the following format:
# {
#   "variableId": value
# }
# 
# Variable Id is the idEx element of the variable node in the variableInfo XML, which is the id used for fetching the values

class PowerStudioGateway():

    # PowerStudio API paths
    DEVICES_PATH = "/services/user/devices.xml"
    VARIABLES_PATH = "/services/user/varInfo.xml"
    VALUES_PATH = "/services/user/values.xml"

    # XML node names
    DEVICES_PARAM_NAME = "id"
    VARIABLES_PARAM_NAME = "var"

    # Batch sizes
    DISCOVER_VARS_BATCH_SIZE = 24
    READ_VALUES_BATCH_SIZE = 60

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.variable_ids = None

    def tags_available(self):
        return self.variable_ids != None

    def get_available_tags(self):
        # Get all the devices XML from PowerStudio
        try:
            response = urllib.request.urlopen(f'{self.host}:{self.port}{PowerStudioGateway.DEVICES_PATH}').read()
        except Exception as e:
            print("Could not connect to PowerStudio", flush=True)
            print("Error: ", e, flush=True)
            return
        
        # Parse the XML
        devices = xml.etree.ElementTree.fromstring(response.decode('utf-8'))

        # Get the device IDs
        device_ids = []
        for device in devices:
            device_ids.append(device.text)
        
        print("Found %i devices" % len(device_ids), flush=True)
       
        # Get the variables from all the devices, in packs, to avoid timeouts
        packs = chop(device_ids, PowerStudioGateway.DISCOVER_VARS_BATCH_SIZE)
        variable_ids = []
        for pack in packs:

            # Build the URI
            variables_uri = f'{self.host}:{self.port}{self.VARIABLES_PATH}?'
            for varId in pack:
                variables_uri += urllib.parse.quote(
                    f'{self.DEVICES_PARAM_NAME}={varId}&', encoding='utf-8')

            # Get the variables info XML from PowerStudio
            try:
                response = urllib.request.urlopen(variables_uri).read()
            except Exception as e:
                print("Could not connect to PowerStudio", flush=True)
                print("Error: ", e, flush=True)
                return

            # Parse the XML
            variables = xml.etree.ElementTree.fromstring(
                response.decode('utf-8'))
            
            # Get the variable IDs
            variable_ids = []
            for variable in variables:
                variable_ids.append(variable.find('idEx').text)

        # Store the variable IDs in the instance for later use
        self.variable_ids = variable_ids

    def get_tags_values(self):
        measurements = defaultdict(float)

        if self.variable_ids is None:
            print("No variables found", flush=True)

        # Get the values from all the variables, in packs, to avoid timeouts
        packs = chop(self.variable_ids, PowerStudioGateway.READ_VALUES_BATCH_SIZE)
        for pack in packs:

            # Build the URI
            variables_uri = f'{self.host}:{self.port}{self.VALUES_PATH}?'
            for varId in pack:
                variables_uri += f'{self.VARIABLES_PARAM_NAME}={varId}&'

            # Get the variables values XML from PowerStudio
            try:
                response = urllib.request.urlopen(variables_uri.replace(
                " ", "%20")).read()
            except Exception as e:
                print("Could not connect to PowerStudio", flush=True)
                print("Error: ", e, flush=True)
                return []
            
            # Parse the XML
            values = xml.etree.ElementTree.fromstring(response.decode('utf-8'))

            # Get the variable IDs and values and store them in the measurements dict
            for value in values:
                if value is not None:
                    id = value.find('id')
                    value = value.find('value')
                    if value is not None and id is not None:
                        measurements[id.text] = value.text

        # Return the measurements dict
        return measurements


# Split a list into chunks of a given size
def chop(list, size):

    # Check if the size is valid
    if size < 2:
        raise ValueError("Chop size cannot be lower than 2")

    ## Split the list into chunks
    # Create an empty list to store the chunks
    parts = []
    # Get the length of the list
    N = len(list)
    # Loop through the list for each chunk
    for i in range(0, N, size):
        # Slice the list and append it to the parts list
        # If the chunk is the last one, slice the list until the end using the min function to avoid out of range errors
        parts.append(list[i:min(N, i + size)])
    return parts