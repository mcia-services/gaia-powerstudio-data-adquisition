# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring

import os
import json
import logging
import sys

import dotenv  # type: ignore
import paho.mqtt.publish
import rocketry  # type: ignore
import rocketry.conds  # type: ignore

import powerstudio_gateway

dotenv.load_dotenv()  # type: ignore


LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")

POWERSTUDIO_HOST = os.getenv("POWERSTUDIO_HOST", default="http://localhost")
POWERSTUDIO_PORT = int(os.getenv("POWERSTUDIO_PORT", default="80"))

BROKER = os.getenv("MQTT_BROKER", default="localhost")
PORT = int(os.getenv("MQTT_PORT", default="1883"))
TOPIC = os.getenv("MQTT_TOPIC", default="powerstudio")
CLIENT_ID = os.getenv("MQTT_CLIENT_ID", default="powerstudio-gateway")
USERNAME = os.getenv("MQTT_USERNAME", default="username")
PASSWORD = os.getenv("MQTT_PASSWORD", default="password")

VALUES_RETRIEVAL_INTERVAL = os.getenv(
    "VALUES_RETRIEVAL_INTERVAL", default="5m"
)

# Configure logging to stdout and stderr

logger = logging.getLogger()

logger.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", "%m-%d-%Y %H:%M:%S"
)

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

logger.addHandler(stdout_handler)

logger.info("Starting application PowerStudio MQTT Gateway")

# Create gateway object to connect to PowerStudio
gateway = powerstudio_gateway.PowerStudioGateway(
    f"https://{POWERSTUDIO_HOST}", POWERSTUDIO_PORT
)

# Get all the available tags at application startup
logger.info("Loading Powerstudio tags file")
gateway.import_tags("./tags_powerstudio.txt")

if not gateway.tags_available():
    logger.info("Tags not available, try discovery again")
    gateway.import_tags("./tags_powerstudio.txt")

if not gateway.tags_available():
    logger.info("Tags still not available, aborting")
    sys.exit(1)

# Create Rocketry app instance
app = rocketry.Rocketry()


# Get data task
@app.task(VALUES_RETRIEVAL_INTERVAL | rocketry.conds.retry(3))  # type: ignore
def task_get_data():

    # Get the values from all the variables, in packs
    measurement = gateway.get_tags_values()
    # Print the measurement
    # Convert dictionary to JSON inside a payload object
    payload_json = json.dumps({"payload": measurement})
    # Print the JSON
    # Publish to MQTT broker
    logger.info("Retrieved data from Powerstudio, %i tags", len(measurement))

    paho.mqtt.publish.single(
        TOPIC,
        payload_json,
        qos=2,
        hostname=BROKER,
        port=PORT,
        client_id=CLIENT_ID,
        auth={"username": USERNAME, "password": PASSWORD},
    )

    logger.info("Published to MQTT broker %s:%i", BROKER, PORT)


# Run the app
app.run()
