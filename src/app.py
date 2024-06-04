# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring

import os
import json
import logging
import sys
import time

import dotenv  # type: ignore
import paho.mqtt.publish
import rocketry  # type: ignore
import rocketry.conds  # type: ignore

import powerstudio_gateway

dotenv.load_dotenv("stack.env", override=True)  # type: ignore


LOGGING_LEVEL = os.getenv("LOGGING_LEVEL", "INFO")

POWERSTUDIO_URL = os.getenv("POWERSTUDIO_URL")
if POWERSTUDIO_URL is None:
    raise ValueError("POWERSTUDIO_URL environment variable not set, aborting")

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

logging.getLogger().setLevel(LOGGING_LEVEL)
logger = logging.getLogger("service")

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s", "%m-%d-%Y %H:%M:%S"
)
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)

logger.addHandler(stdout_handler)
logger.setLevel(LOGGING_LEVEL)
logger.info("Starting application PowerStudio MQTT Gateway")


# Create gateway object to connect to PowerStudio
gateway = powerstudio_gateway.PowerStudioGateway(POWERSTUDIO_URL)

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
logger.info("Creating Rocketry app instance")
app = rocketry.Rocketry()
logger.info("Rocketry app instance created")

rocketry_logger = logging.getLogger("rocketry")
rocketry_logger.addHandler(stdout_handler)
rocketry_logger.setLevel(LOGGING_LEVEL)


# Get data task
@app.task(VALUES_RETRIEVAL_INTERVAL)  # type: ignore
def task_get_data():

    # Get the values from all the variables, in packs
    logger.info("Retrieving data from Powerstudio")

    measurement = None
    retry = 0

    while measurement is None:
        try:
            measurement = gateway.get_tags_values()
        except Exception as e:
            retry += 1
            logger.error("Error while retrieving data from Powerstudio: %s", e)
            if retry > 3:
                logger.error("Max retries reached, aborting")
                return
            time.sleep(5)
    # Print the measurement
    # Convert dictionary to JSON inside a payload object
    logger.info("Converting data to JSON")
    payload_json = json.dumps({"payload": measurement})
    # Print the JSON
    # Publish to MQTT broker
    logger.info(
        "Sending data from Powerstudio, %i tags, to MQTT broker %s:%i",
        len(measurement),
        BROKER,
        PORT,
    )
    done = False
    retry = 0
    while not done:
        try:
            paho.mqtt.publish.single(
                TOPIC,
                payload_json,
                qos=2,
                hostname=BROKER,
                port=PORT,
                client_id=CLIENT_ID,
                auth={"username": USERNAME, "password": PASSWORD},
            )
            done = True
        except Exception as e:
            retry += 1
            logger.error("Error while sending data to MQTT broker: %s", e)
            if retry > 3:
                logger.error("Max retries reached, aborting")
                return
            logger.error("Retrying in 5 seconds")
            time.sleep(5)

    logger.info("Task completed successfully")


# Run the app
logger.info("Launching Rocketry app")
app.run()
