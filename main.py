import os
import time
import flask
import json

from flask import Flask, render_template, request, redirect, url_for
from flask_sse import sse

app = flask.Flask(__name__)
app.config["REDIS_URL"] = "redis://127.0.0.1"

try: app.register_blueprint(sse, url_prefix='/eventsource')
except: pass

## State is only maintained in the client as far as the timing, round progression etc is concerned.
## Server side is just a data holder and broadcaster (forwarder) of state changes via SSE.

## Front end routes:
## / - event picker - redirects to /event/<event-id> (render template)
## /event/<event-id> - show state, matrix and groups (maybe allow highlighting of pilots  ) (render template)
## /eventsource?channel=<event-id> - SSE endpoint for event updates

## API routes:
## /api/event - POST - create event and save to in-memory dict
## /api/event/<event-id>/state - POST - update event state - triggers SSE message

## /api/event/<event-id> - GET only, shows event summary details
## /api/event/<event-id>/round/<round-number> - GET only, shows round details
## /api/event/<event-id>/round/<round-number>/group/<group-letter> - GET only, shows group details


import f3k_cl_competition

# Global dictionary to store events
events = {}

@app.route('/api/event/', methods=['POST'])
def create_event(): 
    """Create a new event"""
    data = flask.request.json
    print(data['event']['event_id'])
    if 'event_id' not in data['event']:
        return flask.jsonify({'error': 'event_id required'}), 400
    
    event = f3k_cl_competition.f3k_event(data)
    events[event.event_id] = event
    print (events)
    
    # Publish event creation via SSE
    #sse.publish({'event_id': event.event_id, 'action': 'created'}, type="event")
    
    #return flask.jsonify({'event_id': event.event_id, 'status': 'created'}), 201
    return redirect(url_for('view_event', event_id=event.event_id))


@app.route('/api/event/<int:event_id>', methods=['GET'])
def get_event(event_id): 
    """GET JSON of a specific event"""
    if event_id not in events:
        return flask.jsonify({'error': 'Event not found'}), 404
    
    event = events[event_id]
    return flask.jsonify({'rounds': [ 
        [
            (g.group_letter, list(event.pilots[p].name for p in g.pilots))
            for g in r.groups
            ]
        for r in event.rounds
    ]})

### /api/event/<event-id>/round/<round-number> 
@app.route('/api/event/<int:event_id>/round/<int:round_number>', methods=['GET'])
def get_event_round(event_id, round_number): 
    """GET JSON of a specific event round"""
    if event_id not in events:
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

### /api/event/<event-id>/round/<round-number>/group/<group-letter> 
@app.route('/api/event/<int:event_id>/round/<int:round_number>/group/<group_letter>', methods=['GET'])
def get_event_round_group(event_id, round_number, group_letter): 
    """GET JSON of a specific event round group"""
    if event_id not in events:
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

@app.route('/event/<int:event_id>', methods=['GET'])
def view_event(event_id):
    """Client page to view event status"""

    return flask.render_template('event_viewer.html', event_id=event_id)

@app.route('/api/event/<event_id>/state', methods=['POST'])
def state(event_id):
    data = flask.request.json
    # Channel should be a string
    #sse.publish(data, type="state", channel=str(event_id))  
    return {}, 200


@app.route("/")
def index():
    return flask.render_template('event_selector.html')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))