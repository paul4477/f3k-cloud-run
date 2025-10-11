import os
import time
#import functions_framework
#import yaml


##
## Event class in separate file
## GET / show event list
##  init creates rounds, groups and sections from POSTed json to /{event id}
## add the event to global dict of events
## persist it somewhere (individual events)
## GET /{event id} returns json of event (summary) [if we haven't got it cached then we load it from f3xvault and transform to our local structure]
## GET /{event id}/round/{round number} returns json of round
## GET /{event id}/round/{round number}/group/{group letter} returns json of group
## GET /{event id}/round/{round number}/group/{group letter}/section/{section index} returns json of section

## GET /{event id}/state ## polled by client for updates
#https://flask-sse.readthedocs.io/en/latest/quickstart.html
# if client sees section change then they can request the details of the new section
# on group change the client can request the pilot list (and perhaps the next one too?)
## where does the pilot list from in?

## POST /{event id}/timer # receives frequent time updates (every second?) from the event runner - can we ws or stream this? reconnect when needed? is htat reliable?
## POST /{event id}/state # receives state changes - round, group, section changes including pilot lists for groups


###



import flask

app = flask.Flask(__name__)

from f3k_cl_competition import Round, Group, make_rounds


import json
data = json.load(open('data/test_data.json'))
rounds = make_rounds(data)

def custom_json(obj):
    if isinstance(obj, Round):
        return {'round_number': obj.round_number, 'groups': obj.groups}
    if isinstance(obj, Group):
        return {'group_letter': obj.group_letter, 'sections': obj.sections}
    if isinstance(obj, Section):
        return {'section_type': obj.__class.__name__, 'section_time': obj.sectionTime}
    raise TypeError(f'Cannot serialize object of {type(obj)}')

def format_sse(data: str, event=None) -> str:
    msg = f'data: {data}\n\n'
    if event is not None:
        msg = f'event: {event}\n{msg}'
    return msg


@app.route('/ping')
def ping():
    msg = format_sse(data=time.time(), event="pong")
    announcer.announce(msg=msg)
    return {}, 200


@app.route('/state', methods=['POST'])
def state():
    data = flask.request.json
    msg = format_sse(data, event="state")
    announcer.announce(msg=msg)
    return {}, 200


@app.route("/")
def hello():
    
    return flask.render_template('test.html')

@app.route('/listen', methods=['GET'])
def listen():

    def stream():
        messages = announcer.listen()  # returns a queue.Queue
        while True:
            msg = messages.get()  # blocks until a new message arrives
            yield msg

    return flask.Response(stream(), mimetype='text/event-stream')

from typing import Callable, Optional
import cl_messages
announcer: Optional[cl_messages.MessageAnnouncer] = None
with app.app_context():
    
    announcer = cl_messages.MessageAnnouncer()

"""@app.route("/")
def hello_world():
    #ame = os.environ.get("NAME", "World")
    out = {}
    for r in rounds:
        for g in r:
            for s in g.sections:
                out[s.get_serial_code()] = s.get_description()
    return json.dumps({'data': rounds, 'o': out}, default=custom_json)"""


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
