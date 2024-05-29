# powerstudio-data-adquisition

This is a project to collect data from a PowerStudio Website and sent it to a MQTT Broker.

## Requirements

- Python 3
- pip
- virtualenv

## Usage with Docker

Create .env file with the following variables:

- POWERSTUDIO="domain.com"
- POWERSTUDIO_PORT=443

- MQTT_BROKER="domain.com"
- MQTT_PORT=1883
- MQTT_TOPIC="topic"
- MQTT_CLIENT_ID="client_id"
- MQTT_USERNAME="username"
- MQTT_PASSWORD="password"

- VAR_INFO_RETRIEVAL_INTERVAL="every 60 minutes"
- VALUES_RETRIEVAL_INTERVAL="every 5 minutes"

Launch the docker-compose manifest:
`docker-compose up -d`

## Usage without Docker

Create stack.env file with the variables described above.
