import configparser
from flask import Flask, request, jsonify
from influxdb import InfluxDBClient

def read_db_config(filename='database.ini', section='influxdb'):
    # Create a parser
    parser = configparser.ConfigParser()
    # Read the config file
    parser.read(filename)

    # Get section, default to influxdb
    db_config = {}
    if parser.has_section(section):
        params = parser.items(section)
        for param in params:
            db_config[param[0]] = param[1]
    else:
        raise Exception(f'Section {section} not found in the {filename} file')

    return db_config
# ==========================================================================================================
# Send packet API
# ==========================================================================================================
app = Flask(__name__)
@app.route('/thermal/<node_id>', methods=['GET'])
def thermal_api_post(node_id):
    # Influxdb credentials
    db_config = read_db_config()

    # start influx session and upload
    try:
        client = InfluxDBClient(db_config['server'], db_config['influx_port'], db_config['user'], db_config['passwd'], db_config['db'])
        result = client.query(f"SELECT * FROM node_data WHERE node_id='{node_id}' LIMIT 1")
        client.close()
        temperature = None
        print(result.get_points())
        for row in result.get_points():
            temperature = row['temperature']

        client.close()

        if temperature is not None:
            return jsonify({'node_id': node_id, 'temperature': temperature}), 200
        else:
            return jsonify({'error': 'Temperature data not found for the given node_id'}), 404
    except:
        print('Error connecting/uploading to InfluxDB')


# ==========================================================================================================

if __name__ == '__main__':
    app.run(debug=True)