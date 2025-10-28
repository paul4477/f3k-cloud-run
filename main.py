import os
import flask
import redis
from redis.commands.json.path import Path
    
# Patch JSONEncoder to use __json__ method if available
from json import JSONEncoder
def wrapped_default(self, obj):
    return getattr(obj.__class__, "__json__", wrapped_default.default)(obj)
wrapped_default.default = JSONEncoder().default

# apply the patch
JSONEncoder.original_default = JSONEncoder.default
JSONEncoder.default = wrapped_default

import logging
logging.basicConfig(format='%(asctime)s.%(msecs)03d %(name)s %(levelname)s:%(message)s', datefmt='%m/%d/%Y %H:%M:%S', level=logging.DEBUG, filename='f3k-cloud-run.log')

from flask import Flask, render_template, request, redirect, url_for
from flask_sse import sse

global events 
events = {}

app = flask.Flask("f3k-cloud-run")
# Redis definition for Flask SSE
app.config["REDIS_URL"] = "redis://127.0.0.1"
app.register_blueprint(sse, url_prefix='/eventsource')

# Redis client for direct access
redis_client = redis.Redis(host="127.0.0.1", port=6379, db=0)

## State is only maintained in the client as far as the timing, round progression etc is concerned.
## Server side is just a data holder and broadcaster (forwarder) of state changes via SSE.

## Front end routes:
## / - event picker - redirects to /event/<event-id> (render template)
## /event/<event-id> - show state, matrix and groups (maybe allow highlighting of pilots  ) (render template)
## /eventsource?channel=<event-id> - SSE endpoint for event updates

## API routes:
## /api/event - POST - create event and save to in-memory dict and add to Redis cache
## /api/event/<event-id>/state - POST - update event state - triggers SSE message to listening clients

## /api/event/<event-id> - GET only, shows event summary details
## /api/event/<event-id>/round/<round-number> - GET only, shows round details
## /api/event/<event-id>/round/<round-number>/group/<group-letter> - GET only, shows group details


import f3k_cl_competition

def load_from_redis(event_id):
    result = redis_client.json().get(event_id)
    if result:
        events[event_id] = f3k_cl_competition.f3k_event(result)
        return events[event_id]
    else:
        return None

@app.route('/api/event/', methods=['POST'])
def create_event(): 
    global events
    data = flask.request.json

    app.logger.debug(f'POST create event: {data}')

    if 'event_id' not in data['event']:
        return flask.jsonify({'error': 'event_id required'}), 400
    
    event = f3k_cl_competition.f3k_event(data)
    events[event.event_id] = event
    redis_client.json().set(event.event_id, Path.root_path(), event)
    redis_client.expire(event.event_id, 3600*8)  # Expire in 8 hour
    
    return redirect(url_for('view_event', event_id=event.event_id))

@app.route('/api/event/<int:event_id>', methods=['GET'])
def get_event(event_id): 
    global events
    """GET JSON of a specific event"""
    if event_id not in events:
        if not load_from_redis(event_id):
            return flask.jsonify({'error': 'Event not found', 'events':events.keys()}), 404
    
    event = events[event_id]
    return flask.jsonify({'rounds': [ 
        [
            (g.group_letter, list(event.pilots[p].name for p in g.pilots))
            for g in r.groups
            ]
        for r in event.rounds
    ]})

@app.route('/api/event/<int:event_id>/round/<int:round_number>', methods=['GET'])
def get_event_round(event_id, round_number): 
    global events
    """GET JSON of a specific event round"""
    if event_id not in events:
        if not load_from_redis(event_id):
            return flask.jsonify({'error': 'Event not found'}), 404

    event = events[event_id]
    if round_number < 1 or round_number > len(event.rounds):
        return flask.jsonify({'error': 'Round not found'}), 404

    round_data = event.rounds[round_number - 1]
    return flask.jsonify({
        'round_number': round_data.round_number,
        'task_name': round_data.task_name,
        'groups': [
            {
                'letter': g.group_letter,
                'pilots': [event.pilots[p].name for p in g.pilots]
            }
            for g in round_data.groups
        ]
    })

@app.route('/api/event/<int:event_id>/round/<int:round_number>/group/<group_letter>', methods=['GET'])
def get_event_round_group(event_id, round_number, group_letter): 
    global events
    """GET JSON of a specific event round group"""
    if event_id not in events:
        if not load_from_redis(event_id):
            return flask.jsonify({'error': 'Event not found'}), 404

    event = events[event_id]
    if round_number < 1 or round_number > len(event.rounds):
        return flask.jsonify({'error': 'Round not found'}), 404

    round_data = event.rounds[round_number - 1]
    group_data = next((g for g in round_data.groups if g.group_letter == group_letter), None)
    if not group_data:
        return flask.jsonify({'error': 'Group not found'}), 404

    return flask.jsonify({
        'group_letter': group_data.group_letter,
        'pilots': [event.pilots[p].name for p in group_data.pilots]
    })

@app.route('/api/event/<event_id>/state', methods=['POST'])
def state(event_id):
    global events
    data = flask.request.json
    app.logger.debug(f'POST state ID:{event_id}: {data}')

    # Channel should be a string
    sse.publish(data, type="state", channel=str(event_id))  
    return {}, 200

## 
## Front end routes

@app.route('/event/<int:event_id>', methods=['GET'])
def view_event(event_id):
    global events
    """Client page to view event status"""

    return flask.render_template('event_viewer.html', event_id=event_id)

@app.route("/")
def index():
    global events
    return flask.render_template('event_selector.html')

# Static content routes
@app.route('/favicon.ico')
def favicon():
    """Serve favicon from assets/images directory"""
    return flask.send_from_directory('assets/images', 'favicon.ico')

@app.route('/assets/images/<path:filename>')
def serve_images(filename):
    """Serve images from assets/images directory"""
    return flask.send_from_directory('assets/images', filename)

def initialise():
 pass

if __name__ == "__main__":

    initialise()
    app.logger.setLevel(logging.DEBUG)

    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
