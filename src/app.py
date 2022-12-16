from dotenv import load_dotenv

try: 
    load_dotenv()
except Exception as e:
    print("Could not load .env file", flush=True)

import json
import paho.mqtt.publish
import rocketry

import powerstudio_gateway

import os

powerstudio = os.getenv("POWERSTUDIO")
powerstudio_port = int(os.getenv("POWERSTUDIO_PORT"))
broker = os.getenv("MQTT_BROKER")
port = int(os.getenv("MQTT_PORT"))
topic = os.getenv("MQTT_TOPIC")
client_id = os.getenv("MQTT_CLIENT_ID")
username = os.getenv("MQTT_USERNAME")
password = os.getenv("MQTT_PASSWORD")
var_info_retrieval_interval = os.getenv("VAR_INFO_RETRIEVAL_INTERVAL")
values_retrieval_interval = os.getenv("VALUES_RETRIEVAL_INTERVAL")

print("PowerStudio MQTT Gateway v1.0.0", flush=True)

# Create gateway object to connect to PowerStudio
gateway = powerstudio_gateway.PowerStudioGateway(powerstudio, powerstudio_port)

# Get all the available tags at application startup
print('Discovering tags from PowerStudio', flush=True)
gateway.get_available_tags()

# Create Rocketry app instance
app = rocketry.Rocketry()

# Define tasks

# Discover tags every hour
@app.task(var_info_retrieval_interval)
def task_discover_tags():
    print('Discovering tags from PowerStudio', flush=True)
    gateway.get_available_tags()


# Get data every 5 minutes
@app.task(values_retrieval_interval)
def task_get_data():

    print('Getting data from PowerStudio', flush=True)
    
    # Check if tags are available
    if not gateway.tags_available():
        print("Tags not available, try discovery again", flush=True)
        gateway.get_available_tags()
        if not gateway.tags_available():
            print("Tags still not available, aborting", flush=True)
            return

    # Get the values from all the variables, in packs
    measurement = gateway.get_tags_values()
    # Print the measurement
    # Convert dictionary to JSON inside a payload object
    payload_json = json.dumps({'payload': measurement})
    # Print the JSON
    # Publish to MQTT broker
    try:
        paho.mqtt.publish.single(topic,
                                payload_json,
                                qos=2,
                                hostname=broker,
                                port=port,
                                client_id=client_id,
                                auth={
                                    'username': username,
                                    'password': password
                                })
    except Exception as e:
        print("Error while publishing to MQTT broker: %s" % e, flush=True)
    
    
    print("Published to MQTT broker %s:%s" % (broker, port), flush=True)

# Run the app
app.run()