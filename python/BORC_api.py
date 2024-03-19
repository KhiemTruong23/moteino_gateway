import configparser
import json
import urllib.parse as ulp
from flask import Flask, request, jsonify
from influxdb import InfluxDBClient
import requests

# ==========================================================================================================
# Send packet API
# ==========================================================================================================
app = Flask(__name__)
@app.route('/thermal/<node_id>', methods=['GET'])
def thermal_api_post(node_id):
    # Influxdb credentials
    query1 = f"SELECT mean(\"temperature\") FROM \"node_data\" WHERE (\"node_id\" = '{node_id}') AND time >= now() - 24h and time <= now() GROUP BY time(500ms) fill(null);"
    query = f"https://data.elemental-platform.com/api/datasources/proxy/3/query?db=berg&q={ulp.quote(query1)}&epoch=ms"
    #print (query)
    # send query to server
    try:
        r = requests.get(query, auth=('username', 'password'), verify=False)
        json_data = json.loads(r.text)
        return(json_data)
    except:
        print ("Error: bad/no response from server")
    # save response from server
# ==========================================================================================================

if __name__ == '__main__':
    app.run(debug=True)